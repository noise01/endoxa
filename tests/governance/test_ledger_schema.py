"""Tests for the ledger's operation schema.

The schema carries two promises beyond holding fields: an entry is never edited
after the fact (frozen), and the schema itself evolves by addition only. The
reserved columns are part of that promise, so they are
tested for being *present and empty* rather than ignored -- a seat that quietly
disappeared would break the increment that comes to sit in it.
"""

import dataclasses

import pytest

from doxa.governance import EVIDENCE_REASONS, LEDGER_OPS, LedgerOp, SupportRef


class TestOperationSet:
    def test_the_seven_operations_are_the_contract(self):
        assert LEDGER_OPS == ("assert", "retract", "supersede", "confirm", "refute", "hold", "ground")

    def test_confirm_and_refute_stay_separate_operations(self):
        # Folding them into one "record evidence"
        # operation with a polarity argument was considered and rejected, so a
        # reader never has to recover the polarity from an argument.
        assert "confirm" in LEDGER_OPS
        assert "refute" in LEDGER_OPS


class TestEntryIsAppendOnly:
    def test_an_entry_cannot_be_edited(self):
        op = LedgerOp(op="assert", target="mortal(socrates)")
        with pytest.raises(dataclasses.FrozenInstanceError):
            op.op = "retract"  # type: ignore[misc]

    def test_defaults_leave_the_reserved_seats_empty(self):
        op = LedgerOp(op="assert", target="mortal(socrates)")
        assert op.session_id is None
        assert op.supported_by == ()
        assert op.valid_at is None

    def test_reserved_seats_can_be_filled_without_touching_the_others(self):
        # The design constraint on a reservation: a later
        # increment fills a seat by *adding* to an entry, not by repurposing a
        # column that already means something.
        op = LedgerOp(
            op="assert",
            target="mortal(socrates)",
            supported_by=(SupportRef(kind="rule", ref="rule_7"),),
            valid_at=1_700_000_000.0,
        )
        assert op.supported_by == (SupportRef(kind="rule", ref="rule_7"),)
        assert op.valid_at == 1_700_000_000.0
        assert op.truth_value is None


class TestTheReasonColumn:
    """A column added the moment it was written.

    The other half of what the promise permits. ``supported_by`` was named in
    advance and filled later, which tested the reservation; ``reason`` was never
    reserved at all, which tests the promise the reservation was an instance of.
    Both are additions, and neither changes what an existing column means.
    """

    def test_the_seven_operations_did_not_change(self):
        # The reason is an *attribute* of confirm/refute, not an eighth operation:
        # The granularity is kept, and adding a column is the
        # only way this schema is allowed to grow.
        assert LEDGER_OPS == ("assert", "retract", "supersede", "confirm", "refute", "hold", "ground")

    def test_an_entry_states_no_reason_by_default(self):
        assert LedgerOp(op="assert", target="mortal(socrates)").reason is None

    def test_an_evidence_entry_carries_one_of_the_reasons(self):
        op = LedgerOp(op="refute", target="animal(mike)", reason="support_lost")
        assert op.reason in EVIDENCE_REASONS

    def test_the_reasons_have_no_duplicates(self):
        assert len(set(EVIDENCE_REASONS)) == len(EVIDENCE_REASONS)


class TestTheSupportSeat:
    """Sitting down in the seat the schema reserved."""

    def test_the_kind_is_carried_not_inferred(self):
        """Both endpoints are strings; only the kind says which beliefs to look on.

        A flat ``tuple[str, ...]`` -- the type the seat was originally declared
        with -- would have made a reader guess, and look up a memory id on the
        it up as though it were an atom. The same refusal applies to a host's own
        record and to the operations.
        """
        refs = (SupportRef(kind="derivation", ref="cat(mike)"), SupportRef(kind="rule", ref="ax_1"))

        assert [ref.ref for ref in refs if ref.kind == "derivation"] == ["cat(mike)"]
        assert [ref.ref for ref in refs if ref.kind == "rule"] == ["ax_1"]

    def test_a_reference_is_frozen_like_the_entry_holding_it(self):
        ref = SupportRef(kind="derivation", ref="cat(mike)")
        with pytest.raises(dataclasses.FrozenInstanceError):
            ref.ref = "dog(mike)"  # type: ignore[misc]

    def test_the_same_support_compares_equal(self):
        # Value equality is what lets the derivation drop a support it already
        # holds ("the same derivation running twice is one footing").
        assert SupportRef(kind="rule", ref="ax_1") == SupportRef(kind="rule", ref="ax_1")
        assert SupportRef(kind="rule", ref="ax_1") != SupportRef(kind="derivation", ref="ax_1")


class TestTargets:
    def test_a_belief_is_the_default_target_kind(self):
        assert LedgerOp(op="assert", target="mortal(socrates)").target_kind == "atom"

    def test_a_rule_is_named_by_its_memory_id(self):
        op = LedgerOp(op="retract", target="mem_42", target_kind="rule", confidence=0.0)
        assert op.target_kind == "rule"
        assert op.confidence == 0.0

    def test_a_hold_names_both_sides(self):
        op = LedgerOp(op="hold", target="alive(felix)", partner="dead(felix)")
        assert op.partner == "dead(felix)"
