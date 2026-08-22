import json

import pytest

from endoxa.instruments.calibration import (
    AskObservation,
    CompetenceObservation,
    KnowledgeObservation,
    observations_from_rows,
    windowed_ask,
    windowed_competence,
    windowed_knowledge,
)

# --- Unit: windowed competence (Brier) recomputation ---------------------------


def test_competence_splits_into_tumbling_windows() -> None:
    """A stream of N observations splits into ceil(N / window_size) windows."""
    observations = [CompetenceObservation(predicted_probability=1.0, success=True) for _ in range(5)]
    curve = windowed_competence(observations, window_size=2)
    assert curve.metric == "competence"
    assert curve.window_size == 2
    assert [w.index for w in curve.windows] == [0, 1, 2]
    assert [w.count for w in curve.windows] == [2, 2, 1]  # partial trailing window


def test_competence_brier_matches_hand_computation() -> None:
    """Each window's Brier is the mean squared error over just that window."""
    # Window 0: perfect predictions -> Brier 0.0. Window 1: p=0.0 but success -> (0-1)^2 = 1.0.
    observations = [
        CompetenceObservation(predicted_probability=1.0, success=True),
        CompetenceObservation(predicted_probability=1.0, success=True),
        CompetenceObservation(predicted_probability=0.0, success=True),
        CompetenceObservation(predicted_probability=0.0, success=True),
    ]
    curve = windowed_competence(observations, window_size=2)
    assert curve.windows[0].brier == 0.0
    assert curve.windows[1].brier == 1.0


def test_competence_partial_window_uses_its_own_count() -> None:
    """The trailing partial window averages only its own observations."""
    observations = [
        CompetenceObservation(predicted_probability=0.5, success=True),
        CompetenceObservation(predicted_probability=0.5, success=False),
        CompetenceObservation(predicted_probability=0.0, success=True),  # lone trailing obs
    ]
    curve = windowed_competence(observations, window_size=2)
    assert curve.windows[0].count == 2
    assert curve.windows[0].brier == 0.25  # (0.5^2 + 0.5^2) / 2
    assert curve.windows[1].count == 1
    assert curve.windows[1].brier == 1.0  # (0 - 1)^2


def test_competence_empty_stream_has_no_windows() -> None:
    """An empty stream yields an empty curve, not a zero-count window."""
    curve = windowed_competence([], window_size=4)
    assert curve.windows == ()


def test_competence_stream_shorter_than_window_is_one_partial_window() -> None:
    """Fewer observations than the window size collapse into a single window."""
    observations = [CompetenceObservation(predicted_probability=0.2, success=False) for _ in range(3)]
    curve = windowed_competence(observations, window_size=10)
    assert len(curve.windows) == 1
    assert curve.windows[0].count == 3


def test_window_size_below_one_is_rejected() -> None:
    """A window size of zero (or less) is a programming error, not silently clamped."""
    with pytest.raises(ValueError, match="window_size must be >= 1"):
        windowed_competence([], window_size=0)


# --- Unit: windowed knowledge recomputation (window-local first-time tracking) --


def test_knowledge_first_time_tracking_resets_per_window() -> None:
    """`known` membership is window-local: the same target counts fresh each window."""
    # Same target classified known in window 0 and again in window 1; with a
    # window size of 1 each observation is its own window, so it is "first time
    # known" in each -- proving per-window reset (the live cumulative module
    # would count it once).
    observations = [
        KnowledgeObservation(target="t", previous_status=None, status="known"),
        KnowledgeObservation(target="t", previous_status="known", status="known"),
    ]
    curve = windowed_knowledge(observations, window_size=1)
    assert len(curve.windows) == 2
    # Each window saw exactly one target enter `known` for the first time (locally).
    assert curve.windows[0].overconfidence_rate == 0.0
    assert curve.windows[1].overconfidence_rate == 0.0


