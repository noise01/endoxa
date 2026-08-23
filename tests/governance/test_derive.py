"""Tests for deriving the ledger from persisted event rows.

The derivation is a pure function, so these run without a store, a DB or an
LLM. Beyond the mapping itself, three things are guarded:

- **The positive control** (criterion 4): ``hold``, ``supersede`` and
  ``ground`` are made to actually stand up from hand-built rows. Zero not moving
  is not a result, and these three are exactly the
  operations a run may go without ever performing.
- **The retract/supersede discriminator**: the two differ only in whether the
  write stated a confidence, which is the belief store's own test for whether a flip is
  counter-evidence (a host's belief store). Both shapes are fixed here.
- **Both row shapes** produce the same series: a JSON string payload with a
  ``datetime``, and a plain dict payload with an epoch float.
"""

import json
from datetime import UTC, datetime
from typing import Any

from endoxa.governance import SupportRef, derive_ledger
from endoxa.governance.derive import AXIOM_LOAD_CORRELATION_ID

_T0 = 1_700_000_000.0


def _derivation(antecedent_id: str) -> list[dict[str, str]]:
    """Build the belief store's support record for a forward-derived consequent."""
    return [{"kind": "derivation", "ref": antecedent_id}]


def _row(event_type: str, payload: dict[str, Any], *, at: float = _T0, event_id: str = "e1") -> dict[str, Any]:
    return {"id": event_id, "timestamp": at, "event_type": event_type, "payload": dict(payload)}


def _adapter_row(event_type: str, payload: dict[str, Any], *, at: float = _T0, event_id: str = "e1") -> dict[str, Any]:
    """Return a store shape that serialises: payload as JSON, timestamp as datetime."""
    row = _row(event_type, payload, at=at, event_id=event_id)
    row["payload"] = json.dumps(row["payload"])
    row["timestamp"] = datetime.fromtimestamp(at, tz=UTC)
    return row


def _atom(node_id: str, properties: dict[str, Any] | None, *, role: str = "user", grounding: bool = False):
    return {"node_id": node_id, "expr_obj": node_id, "properties": properties, "role": role, "ask_grounding": grounding}


def _ops(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(op.op, op.target) for op in derive_ledger(rows).ops]


class TestAtomOperations:
    def test_a_first_write_is_an_assert(self):
        ledger = derive_ledger([_row("AtomAddedEvent", _atom("mortal(socrates)", {"confidence": 0.9}))])
        (op,) = ledger.ops
        assert op.op == "assert"
        assert op.target == "mortal(socrates)"
        assert op.truth_value is True  # add_atom's own birth default
        assert op.confidence == 0.9
        assert op.actor == "user"

    def test_a_flip_without_a_stated_confidence_is_a_retract(self):
        # TMS revision writes the truth value alone and lets the beliefs
        # re-attribute the evidence; that silence is the retraction.
        rows = [
            _row("AtomAddedEvent", _atom("flammable(bridge)", {"truth_value": True, "confidence": 0.95})),
            _row("AtomAddedEvent", _atom("flammable(bridge)", {"truth_value": False}, role="agent"), event_id="e2"),
        ]
        assert _ops(rows) == [("assert", "flammable(bridge)"), ("retract", "flammable(bridge)")]

    def test_a_flip_that_restates_the_confidence_is_a_supersede(self):
        # Recency supersession says the world moved, not that the belief was
        # miscalibrated, and states the confidence to say so.
        rows = [
            _row("AtomAddedEvent", _atom("at(bob,home)", {"truth_value": True, "confidence": 0.9})),
            _row(
                "AtomAddedEvent",
                _atom("at(bob,home)", {"truth_value": False, "confidence": 0.9}, role="agent"),
                event_id="e2",
            ),
        ]
        ops = derive_ledger(rows).ops
        assert [op.op for op in ops] == ["assert", "supersede"]
        assert ops[1].truth_value is False
        assert ops[1].confidence == 0.9

    def test_an_ask_user_write_is_a_ground(self):
        rows = [
            _row("AtomAddedEvent", _atom("alive(felix)", {"truth_value": True, "confidence": 1.0})),
            _row(
                "AtomAddedEvent",
                _atom("alive(felix)", {"truth_value": False, "confidence": 1.0}, role="agent", grounding=True),
                event_id="e2",
            ),
        ]
        ops = derive_ledger(rows).ops
        assert [op.op for op in ops] == ["assert", "ground"]
        assert ops[1].confidence == 1.0

    def test_a_restatement_is_an_assert_not_a_flip(self):
        rows = [
            _row("AtomAddedEvent", _atom("mortal(socrates)", {"truth_value": True})),
            _row("AtomAddedEvent", _atom("mortal(socrates)", {"confidence": 0.8}), event_id="e2"),
        ]
        assert _ops(rows) == [("assert", "mortal(socrates)"), ("assert", "mortal(socrates)")]

    def test_a_write_without_a_node_id_yields_nothing(self):
        assert derive_ledger([_row("AtomAddedEvent", _atom("", None))]).ops == ()


