"""The live accumulators, on their own terms.

Every ``windowed_*`` function folds one of these three types, so the windowed
tests do reach them -- but only through a wrapper, and only over inputs a window
can produce. That leaves three things unchecked, and they are what this file is
for: each accumulator's contract stated directly rather than inferred from a
caller, the states the wrapper cannot reach (an accumulator that has seen
nothing, which ``_tumbling`` never yields), and the property no wrapper test can
express -- that folding one observation at a time agrees with computing over the
whole stream at once.

The last is the nearest thing here to what the differential harness gives the
solver. There is no second implementation of a Brier score to compare against,
so the reference is the definition itself computed in one pass; what is under
test is the folding, which is where an accumulator goes wrong.
"""

import types
from dataclasses import FrozenInstanceError
from statistics import fmean

import pytest
from hypothesis import given
from hypothesis import strategies as st

from endoxa.instruments import calibration
from endoxa.instruments.calibration import (
    AskOutcomeCounts,
    BrierAccumulator,
    CalibrationSnapshot,
    KnowledgeCalibrationStats,
)

#: Resolved predictions: a probability in [0, 1] and what actually happened.
PREDICTIONS = st.lists(
    st.tuples(st.floats(min_value=0.0, max_value=1.0, allow_nan=False), st.booleans()),
    min_size=1,
    max_size=64,
)

OUTCOMES = st.lists(st.sampled_from(["affirmed", "denied", "timed_out"]), min_size=1, max_size=64)


def _fold_predictions(pairs) -> BrierAccumulator:
    accumulator = BrierAccumulator()
    for probability, success in pairs:
        accumulator = accumulator.observe(predicted_probability=probability, success=success)
    return accumulator


def _fold_outcomes(outcomes) -> AskOutcomeCounts:
    counts = AskOutcomeCounts()
    for outcome in outcomes:
        counts = counts.observe(outcome)
    return counts


# --- The competence accumulator (Brier) ----------------------------------------


def test_a_fresh_accumulator_scores_none() -> None:
    """No observations is not a score of zero.

    The wrapper never asks: tumbling windows are never empty, so nothing on the
    windowed path can tell a perfect accumulator from an empty one.
    """
    assert BrierAccumulator().score() is None
    assert BrierAccumulator().count == 0


def test_certainty_that_was_right_scores_zero_and_certainty_that_was_wrong_scores_one() -> None:
    """The two ends of the scale, which fix its direction: lower is better."""
    assert BrierAccumulator().observe(predicted_probability=1.0, success=True).score() == 0.0
    assert BrierAccumulator().observe(predicted_probability=1.0, success=False).score() == 1.0


def test_the_score_is_a_mean_and_not_a_sum() -> None:
    """Two identical errors score the same as one, or the metric would punish volume."""
    one = BrierAccumulator().observe(predicted_probability=0.5, success=True)
    two = one.observe(predicted_probability=0.5, success=True)
    assert one.score() == two.score() == pytest.approx(0.25)
    assert two.count == 2


def test_observing_leaves_the_original_alone() -> None:
    """The type is frozen, and the fold has to return rather than mutate."""
    before = BrierAccumulator().observe(predicted_probability=0.0, success=False)
    after = before.observe(predicted_probability=1.0, success=False)
    assert before.count == 1
    assert after.count == 2
    with pytest.raises(FrozenInstanceError):
        before.count = 99


@given(PREDICTIONS)
def test_folding_one_at_a_time_agrees_with_the_whole_stream_at_once(pairs) -> None:
    """The reference is the definition, computed in one pass over everything."""
    expected = fmean([(probability - (1.0 if success else 0.0)) ** 2 for probability, success in pairs])
    assert _fold_predictions(pairs).score() == pytest.approx(expected)


@given(PREDICTIONS)
def test_the_score_stays_in_the_unit_interval(pairs) -> None:
    """A probability in [0, 1] cannot produce a squared error outside it."""
    score = _fold_predictions(pairs).score()
    assert score is not None
    assert 0.0 <= score <= 1.0


@given(PREDICTIONS)
def test_the_order_of_the_stream_does_not_move_the_score(pairs) -> None:
    """Brier is an unordered mean; a fold that drifts with order is a fold that drifts."""
    assert _fold_predictions(pairs).score() == pytest.approx(_fold_predictions(list(reversed(pairs))).score())


# --- The ask-policy counters ---------------------------------------------------


def test_fresh_counters_report_none_for_both_rates() -> None:
    """Never having asked is not a resolution rate of zero."""
    counts = AskOutcomeCounts()
    assert counts.resolution_rate() is None
    assert counts.affirm_rate() is None


def test_each_outcome_lands_in_its_own_counter() -> None:
    counts = _fold_outcomes(["affirmed", "affirmed", "denied", "timed_out"])
    assert (counts.affirmed, counts.denied, counts.timed_out) == (2, 1, 1)


def test_the_two_rates_have_different_denominators() -> None:
    """Timeouts count against resolution and are invisible to affirmation.

    Both rates would be the same number if the denominators were shared, and the
    distinction is the whole point of keeping two.
    """
    counts = _fold_outcomes(["affirmed", "timed_out"])
    assert counts.resolution_rate() == 0.5
    assert counts.affirm_rate() == 1.0


