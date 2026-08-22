"""Tests for reading a belief's footing off its supports.

The judgement is placed but not fired, so nothing in the running
system exercises it yet. That makes the positive control the whole of this
increment's evidence: a fold nobody calls is worth exactly what its tests show
it can distinguish (-- a 0 that never moves is not a result).

The distinction that matters is the last row of the table: ``out`` and
``indeterminate`` must not be the same answer. If they were, increment 3 would
turn a paged-out antecedent into counter-evidence against everything
that once rested on it, which is the false refutation this keeps at zero.
"""

import pytest

from endoxa.governance import (
    ABSENT,
    ALIVE,
    DEAD,
    IN,
    INDETERMINATE,
    OUT,
    UNSUPPORTED,
    SupportState,
    support_verdict,
)


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        # Nothing to lose: a user assertion, an observation, an innate axiom.
        ([], UNSUPPORTED),
        # One live footing is enough, wherever it sits in the record.
        ([ALIVE], IN),
        ([DEAD, ALIVE], IN),
        ([ALIVE, DEAD, ABSENT], IN),
        # Everything it rested on was refuted or retracted.
        ([DEAD], OUT),
        ([DEAD, DEAD], OUT),
        # Nothing alive, but what is missing left the beliefs rather than failed.
        ([ABSENT], INDETERMINATE),
        ([DEAD, ABSENT], INDETERMINATE),
        ([ABSENT, ABSENT], INDETERMINATE),
    ],
)
def test_the_fold_names_each_footing(states: list[SupportState], expected: str) -> None:
    assert support_verdict(states) == expected


def test_out_and_indeterminate_are_different_answers() -> None:
    """The point of the fourth state, stated on its own.

    Same number of supports, same absence of a live one; the only difference is
    whether the missing support failed or merely left. Increment 3 fires on one
    of these and must stay silent on the other.
    """
    assert support_verdict([DEAD, DEAD]) == OUT
    assert support_verdict([DEAD, ABSENT]) == INDETERMINATE
    assert support_verdict([DEAD, DEAD]) != support_verdict([DEAD, ABSENT])


def test_an_empty_record_is_not_a_loss() -> None:
    """``unsupported`` is not ``out`` -- 97.2% of atoms in vivo sit here."""
    assert support_verdict([]) == UNSUPPORTED
    assert support_verdict([]) != OUT


def test_the_order_of_the_supports_does_not_matter() -> None:
    """The record keeps derivation order; the verdict does not read it."""
    assert support_verdict([ALIVE, DEAD]) == support_verdict([DEAD, ALIVE])
    assert support_verdict([ABSENT, DEAD]) == support_verdict([DEAD, ABSENT])