class TestEvidenceOperations:
    def test_supporting_evidence_is_a_confirm(self):
        rows = [_row("BeliefEvidenceRecordedEvent", {"node_id": "mortal(socrates)", "supports": True})]
        (op,) = derive_ledger(rows).ops
        assert op.op == "confirm"
        # The event says only which way it points: the credence is the view's
        # replay of the Laplace fold, not something the operation states.
        assert op.confidence is None

    def test_counter_evidence_is_a_refute(self):
        rows = [_row("BeliefEvidenceRecordedEvent", {"node_id": "mortal(socrates)", "supports": False})]
        assert _ops(rows) == [("refute", "mortal(socrates)")]

    def test_a_booking_the_host_made_itself_is_the_same_operation(self):
        """The two evidence event types are one row type here.

        Which class the host published says whether the beliefs had already folded
        before recording -- a wiring detail of the host's own re-entrancy, not a
        governance distinction. A derivation that treated them differently would
        be reading the host's plumbing into the ledger.
        """
        published = [_row("BeliefEvidenceRecordedEvent", {"node_id": "p(x)", "supports": False})]
        booked = [_row("BeliefEvidenceBookedEvent", {"node_id": "p(x)", "supports": False})]
        assert _ops(published) == _ops(booked) == [("refute", "p(x)")]

    def test_the_reason_rides_on_the_operation(self):
        rows = [
            _row(
                "BeliefEvidenceBookedEvent",
                {"node_id": "animal(mike)", "supports": False, "reason": "support_lost"},
            ),
        ]
        (op,) = derive_ledger(rows).ops
        assert op.op == "refute"
        assert op.reason == "support_lost"

    def test_an_unrecognised_reason_is_dropped_not_carried(self):
        """Dropped rather than guessed, as an unknown support ``kind`` is.

        A log written by a host older than this set of names, or by a writer it has
        not caught up with, has to read as "no reason stated". Passing the word
        through would be worse than dropping it: a reader could not tell a reason
        the host meant from one that merely survived.
        """
        rows = [
            _row("BeliefEvidenceBookedEvent", {"node_id": "p(x)", "supports": True, "reason": "invented"}),
            _row("BeliefEvidenceBookedEvent", {"node_id": "q(x)", "supports": True}, event_id="e2"),
        ]
        assert [op.reason for op in derive_ledger(rows).ops] == [None, None]

    def test_an_operation_that_is_not_evidence_states_no_reason(self):
        rows = [
            _row("AtomAddedEvent", _atom("mortal(socrates)", {"truth_value": True})),
            _row("AtomAddedEvent", _atom("mortal(socrates)", {"truth_value": False}), event_id="e2"),
        ]
        assert all(op.reason is None for op in derive_ledger(rows).ops)


