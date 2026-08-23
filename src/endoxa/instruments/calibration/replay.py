"""Persisted event rows to ordered calibration observation streams.

Turns the raw dicts a host's event log returns -- an event type plus a JSON
payload string -- into the minimal observation types
:mod:`endoxa.instruments.calibration.windowed` consumes. This is the read side of
the offline windowed recomputation: it runs nothing, it only re-reads what was
already recorded. Reading the rows out of storage is the host's job; this turns
them into observations.

The three event types it recognises are the ones a live calibration instrument
would subscribe to. An observation the live side would skip -- a resolved
prediction with no predicted probability, a resolved question with no outcome --
is skipped here too, so a recomputed curve matches the live accounting rather
than quietly exceeding it.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from endoxa.instruments.calibration.windowed import (
    AskObservation,
    CompetenceObservation,
    KnowledgeObservation,
)

PREDICTION_OUTCOME_EVENT = "PredictionOutcomeEvent"
KNOWLEDGE_SIGNAL_EVENT = "KnowledgeCalibrationSignalEvent"
QUESTION_RESOLVED_EVENT = "QuestionResolvedEvent"

#: The event types the offline recomputation needs from the persisted log.
CALIBRATION_EVENT_TYPES = frozenset(
    {PREDICTION_OUTCOME_EVENT, KNOWLEDGE_SIGNAL_EVENT, QUESTION_RESOLVED_EVENT},
)


@dataclass(slots=True, frozen=True)
class ReplayedObservations:
    """The 3 calibration observation streams recovered from the event log.

    Each stream is in the stream (time) order of the input rows.

    Attributes:
        competence: Resolved predictions carrying a ``predicted_probability``.
        knowledge: Epistemic-status transitions.
        ask: Resolved ask-user questions carrying an ``outcome``.
    """

    competence: tuple[CompetenceObservation, ...]
    knowledge: tuple[KnowledgeObservation, ...]
    ask: tuple[AskObservation, ...]


def observations_from_rows(rows: Sequence[dict[str, Any]]) -> ReplayedObservations:
    """Parse time-ordered stored-event rows into calibration observation streams.

    Args:
        rows: Stored-event dicts (each with ``event_type`` and a JSON ``payload``
            string), already in ascending timestamp order -- the order a host's
            event store hands them back in. Rows whose payload cannot be parsed,
            or whose calibration field is absent, are skipped.

    Returns:
        The 3 observation streams for windowed recomputation.
    """
    competence: list[CompetenceObservation] = []
    knowledge: list[KnowledgeObservation] = []
    ask: list[AskObservation] = []

    for row in rows:
        event_type = row.get("event_type")
        try:
            payload = json.loads(row["payload"])
        except KeyError, TypeError, json.JSONDecodeError:
            continue

        if event_type == PREDICTION_OUTCOME_EVENT:
            probability = payload.get("predicted_probability")
            if probability is None:
                continue
            competence.append(
                CompetenceObservation(
                    predicted_probability=float(probability),
                    success=bool(payload.get("success", False)),
                ),
            )
        elif event_type == KNOWLEDGE_SIGNAL_EVENT:
            status = payload.get("status")
            if status is None:
                continue
            knowledge.append(
                KnowledgeObservation(
                    target=str(payload.get("target", "")),
                    previous_status=payload.get("previous_status"),
                    status=str(status),
                ),
            )
        elif event_type == QUESTION_RESOLVED_EVENT:
            outcome = payload.get("outcome")
            if outcome is None:
                continue
            ask.append(AskObservation(outcome=outcome))

    return ReplayedObservations(
        competence=tuple(competence),
        knowledge=tuple(knowledge),
        ask=tuple(ask),
    )