def test_knowledge_overconfidence_within_a_window() -> None:
    """A target that enters and later leaves `known` inside one window is overconfidence."""
    observations = [
        KnowledgeObservation(target="a", previous_status=None, status="known"),
        KnowledgeObservation(target="a", previous_status="known", status="uncertain"),
    ]
    curve = windowed_knowledge(observations, window_size=10)
    assert len(curve.windows) == 1
    assert curve.windows[0].overconfidence_rate == 1.0


def test_knowledge_unknown_confirmation_within_a_window() -> None:
    """A target that starts non-`known` and becomes `known` is unknown-confirmation."""
    observations = [
        KnowledgeObservation(target="b", previous_status=None, status="unknown"),
        KnowledgeObservation(target="b", previous_status="unknown", status="known"),
    ]
    curve = windowed_knowledge(observations, window_size=10)
    assert curve.windows[0].unknown_confirmation_rate == 1.0


def test_knowledge_empty_rate_is_none() -> None:
    """A window with no `known` classification reports None, not 0.0, for overconfidence."""
    observations = [KnowledgeObservation(target="c", previous_status=None, status="unknown")]
    curve = windowed_knowledge(observations, window_size=10)
    assert curve.windows[0].overconfidence_rate is None


# --- Unit: windowed ask-policy recomputation -----------------------------------


def test_ask_window_rates() -> None:
    """Resolution and affirm rates are computed per window."""
    observations = [
        AskObservation(outcome="affirmed"),
        AskObservation(outcome="denied"),
        AskObservation(outcome="timed_out"),
        AskObservation(outcome="affirmed"),
    ]
    curve = windowed_ask(observations, window_size=4)
    window = curve.windows[0]
    assert window.count == 4
    assert window.resolution_rate == 0.75  # 3 of 4 resolved
    assert window.affirm_rate == pytest.approx(2 / 3)  # 2 of 3 resolved were affirmed


# --- Unit: replay adapter (persisted rows -> observation streams) --------------


def _row(event_type: str, payload: dict) -> dict:
    return {"event_type": event_type, "payload": json.dumps(payload)}


def test_replay_parses_all_three_streams() -> None:
    """Each event type routes to its own observation stream."""
    rows = [
        _row("PredictionOutcomeEvent", {"predicted_probability": 0.8, "success": True}),
        _row("KnowledgeCalibrationSignalEvent", {"target": "x", "previous_status": None, "status": "known"}),
        _row("QuestionResolvedEvent", {"key": "q1", "outcome": "affirmed"}),
    ]
    observations = observations_from_rows(rows)
    assert observations.competence == (CompetenceObservation(predicted_probability=0.8, success=True),)
    assert observations.knowledge == (KnowledgeObservation(target="x", previous_status=None, status="known"),)
    assert observations.ask == (AskObservation(outcome="affirmed"),)


def test_replay_skips_events_the_live_module_would_skip() -> None:
    """Predictions without a probability and questions without an outcome are dropped."""
    rows = [
        _row("PredictionOutcomeEvent", {"predicted_probability": None, "success": True}),
        _row("QuestionResolvedEvent", {"key": "q1", "outcome": None}),
    ]
    observations = observations_from_rows(rows)
    assert observations.competence == ()
    assert observations.ask == ()


def test_replay_skips_malformed_and_unrelated_rows() -> None:
    """Unparseable payloads and unrelated event types are ignored, not fatal."""
    rows = [
        {"event_type": "PredictionOutcomeEvent", "payload": "not-json"},
        _row("SomeOtherEvent", {"foo": "bar"}),
        _row("PredictionOutcomeEvent", {"predicted_probability": 0.3, "success": False}),
    ]
    observations = observations_from_rows(rows)
    assert observations.competence == (CompetenceObservation(predicted_probability=0.3, success=False),)


def test_replay_preserves_row_order() -> None:
    """Observations keep the (time) order of the input rows -- windows depend on it."""
    rows = [_row("PredictionOutcomeEvent", {"predicted_probability": p, "success": True}) for p in (0.1, 0.2, 0.3, 0.4)]
    observations = observations_from_rows(rows)
    assert [o.predicted_probability for o in observations.competence] == [0.1, 0.2, 0.3, 0.4]