class TestHoldOperations:
    def test_a_detected_tie_is_one_hold_over_the_pair(self):
        rows = [
            _row(
                "ContradictionTieDetectedEvent",
                {"node_a": "alive(felix)", "truth_a": True, "node_b": "dead(felix)", "truth_b": True},
            ),
        ]
        (op,) = derive_ledger(rows).ops
        assert op.op == "hold"
        assert op.target == "alive(felix)"
        assert op.partner == "dead(felix)"

    def test_the_ask_event_is_not_a_ledger_operation(self):
        # Being unable to settle is the governance layer's judgement; deciding to
        # ask about it is the host's dialogue policy.
        rows = [_row("RevisionTieAskEvent", {"node_a": "alive(felix)", "node_b": "dead(felix)"})]
        assert derive_ledger(rows).ops == ()


class TestRuleOperations:
    def test_the_axiom_load_asserts_every_rule_it_carries(self):
        rows = [
            _row(
                "MemoryBatchGetResponseEvent",
                {
                    "correlation_id": AXIOM_LOAD_CORRELATION_ID,
                    "results": [
                        {"id": "mem_1", "confidence": 1.0, "source_kind": "seed"},
                        {"id": "mem_2", "confidence": 0.7, "source_kind": "consolidation"},
                    ],
                },
            ),
        ]
        ops = derive_ledger(rows).ops
        assert [(op.op, op.target, op.target_kind) for op in ops] == [
            ("assert", "mem_1", "rule"),
            ("assert", "mem_2", "rule"),
        ]
        assert ops[1].actor == "consolidation"

    def test_another_batch_get_response_is_not_the_rule_set(self):
        rows = [
            _row(
                "MemoryBatchGetResponseEvent",
                {"correlation_id": "some_recall", "results": [{"id": "mem_1", "confidence": 1.0}]},
            ),
        ]
        assert derive_ledger(rows).ops == ()

    def test_driving_a_rule_below_the_threshold_is_a_retract(self):
        payload = {"memory_type": "axiom", "updates": [{"id": "mem_2", "confidence": 0.0}]}
        ops = derive_ledger([_row("MemoryBatchUpdateRequestEvent", payload)]).ops
        assert [(op.op, op.target, op.target_kind) for op in ops] == [("retract", "mem_2", "rule")]

    def test_an_update_that_leaves_the_rule_active_is_a_restatement(self):
        payload = {"memory_type": "axiom", "updates": [{"id": "mem_2", "confidence": 0.8}]}
        assert _ops([_row("MemoryBatchUpdateRequestEvent", payload)]) == [("assert", "mem_2")]

    def test_a_non_axiom_update_is_not_a_rule_operation(self):
        payload = {"memory_type": "semantic", "updates": [{"id": "m", "confidence": 0.0}]}
        assert derive_ledger([_row("MemoryBatchUpdateRequestEvent", payload)]).ops == ()


class TestPositiveControl:
    """Hold, supersede and ground actually stand up."""

    def test_the_three_rare_operations_appear_in_one_series(self):
        rows = [
            _row("AtomAddedEvent", _atom("alive(felix)", {"truth_value": True, "confidence": 0.95}), at=_T0),
            _row(
                "AtomAddedEvent",
                _atom("dead(felix)", {"truth_value": True, "confidence": 0.95}),
                at=_T0 + 1,
                event_id="e2",
            ),
            _row(
                "ContradictionTieDetectedEvent",
                {"node_a": "alive(felix)", "node_b": "dead(felix)", "truth_a": True, "truth_b": True},
                at=_T0 + 2,
                event_id="e3",
            ),
            _row(
                "AtomAddedEvent",
                _atom("dead(felix)", {"truth_value": False, "confidence": 1.0}, role="agent", grounding=True),
                at=_T0 + 3,
                event_id="e4",
            ),
            _row(
                "AtomAddedEvent",
                _atom("at(felix,home)", {"truth_value": True, "confidence": 0.9}, role="observation"),
                at=_T0 + 4,
                event_id="e5",
            ),
            _row(
                "AtomAddedEvent",
                _atom("at(felix,home)", {"truth_value": False, "confidence": 0.9}, role="agent"),
                at=_T0 + 5,
                event_id="e6",
            ),
        ]
        performed = {op.op for op in derive_ledger(rows).ops}
        assert {"hold", "supersede", "ground"} <= performed


