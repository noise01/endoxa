"""Pure windowed recomputation of calibration metrics from an ordered stream.

The live calibration instruments fold observations into *monotonic cumulative*
counters. That is the right shape for a live query, but it cannot draw an
*improvement curve*: early immaturity and late maturity blur together in a single
running mean. This module recomputes the same three metrics over **count-based
tumbling windows** of a replayed, time-ordered observation stream, so a Brier
improvement curve -- or a cross-session A/B -- can be drawn offline.

Design:

- **The live instruments stay untouched.** They may be feeding a reward signal,
  and changing the definition of a measure that something optimises against
  changes behaviour. This is a separate, read-only recomputation path over a
  persisted log.
- **Reuse, don't reimplement.** Each window folds the very same
  :class:`BrierAccumulator` / :class:`KnowledgeCalibrationStats` /
  :class:`AskOutcomeCounts` the live module uses, starting from a fresh instance
  per window. No new accounting logic is introduced here.
- **Knowledge first-time tracking is window-local.** The overconfidence /
  unknown-confirmation rates count, *within each window*, the targets newly
  classified ``known`` / non-``known`` in that window (the live module tracks
  ``_known_seen`` / ``_nonknown_seen`` across all time). Resetting per window is
  what makes the rate a per-window quantity readable as a curve rather than a
  cumulative fraction dominated by early observations.

This module is a pure function of its inputs and unit-testable in isolation; the
replay adapter that builds the observation streams from persisted events lives
in :mod:`endoxa.instruments.calibration.replay`.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from endoxa.instruments.calibration.ask_policy import AskOutcome, AskOutcomeCounts
from endoxa.instruments.calibration.competence import BrierAccumulator
from endoxa.instruments.calibration.knowledge import KnowledgeCalibrationStats

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


@dataclass(slots=True, frozen=True)
class CompetenceObservation:
    """One resolved prediction feeding the competence Brier score.

    Attributes:
        predicted_probability: The predicted success probability in ``[0.0, 1.0]``.
        success: Whether the action actually succeeded.
    """

    predicted_probability: float
    success: bool


@dataclass(slots=True, frozen=True)
class KnowledgeObservation:
    """One epistemic-status transition feeding the knowledge-calibration rates.

    Attributes:
        target: Identifier of the belief whose status transitioned.
        previous_status: The status before this transition, or ``None`` if this
            is the first observation of the target.
        status: The status after this transition.
    """

    target: str
    previous_status: str | None
    status: str


@dataclass(slots=True, frozen=True)
class AskObservation:
    """One resolved ask-user question feeding the ask-policy counters.

    Attributes:
        outcome: How the question resolved ("affirmed", "denied", "timed_out").
    """

    outcome: AskOutcome


@dataclass(slots=True, frozen=True)
class CompetenceWindow:
    """Competence calibration over one tumbling window.

    Attributes:
        index: Zero-based window index in stream order.
        count: Number of observations folded into this window.
        brier: Mean Brier score for the window, or ``None`` if empty.
    """

    index: int
    count: int
    brier: float | None


@dataclass(slots=True, frozen=True)
class KnowledgeWindow:
    """Knowledge calibration over one tumbling window.

    Attributes:
        index: Zero-based window index in stream order.
        count: Number of transitions folded into this window.
        overconfidence_rate: Fraction of targets first classified ``known`` in
            this window that later (still within the window) left ``known``, or
            ``None`` if no target was classified ``known`` in the window.
        unknown_confirmation_rate: Fraction of targets first classified
            non-``known`` in this window that later became ``known``, or ``None``.
    """

    index: int
    count: int
    overconfidence_rate: float | None
    unknown_confirmation_rate: float | None


@dataclass(slots=True, frozen=True)
class AskWindow:
    """Ask-policy quality over one tumbling window.

    Attributes:
        index: Zero-based window index in stream order.
        count: Number of resolved questions folded into this window.
        resolution_rate: Fraction of questions resolved (not timed out), or
            ``None`` if the window is empty.
        affirm_rate: Fraction of resolved questions that were affirmed, or
            ``None`` if none resolved.
    """

    index: int
    count: int
    resolution_rate: float | None
    affirm_rate: float | None


Window = CompetenceWindow | KnowledgeWindow | AskWindow


@dataclass(slots=True, frozen=True)
class WindowedCalibrationCurve:
    """A homogeneous series of per-window calibration readings.

    Attributes:
        metric: Which metric this curve is over ("competence", "knowledge" or
            "ask").
        window_size: The tumbling-window size the stream was split by.
        windows: The per-window readings in stream order (the last window may be
            partial when the stream length is not a multiple of ``window_size``).
    """

    metric: str
    window_size: int
    windows: tuple[Window, ...]


def _tumbling[T](seq: Sequence[T], window_size: int) -> Iterator[tuple[int, Sequence[T]]]:
    """Yield ``(index, chunk)`` tumbling windows of ``window_size`` over ``seq``.

    The final chunk is yielded even when partial (shorter than ``window_size``).

    Args:
        seq: The ordered sequence to split.
        window_size: Window size; must be at least 1.

    Yields:
        ``(index, chunk)`` pairs, ``index`` zero-based in stream order.

    Raises:
        ValueError: If ``window_size`` is less than 1.
    """
    if window_size < 1:
        msg = f"window_size must be >= 1, got {window_size}"
        raise ValueError(msg)
    for start in range(0, len(seq), window_size):
        yield start // window_size, seq[start : start + window_size]


def windowed_competence(
    observations: Sequence[CompetenceObservation],
    window_size: int,
) -> WindowedCalibrationCurve:
    """Recompute the competence Brier score over tumbling windows.

    Args:
        observations: Resolved predictions in stream (time) order.
        window_size: Tumbling-window size (>= 1).

    Returns:
        A :class:`WindowedCalibrationCurve` of :class:`CompetenceWindow`.
    """
    windows: list[Window] = []
    for index, chunk in _tumbling(observations, window_size):
        acc = BrierAccumulator()
        for obs in chunk:
            acc = acc.observe(predicted_probability=obs.predicted_probability, success=obs.success)
        windows.append(CompetenceWindow(index=index, count=acc.count, brier=acc.score()))
    return WindowedCalibrationCurve(metric="competence", window_size=window_size, windows=tuple(windows))


def windowed_knowledge(
    observations: Sequence[KnowledgeObservation],
    window_size: int,
) -> WindowedCalibrationCurve:
    """Recompute the knowledge-calibration rates over tumbling windows.

    First-time ``known``/non-``known`` membership is tracked window-locally (see
    module docstring), mirroring the live module's per-target logic reset at each
    window boundary.

    Args:
        observations: Epistemic-status transitions in stream (time) order.
        window_size: Tumbling-window size (>= 1).

    Returns:
        A :class:`WindowedCalibrationCurve` of :class:`KnowledgeWindow`.
    """
    windows: list[Window] = []
    for index, chunk in _tumbling(observations, window_size):
        stats = KnowledgeCalibrationStats()
        known_seen: set[str] = set()
        nonknown_seen: set[str] = set()
        for obs in chunk:
            first_time_known = obs.status == "known" and obs.target not in known_seen
            first_time_nonknown = obs.status != "known" and obs.target not in nonknown_seen
            if obs.status == "known":
                known_seen.add(obs.target)
            else:
                nonknown_seen.add(obs.target)
            stats = stats.observe_transition(
                previous=obs.previous_status,  # type: ignore[arg-type]
                status=obs.status,  # type: ignore[arg-type]
                first_time_known=first_time_known,
                first_time_nonknown=first_time_nonknown,
            )
        windows.append(
            KnowledgeWindow(
                index=index,
                count=len(chunk),
                overconfidence_rate=stats.overconfidence_rate(),
                unknown_confirmation_rate=stats.unknown_confirmation_rate(),
            ),
        )
    return WindowedCalibrationCurve(metric="knowledge", window_size=window_size, windows=tuple(windows))


def windowed_ask(
    observations: Sequence[AskObservation],
    window_size: int,
) -> WindowedCalibrationCurve:
    """Recompute the ask-policy counters over tumbling windows.

    Args:
        observations: Resolved ask-user questions in stream (time) order.
        window_size: Tumbling-window size (>= 1).

    Returns:
        A :class:`WindowedCalibrationCurve` of :class:`AskWindow`.
    """
    windows: list[Window] = []
    for index, chunk in _tumbling(observations, window_size):
        counts = AskOutcomeCounts()
        for obs in chunk:
            counts = counts.observe(obs.outcome)
        windows.append(
            AskWindow(
                index=index,
                count=len(chunk),
                resolution_rate=counts.resolution_rate(),
                affirm_rate=counts.affirm_rate(),
            ),
        )
    return WindowedCalibrationCurve(metric="ask", window_size=window_size, windows=tuple(windows))
