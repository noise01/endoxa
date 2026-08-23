"""Writing a formula out produces text this package can read back.

``parse_fof`` and ``to_tptp`` are exported side by side, and nothing was checking
that they agree. Coverage put the number on it: with the grammar moved to its own
module, what remained of ``tptp.py`` -- the write-out half, all of it public --
measured 16%, because no test called it at all.

The property asserted here is that parse, write, and parse again lands on the
same expression object. Hash-consing makes that an identity check: two structurally
identical formulas are one object, so ``is`` compares meaning, not spelling.
"""

import pytest

from endoxa.solver import INT_SORT, Bool, BoolVal, Function, Int, Not, Or, parse_fof, to_tptp

#: One per construction the writer handles. The surface forms differ from what
#: comes back -- the writer parenthesises and spaces to its own taste -- which is
#: why the check is on the expression and not on the string.
FORMULAS = [
    "p",
    "socrates",
    "human(socrates)",
    "likes(alice, bob)",
    "~p",
    "(p & q)",
    "(p | q)",
    "(p => q)",
    "(a = b)",
    "(a != b)",
    "![X] : (human(X) => mortal(X))",
    "?[Y] : cat(Y)",
    "![X] : ?[Y] : loves(X, Y)",
    "((p & q) | ~r)",
    "$true",
    "$false",
]


def _parse(formula: str):
    return parse_fof(f"fof(r, axiom, {formula}).")[2]


@pytest.mark.parametrize("formula", FORMULAS)
def test_written_out_it_reads_back_the_same(formula):
    once = _parse(formula)
    written = to_tptp(once)
    assert _parse(written) is once, f"{formula!r} wrote as {written!r}, which is a different formula"


def test_the_check_can_fail():
    """The control: two different formulas must not compare equal under it."""
    assert _parse("(p & q)") is not _parse("(p | q)")


class TestTheBooleanConstants:
    """``to_tptp`` has always written ``$true``; the grammar has only just learnt it."""

    def test_they_survive_a_round_trip(self):
        for value in (True, False):
            written = to_tptp(BoolVal(val=value))
            assert written == ("$true" if value else "$false")
            assert _parse(written) is BoolVal(val=value)

    def test_a_formula_carrying_one_is_readable(self):
        """The case that used to produce text this package's own parser refused."""
        assert _parse(to_tptp(_parse("(p | $false)"))) is _parse("(p | $false)")


class TestWhatTheWriterDoesNotSpecialCase:
    def test_a_predicate_named_implies_stays_a_predicate(self):
        """``Implies`` desugars, so a declaration of that name is only ever a caller's own.

        Writing it as an arrow would turn someone's two-argument predicate into a
        connective. The writer has no branch for it, and this is what says so.
        """
        implies = Function("implies", INT_SORT, INT_SORT, INT_SORT)
        written = to_tptp(implies(Int("a"), Int("b")))
        assert written == "implies(a, b)"
        assert "=>" not in written

    def test_implies_itself_is_written_as_an_arrow(self):
        """Built through the API it is an ``Or`` over a ``Not``, and comes back as ``=>``."""
        assert to_tptp(Or(Not(Bool("p")), Bool("q"))) == "(p => q)"