class TestTheSupportSeat:
    """What each operation was resting on, filled from the log."""

    def test_a_materialized_derivation_carries_its_antecedent(self):
        rows = [
            _row(
                "AtomAddedEvent",
                _atom("animal(mike)", {"truth_value": True, "supported_by": _derivation("cat(mike)")}, role="agent"),
            ),
        ]
        (op,) = derive_ledger(rows).ops
        assert op.supported_by == (SupportRef(kind="derivation", ref="cat(mike)"),)

    def test_a_belief_nobody_derived_carries_nothing(self):
        """The large majority of beliefs, and the class kept outside OUT."""
        (op,) = derive_ledger([_row("AtomAddedEvent", _atom("cat(mike)", {"truth_value": True}))]).ops
        assert op.supported_by == ()

    def test_a_second_support_is_added_by_its_own_event(self):
        """The row that makes a second footing exist anywhere at all."""
        rows = [
            _row(
                "AtomAddedEvent",
                _atom("animal(mike)", {"truth_value": True, "supported_by": _derivation("cat(mike)")}, role="agent"),
                event_id="e1",
            ),
            _row(
                "BeliefSupportRecordedEvent",
                {"node_id": "animal(mike)", "support": {"kind": "derivation", "ref": "dog(mike)"}},
                at=_T0 + 1,
                event_id="e2",
            ),
            _row(
                "BeliefEvidenceRecordedEvent",
                {"node_id": "animal(mike)", "supports": False},
                at=_T0 + 2,
                event_id="e3",
            ),
        ]
        ops = derive_ledger(rows).ops

        # The support row is state, not an operation: two rows in, two ops out.
        assert [op.op for op in ops] == ["assert", "refute"]
        assert ops[1].supported_by == (
            SupportRef(kind="derivation", ref="cat(mike)"),
            SupportRef(kind="derivation", ref="dog(mike)"),
        )

    def test_an_operation_before_the_support_arrived_stays_empty(self):
        """The stamp is what the belief rested on *at that moment*, not in the end."""
        rows = [
            _row("AtomAddedEvent", _atom("animal(mike)", {"truth_value": True}), event_id="e1"),
            _row(
                "BeliefEvidenceRecordedEvent",
                {"node_id": "animal(mike)", "supports": True},
                at=_T0 + 1,
                event_id="e2",
            ),
            _row(
                "BeliefSupportRecordedEvent",
                {"node_id": "animal(mike)", "support": {"kind": "derivation", "ref": "cat(mike)"}},
                at=_T0 + 2,
                event_id="e3",
            ),
            _row(
                "BeliefEvidenceRecordedEvent",
                {"node_id": "animal(mike)", "supports": False},
                at=_T0 + 3,
                event_id="e4",
            ),
        ]
        ops = derive_ledger(rows).ops

        assert ops[1].supported_by == ()
        assert ops[2].supported_by == (SupportRef(kind="derivation", ref="cat(mike)"),)

    def test_the_same_support_twice_is_one_footing(self):
        rows = [
            _row("AtomAddedEvent", _atom("animal(mike)", {"truth_value": True}), event_id="e1"),
            _row(
                "BeliefSupportRecordedEvent",
                {"node_id": "animal(mike)", "support": {"kind": "derivation", "ref": "cat(mike)"}},
                at=_T0 + 1,
                event_id="e2",
            ),
            _row(
                "BeliefSupportRecordedEvent",
                {"node_id": "animal(mike)", "support": {"kind": "derivation", "ref": "cat(mike)"}},
                at=_T0 + 2,
                event_id="e3",
            ),
            _row(
                "BeliefEvidenceRecordedEvent",
                {"node_id": "animal(mike)", "supports": False},
                at=_T0 + 3,
                event_id="e4",
            ),
        ]
        assert derive_ledger(rows).ops[1].supported_by == (SupportRef(kind="derivation", ref="cat(mike)"),)

    def test_a_re_derivation_replaces_what_was_written(self):
        """``add_atom`` overwrites the property, so the ledger must too."""
        rows = [
            _row(
                "AtomAddedEvent",
                _atom("animal(mike)", {"truth_value": True, "supported_by": _derivation("cat(mike)")}, role="agent"),
                event_id="e1",
            ),
            _row(
                "AtomAddedEvent",
                _atom("animal(mike)", {"truth_value": True, "supported_by": _derivation("mammal(mike)")}, role="agent"),
                at=_T0 + 1,
                event_id="e2",
            ),
        ]
        assert derive_ledger(rows).ops[1].supported_by == (SupportRef(kind="derivation", ref="mammal(mike)"),)

    def test_a_rule_support_keeps_its_kind(self):
        """The grounding write that records the rules a derivation could not do without."""
        rows = [
            _row(
                "AtomAddedEvent",
                _atom(
                    "flies(tweety)",
                    {"truth_value": True, "supported_by": [{"kind": "rule", "ref": "ax_1"}]},
                    role="observation",
                ),
            ),
        ]
        (op,) = derive_ledger(rows).ops
        assert op.supported_by == (SupportRef(kind="rule", ref="ax_1"),)

    def test_a_malformed_record_reads_as_no_support(self):
        """An audit log is not a place where raising is useful; an unknown kind is dropped."""
        rows = [
            _row(
                "AtomAddedEvent",
                _atom(
                    "animal(mike)",
                    {"truth_value": True, "supported_by": ["cat(mike)", {"kind": "wat", "ref": "x"}, {"ref": "y"}]},
                ),
            ),
        ]
        (op,) = derive_ledger(rows).ops
        assert op.supported_by == ()