def test_questions_that_only_ever_timed_out_have_no_affirmation_rate() -> None:
    """Resolution is zero -- a real reading -- while affirmation has nothing to divide."""
    counts = _fold_outcomes(["timed_out", "timed_out"])
    assert counts.resolution_rate() == 0.0
    assert counts.affirm_rate() is None


def test_observing_an_outcome_leaves_the_original_alone() -> None:
    before = AskOutcomeCounts().observe("affirmed")
    after = before.observe("denied")
    assert (before.affirmed, before.denied) == (1, 0)
    assert (after.affirmed, after.denied) == (1, 1)


@given(OUTCOMES)
def test_the_counters_account_for_every_question(outcomes) -> None:
    """Nothing is dropped and nothing is counted twice."""
    counts = _fold_outcomes(outcomes)
    assert counts.affirmed + counts.denied + counts.timed_out == len(outcomes)


# --- The knowledge-calibration counters ----------------------------------------


def test_fresh_stats_report_none_for_both_rates() -> None:
    stats = KnowledgeCalibrationStats()
    assert stats.overconfidence_rate() is None
    assert stats.unknown_confirmation_rate() is None


def test_a_first_sighting_is_not_a_transition() -> None:
    """``previous=None`` means the target was never classified before.

    Counting it as an arrival would make every target that starts out ``known``
    look like a confirmed unknown.
    """
    stats = KnowledgeCalibrationStats().observe_transition(
        previous=None,
        status="known",
        first_time_known=True,
        first_time_nonknown=False,
    )
    assert stats.known_ever == 1
    assert stats.known_to_nonknown == 0
    assert stats.nonknown_to_known == 0
    assert stats.overconfidence_rate() == 0.0


def test_leaving_known_is_overconfidence() -> None:
    stats = KnowledgeCalibrationStats(known_ever=1).observe_transition(
        previous="known",
        status="uncertain",
        first_time_known=False,
        first_time_nonknown=True,
    )
    assert stats.known_to_nonknown == 1
    assert stats.overconfidence_rate() == 1.0


def test_arriving_at_known_from_anywhere_else_is_confirmation() -> None:
    for previous in ("uncertain", "unknown"):
        stats = KnowledgeCalibrationStats(nonknown_ever=1).observe_transition(
            previous=previous,
            status="known",
            first_time_known=True,
            first_time_nonknown=False,
        )
        assert stats.nonknown_to_known == 1, previous
        assert stats.unknown_confirmation_rate() == 1.0


def test_staying_put_counts_as_neither() -> None:
    """Both directions require a crossing, and ``uncertain`` to ``unknown`` is not one."""
    held = KnowledgeCalibrationStats().observe_transition(
        previous="known",
        status="known",
        first_time_known=False,
        first_time_nonknown=False,
    )
    drifted = KnowledgeCalibrationStats().observe_transition(
        previous="uncertain",
        status="unknown",
        first_time_known=False,
        first_time_nonknown=False,
    )
    assert (held.known_to_nonknown, held.nonknown_to_known) == (0, 0)
    assert (drifted.known_to_nonknown, drifted.nonknown_to_known) == (0, 0)


def test_the_denominators_are_the_callers_to_supply() -> None:
    """Aggregates live here; per-target membership belongs to whoever folds them.

    Stated as a test because it is the one part of the contract a caller can get
    wrong without anything failing: pass ``first_time_known`` twice for the same
    target and the rate quietly halves.
    """
    stats = KnowledgeCalibrationStats()
    for _ in range(2):
        stats = stats.observe_transition(
            previous="known",
            status="unknown",
            first_time_known=True,
            first_time_nonknown=False,
        )
    assert stats.known_ever == 2
    assert stats.known_to_nonknown == 2
    assert stats.overconfidence_rate() == 1.0


def test_observing_a_transition_leaves_the_original_alone() -> None:
    before = KnowledgeCalibrationStats()
    after = before.observe_transition(
        previous=None,
        status="known",
        first_time_known=True,
        first_time_nonknown=False,
    )
    assert before.known_ever == 0
    assert after.known_ever == 1


# --- The snapshot and the public surface ---------------------------------------


def test_the_snapshot_bundles_the_three_facets_without_recomputing_them() -> None:
    """It is a coherent read, not a fourth accounting."""
    knowledge = KnowledgeCalibrationStats(known_ever=3, known_to_nonknown=1)
    competence = BrierAccumulator().observe(predicted_probability=0.25, success=False)
    ask = AskOutcomeCounts().observe("denied")
    snapshot = CalibrationSnapshot(knowledge=knowledge, competence_brier=competence, ask_policy=ask)
    assert snapshot.knowledge.overconfidence_rate() == pytest.approx(1 / 3)
    assert snapshot.competence_brier.score() == pytest.approx(0.0625)
    assert snapshot.ask_policy.affirm_rate() == 0.0
    with pytest.raises(FrozenInstanceError):
        snapshot.knowledge = knowledge


def test_the_export_list_and_the_package_agree() -> None:
    """An enumeration without a check is an enumeration that rots.

    Both directions: a name promised but gone breaks an importer, and a name
    present but unpromised is public by accident.
    """
    promised = set(calibration.__all__)
    present = {
        name
        for name, value in vars(calibration).items()
        if not name.startswith("_") and not isinstance(value, types.ModuleType)
    }
    assert promised - present == set(), f"exported but missing: {sorted(promised - present)}"
    assert present - promised == set(), f"public but unexported: {sorted(present - promised)}"
