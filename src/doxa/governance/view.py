"""The current view as a derivation of the ledger.

RFC-0063 declares that **the current view is derived from the ledger**. This
module is that declaration executed: fold the operation series and what comes out
is what the system holds -- including the beliefs it holds *without deciding
between them*.

``UNRESOLVED`` is the point of the exercise. Being unable to settle a
contradiction has been a real state since ADR-0082, and the system already speaks
about it (the tie question), but it has never had a name in the state itself: a
held tie was indistinguishable from two ordinary beliefs that happen to conflict.
Here it is a value of :attr:`BeliefState.state`, and both sides carry it.

**Releasing a hold is derived, never asserted**. A hold
is not a lock: it is the name of "the preference cannot separate these two"
, so it ends when the preference *can* -- when a later operation moves
one side out of the other's band. :attr:`BeliefState.released_by` reads back which
operation did it.

**The synthetic-layer 1.0 rule** (``backlog.md`` §6(e)(v), RFC-0023 §6) is stated
once, here: ``ground`` is the only operation that confers 1.0, so a
grounded answer is the one operation that always separates a band and directly
releases a hold. Evidence can release one too, but only by actually moving a
credence -- which is the difference between settling a tie and outranking it.

**On replaying the Laplace fold.** ``confirm``/``refute`` carry no confidence:
the host's event says only which way the evidence points, and the credence is
computed by ``domains/blackboard/evidence.py``. To reconstruct a view
that can be *checked* against the board, this module replays the same arithmetic.
That is a fourth copy of Laplace smoothing in the codebase (ADR-0075 counted
three), and it is deliberate: an asset may not import host domain code, and a
view that gave up on confidence could not tell a correct derivation from one that
lost half its evidence. The copy collapses when the evidence rule itself moves
into ``kernel/governance`` in the Phase 2 migration (increment 3).

Pure and basis-independent (stdlib only).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from doxa.governance.ledger import LedgerOp, TargetKind

#: A belief the view holds outright.
HELD = "HELD"

#: A belief the view holds *without* being able to prefer it or its rival: the
#: first-class form of the unsettleable tie. Both sides of the tie
#: carry it, and neither is withdrawn -- holding both is the calibrated answer,
#: and picking one would be arbitrariness.
UNRESOLVED = "UNRESOLVED"

BeliefStatus = Literal["HELD", "UNRESOLVED"]

#: Mirrors ``kernel/governance/tms/preference.py``: a belief with no explicit confidence is
#: inviolable, revision failing safe toward not touching an unmarked belief.
_DEFAULT_CONFIDENCE = 1.0

#: Mirrors ``kernel/governance/tms/preference.py``'s band tolerance. The two derivations of
#: "does the preference separate these?" are kept independent on purpose -- the
#: asset may not import the host's TMS -- and a test pins them against each other,
#: so the day one is changed alone, it shows up as a failure rather than as a
#: silent divergence between what the system does and what its ledger says.
_CONFIDENCE_EPSILON = 1e-9

#: The role a conjecture is written under (``belief_context``), which the
#: revision preference reaches for first.
_HYPOTHESIS = "hypothesis"

#: Defaults for the evidence fold, mirroring ``settings.belief_evidence_*``.
DEFAULT_PRIOR_STRENGTH = 2.0
DEFAULT_CONFIDENCE_CEILING = 0.99


@dataclass(frozen=True, slots=True)
class BeliefState:
    """What the ledger says is currently the case about one target.

    Attributes:
        target: The belief's node id, or the rule's memory id.
        target_kind: Which of those it is.
        truth_value: The claim the target currently makes.
        confidence: The credence, or ``None`` when no operation ever stated one
            and none was derived (an unmarked belief; see ``_DEFAULT_CONFIDENCE``
            for how the preference reads that).
        status: ``HELD`` or ``UNRESOLVED``.
        context: The role the target was born under (``belief_context`` on the
            board), which is what the revision preference reads to tell a
            conjecture from an assertion.
        held_with: The other side of the tie, while unresolved.
        released_by: The ``origin_event_id`` of the operation that ended the last
            hold, or ``None`` when it was never held or is held still.
        evidence_prior: The credence burned in at the first piece of evidence,
            and the for/against tally since. Kept because the fold
            is path-dependent -- the posterior cannot be recomputed from the
            confidence alone.
        evidence_for: Corroborations folded in so far.
        evidence_against: Counter-evidence folded in so far.
    """

    target: str
    target_kind: TargetKind = "atom"
    truth_value: bool = True
    confidence: float | None = None
    status: BeliefStatus = HELD
    context: str = ""
    held_with: str | None = None
    released_by: str | None = None
    evidence_prior: float | None = None
    evidence_for: int = 0
    evidence_against: int = 0


@dataclass(frozen=True, slots=True)
class ViewEquivalence:
    """The result of checking a reconstructed view against the live board.

    RFC-0063 §7 criterion 3 asks for zero breakage between the view the ledger
    reconstructs and what the blackboard actually holds. Several numbers rather
    than one, because they fail for different reasons and blurring them would
    hide the interesting one.

    ``UNRESOLVED`` has no counterpart here, and that is not an omission: **the
    board cannot represent a hold**. Two beliefs the preference could not
    separate sit on it as two ordinary beliefs, which is the gap this increment
    closes. There is nothing on the other side for the ledger's status to break
    against, so it is fixed by the positive control instead (RFC-0063 §7
    criterion 4) rather than by this comparison.

    Attributes:
        compared: Targets checked on both sides.
        truth_breaks: Targets whose truth value disagrees. **This is the
            invariant**: a non-zero count means the derivation misread an
            operation.
        confidence_breaks: Targets whose credence disagrees among those whose
            evidence the ledger could fully account for.
        unattributed: Targets excluded from the credence comparison because the
            two sides' evidence tallies disagree. **Expected to be zero**: this
            column was the write side's silences, and RFC-0065 increment 1 closed
            them -- the board no longer moves a credence without recording it
            . Two things can still put a target here, and they are not
            the same:

            - **A regression in the recording path.** A booking the board folded
              and did not record, or recorded and did not fold. Either way the
              write side and the ledger have come apart again.
            - **A restore that brought no tally back.** The ledger keeps a
              belief's whole series, so a belief that returned to the board
              without its counts reads as saying less than the audit log can
              account for. Paging carries the tally now, which is what
              made this column an invariant rather than a residual; what remains
              are the restores whose source has no tally to give -- a broadcast
              persists a proposition, not its evidence. Paging itself
              is still not a ledger operation: the fix was to
              stop the board forgetting, not to teach the ledger to forget.

            Note the test is a disagreement, not an inequality: the ledger
            holding *more* than the board lands here too, which is what makes
            the second case visible at all.
        missing_from_board: Targets the ledger knows that the board no longer
            has -- paged out to LTM or evicted. Excluded from the
            comparison rather than counted as breakage, and reported so the
            exclusion is never invisible.
        details: Human-readable lines for the disagreements, for a failing test
            or a diagnostic run to print.
    """

    compared: int = 0
    truth_breaks: int = 0
    confidence_breaks: int = 0
    unattributed: int = 0
    missing_from_board: int = 0
    details: tuple[str, ...] = field(default_factory=tuple)


def reconstruct_view(
    ops: Sequence[LedgerOp],
    *,
    prior_strength: float = DEFAULT_PRIOR_STRENGTH,
    ceiling: float = DEFAULT_CONFIDENCE_CEILING,
) -> dict[str, BeliefState]:
    """Fold the ledger into the current view.

    Args:
        ops: The operation series, in order.
        prior_strength: Pseudo-observations backing the evidence prior.
        ceiling: Upper bound the evidence fold may reach, strictly below 1.0.

    Returns:
        The state of every target the series mentions, keyed by target.
    """
    view: dict[str, BeliefState] = {}
    for op in ops:
        first_seen = op.target not in view
        state = view.get(op.target) or BeliefState(
            target=op.target,
            target_kind=op.target_kind,
            context=op.actor,
        )
        view[op.target] = _apply(
            state,
            op,
            prior_strength=prior_strength,
            ceiling=ceiling,
            first_seen=first_seen,
        )
        if op.op == "hold" and op.partner is not None:
            partner = view.get(op.partner) or BeliefState(target=op.partner)
            view[op.partner] = replace(partner, status=UNRESOLVED, held_with=op.target, released_by=None)
        _release_holds(view, op)
    return view


def _apply(
    state: BeliefState,
    op: LedgerOp,
    *,
    prior_strength: float,
    ceiling: float,
    first_seen: bool,
) -> BeliefState:
    """Apply one operation to one target's state.

    ``first_seen`` says whether the series has mentioned this target before, which
    the evidence re-attribution below needs and the state alone cannot supply: a
    fresh :class:`BeliefState` is indistinguishable from one that has settled on
    the same values.
    """
    if op.op == "hold":
        return replace(state, status=UNRESOLVED, held_with=op.partner, released_by=None)
    if op.op in {"confirm", "refute"}:
        return _fold_evidence(state, supports=op.op == "confirm", prior_strength=prior_strength, ceiling=ceiling)
    updated = replace(
        state,
        truth_value=state.truth_value if op.truth_value is None else op.truth_value,
        confidence=state.confidence if op.confidence is None else op.confidence,
    )
    if op.op == "retract" and op.target_kind == "atom" and op.confidence is None:
        # The flip re-attributes the belief's own evidence to the claim it now
        # makes (``swap_evidence``). The two conditions mirror the
        # board's own: it swaps only for an atom, and only when the write stated
        # no confidence -- a writer that states one is declaring a credence for
        # the new claim, and a tally kept for the old one must not overrule it.
        # A retracted *rule* has no tally at all: its retraction is the stated
        # confidence itself (``_retract_rule``).
        return _swap_evidence(updated, prior_strength=prior_strength, ceiling=ceiling)
    if _is_grounded_reversal(state, op, first_seen=first_seen):
        return _swap_evidence(updated, prior_strength=prior_strength, ceiling=ceiling)
    return updated


def _is_grounded_reversal(state: BeliefState, op: LedgerOp, *, first_seen: bool) -> bool:
    """Whether a ``ground`` also reversed a belief the board already held.

    An ask-user answer wins the operation whatever else the write does
    (:mod:`~doxa.governance.derive`), which is right --
    conferring confidence 1.0 is the thing that only this operation does. But the
    write can *also* be a reversal, and then the board re-attributes the belief's
    evidence exactly as it does for a revision flip: its test is "the truth value
    changed and no confidence was stated", and it does not ask which operation
    the ledger will call it.

    So this restates the board's own test rather than keying off the operation
    name. All three conditions are the board's: an existing belief
    (``truth_flipped`` is only set for a node already there), a changed truth
    value, and no stated confidence.

    Found by RFC-0065 increment 1 -- **while the write side was silent
    this could not be seen**, because ``unattributed`` was expected to be non-zero
    for other reasons and a target landing there said nothing in particular.
    """
    return (
        op.op == "ground"
        and op.target_kind == "atom"
        and op.confidence is None
        and not first_seen
        and op.truth_value is not None
        and op.truth_value != state.truth_value
    )


def _release_holds(view: dict[str, BeliefState], op: LedgerOp) -> None:
    """End any hold this operation just made settleable.

    A hold is released when the preference can separate the pair again -- when
    the two sides no longer share a band. The releasing operation is recorded so
    the release can be read back with a time and an author, without ever having
    been a first-class operation of its own.
    """
    if op.op == "hold":
        return
    state = view.get(op.target)
    if state is None or state.status != UNRESOLVED or state.held_with is None:
        return
    partner = view.get(state.held_with)
    if partner is None or _same_band(state, partner):
        return
    view[op.target] = replace(state, status=HELD, held_with=None, released_by=op.origin_event_id)
    if partner.held_with == op.target:
        view[state.held_with] = replace(partner, status=HELD, held_with=None, released_by=op.origin_event_id)


def _band_key(state: BeliefState) -> tuple[bool, float]:
    """Where the revision preference ranks this belief.

    The host's derivation of the same judgement is ``kernel/governance/tms/preference.py``
    ``band_key``; see ``_CONFIDENCE_EPSILON`` on why there are two.
    """
    confidence = _DEFAULT_CONFIDENCE if state.confidence is None else state.confidence
    return (state.context != _HYPOTHESIS, confidence)


def _same_band(left: BeliefState, right: BeliefState) -> bool:
    """Whether the preference ranks two beliefs identically."""
    left_key, right_key = _band_key(left), _band_key(right)
    return left_key[0] == right_key[0] and abs(left_key[1] - right_key[1]) <= _CONFIDENCE_EPSILON


def _posterior(*, prior: float, for_count: int, against_count: int, prior_strength: float, ceiling: float) -> float:
    """Laplace-smoothed credence from a prior mean and a for/against tally."""
    numerator = prior * prior_strength + for_count
    denominator = prior_strength + for_count + against_count
    return min(numerator / denominator, ceiling)


def _fold_evidence(
    state: BeliefState,
    *,
    supports: bool,
    prior_strength: float,
    ceiling: float,
) -> BeliefState:
    """Book one piece of evidence (mirroring ``fold_evidence``).

    An inviolable belief is left alone: it cannot become more certain, and
    running it through the update would only lower it.
    """
    confidence = _DEFAULT_CONFIDENCE if state.confidence is None else state.confidence
    if confidence >= 1.0:
        return state
    prior = state.evidence_prior if state.evidence_prior is not None else confidence
    for_count = state.evidence_for + (1 if supports else 0)
    against_count = state.evidence_against + (0 if supports else 1)
    posterior = _posterior(
        prior=prior,
        for_count=for_count,
        against_count=against_count,
        prior_strength=prior_strength,
        ceiling=ceiling,
    )
    if posterior == confidence and state.evidence_prior is not None:
        return state
    return replace(
        state,
        confidence=posterior,
        evidence_prior=prior,
        evidence_for=for_count,
        evidence_against=against_count,
    )


def _swap_evidence(state: BeliefState, *, prior_strength: float, ceiling: float) -> BeliefState:
    """Hand a flipped belief's evidence to the claim it now makes (mirroring ``swap_evidence``).

    The counts support *what the target currently claims*, not a fixed
    proposition, so the counter-evidence that motivated the flip reads as one
    count for the new claim and the burned-in prior becomes its complement
    .
    """
    confidence = _DEFAULT_CONFIDENCE if state.confidence is None else state.confidence
    if confidence >= 1.0:
        return state
    prior = state.evidence_prior if state.evidence_prior is not None else confidence
    swapped_prior = 1.0 - prior
    swapped_for = state.evidence_against + 1
    swapped_against = state.evidence_for
    return replace(
        state,
        confidence=_posterior(
            prior=swapped_prior,
            for_count=swapped_for,
            against_count=swapped_against,
            prior_strength=prior_strength,
            ceiling=ceiling,
        ),
        evidence_prior=swapped_prior,
        evidence_for=swapped_for,
        evidence_against=swapped_against,
    )


def compare_to_state(
    view: Mapping[str, BeliefState],
    board: Mapping[str, Mapping[str, Any]],
) -> ViewEquivalence:
    """Check a reconstructed view against the live blackboard (criterion 3).

    Args:
        view: The output of :func:`reconstruct_view`.
        board: The blackboard's atom nodes, keyed by node id, each a mapping of
            the node attributes (``truth_value``/``confidence``/``evidence_*``).

    Returns:
        The tally of agreements and disagreements. See :class:`ViewEquivalence`
        for why credence is reported apart from truth, and what is excluded.
    """
    compared = truth_breaks = confidence_breaks = 0
    unattributed = missing = 0
    details: list[str] = []
    for target, state in view.items():
        if state.target_kind != "atom":
            continue
        node = board.get(target)
        if node is None:
            missing += 1
            continue
        compared += 1
        board_truth = bool(node.get("truth_value", True))
        if board_truth != state.truth_value:
            truth_breaks += 1
            details.append(f"truth {target}: ledger={state.truth_value} board={board_truth}")
        if _board_evidence(node) != (state.evidence_for, state.evidence_against):
            unattributed += 1
            continue
        board_confidence = node.get("confidence")
        if not _confidence_agrees(state.confidence, board_confidence):
            confidence_breaks += 1
            details.append(f"confidence {target}: ledger={state.confidence} board={board_confidence}")
    return ViewEquivalence(
        compared=compared,
        truth_breaks=truth_breaks,
        confidence_breaks=confidence_breaks,
        unattributed=unattributed,
        missing_from_board=missing,
        details=tuple(details),
    )


def _board_evidence(node: Mapping[str, Any]) -> tuple[int, int]:
    """Read the board's for/against tally for one node."""
    return (int(node.get("evidence_for", 0) or 0), int(node.get("evidence_against", 0) or 0))


def _confidence_agrees(ledger: float | None, board: object) -> bool:
    """Whether the ledger's credence matches the board's, both absences included."""
    if ledger is None or board is None:
        return ledger is None and board is None
    if not isinstance(board, (int, float)) or isinstance(board, bool):
        return False
    return abs(float(board) - ledger) <= _CONFIDENCE_EPSILON


__all__ = [
    "HELD",
    "UNRESOLVED",
    "BeliefState",
    "BeliefStatus",
    "ViewEquivalence",
    "compare_to_state",
    "reconstruct_view",
]