class TestWhatTheDerivationCannotSee:
    def test_the_horizon_is_the_earliest_row(self):
        rows = [
            _row("AtomAddedEvent", _atom("a(x)", None), at=_T0 + 10, event_id="e2"),
            _row("AtomAddedEvent", _atom("b(x)", None), at=_T0, event_id="e1"),
        ]
        assert derive_ledger(rows).horizon == _T0

    def test_an_unreadable_payload_is_counted_not_dropped_silently(self):
        rows = [
            {"id": "e1", "timestamp": _T0, "event_type": "AtomAddedEvent", "payload": "{not json"},
            _row("AtomAddedEvent", _atom("a(x)", None), event_id="e2"),
        ]
        ledger = derive_ledger(rows)
        assert ledger.rows_read == 2
        assert ledger.rows_unreadable == 1
        assert len(ledger.ops) == 1

    def test_rows_are_read_in_time_order_not_input_order(self):
        rows = [
            _row("AtomAddedEvent", _atom("p(x)", {"truth_value": False}, role="agent"), at=_T0 + 1, event_id="e2"),
            _row("AtomAddedEvent", _atom("p(x)", {"truth_value": True, "confidence": 0.9}), at=_T0, event_id="e1"),
        ]
        assert _ops(rows) == [("assert", "p(x)"), ("retract", "p(x)")]


class TestRowShapes:
    def test_both_store_shapes_yield_the_same_series(self):
        payload = _atom("mortal(socrates)", {"truth_value": True, "confidence": 0.9})
        plain = derive_ledger([_row("AtomAddedEvent", payload)])
        adapter = derive_ledger([_adapter_row("AtomAddedEvent", payload)])
        assert plain.ops == adapter.ops
        assert plain.horizon == adapter.horizon
