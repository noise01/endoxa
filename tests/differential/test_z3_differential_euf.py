"""The same differential, over equality and uninterpreted functions.

The propositional sweep next door exercises the CDCL core. It says nothing about
the congruence closure underneath it, which is most of what makes this an SMT
solver rather than a SAT solver -- and which the README's summary of "asserted
differentially against Z3" was quietly taken to cover.

Same contract as the propositional fragment, for the same reason: both solvers
are complete on quantifier-free EUF, so a disagreement is a bug and an UNKNOWN
from this side is an incompleteness worth failing on.

Quantifiers stay outside. Instantiation here is anytime and answers UNKNOWN when
its budget runs out -- a correct answer, and not one a verdict comparison can
score.
"""

import random

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

pytest.importorskip("z3", reason="z3-solver is a dev dependency; the differential oracle needs it")

from tests.differential.formula import And as NAnd
from tests.differential.formula import Apply as NApply
from tests.differential.formula import Atom as NAtom
from tests.differential.formula import Equal as NEqual
from tests.differential.formula import Not as NNot
from tests.differential.formula import Or as NOr
from tests.differential.formula import generate_euf_formula
from tests.differential.z3_differential import differential_check

_SEED = 20260823
_BATCH = 200

_CONSTANTS = st.sampled_from([NAtom(f"c{i}") for i in range(4)])
_FUNCTIONS = st.sampled_from(["f0", "f1"])


def _terms() -> st.SearchStrategy:
    """Constants, and functions over them. Shallow: depth buys little here.

    What makes an EUF instance hard is how often distinct-looking terms are forced
    equal, and that comes from reusing a small vocabulary rather than from nesting.
    """
    return st.recursive(
        _CONSTANTS,
        lambda children: st.builds(
            lambda fn, args: NApply(fn, tuple(args)),
            _FUNCTIONS,
            st.lists(children, min_size=1, max_size=2),
        ),
        max_leaves=6,
    )


def _formulas() -> st.SearchStrategy:
    equalities = st.builds(NEqual, _terms(), _terms())
    return st.recursive(
        equalities,
        lambda children: st.one_of(
            st.builds(NNot, children),
            st.builds(lambda a, b: NAnd((a, b)), children, children),
            st.builds(lambda a, b: NOr((a, b)), children, children),
        ),
        max_leaves=12,
    )


@given(_formulas())
@settings(max_examples=600, deadline=None)
def test_the_solver_agrees_with_z3_on_equality(formula) -> None:
    result = differential_check(formula)
    assert result.agree, f"solver disagreement: endoxa={result.endoxa} z3={result.z3} on {result.formula_repr}"


def test_the_solver_agrees_with_z3_on_a_seeded_euf_batch() -> None:
    """A fixed batch, so a regression is the same formulas every run, not a fresh one."""
    rng = random.Random(_SEED)
    verdicts: set[str] = set()
    disagreements = []
    for _ in range(_BATCH):
        result = differential_check(generate_euf_formula(rng))
        verdicts.add(result.endoxa)
        if not result.agree:
            disagreements.append(f"endoxa={result.endoxa} z3={result.z3} on {result.formula_repr}")

    assert not disagreements, "EUF differential disagreement(s):\n" + "\n".join(disagreements)
    assert {"SAT", "UNSAT"} <= verdicts, f"the seeded batch covered only {verdicts}"


def test_the_batch_is_not_lopsided() -> None:
    """The guard the propositional side needs, sharpened.

    "Both verdicts appeared" is satisfied by 299 SAT and one UNSAT, which is what
    a generator of random equalities actually produces -- equality is easy to
    satisfy, and the congruence closure only has to work on the other side. This
    asserts the batch spends a real share of its time there.
    """
    rng = random.Random(_SEED)
    verdicts = [differential_check(generate_euf_formula(rng)).endoxa for _ in range(_BATCH)]
    unsat = verdicts.count("UNSAT")
    assert _BATCH * 0.2 <= unsat <= _BATCH * 0.8, f"{unsat}/{_BATCH} unsatisfiable, which is not a mix"


class TestTheOracleWouldNotice:
    """Controls: the comparison has to be able to fail, on each side."""

    def test_congruence_is_what_decides_the_hard_case(self) -> None:
        """``a = b`` with ``f(a) != f(b)`` is UNSAT only if congruence closes."""
        a, b = NAtom("c0"), NAtom("c1")
        trap = NAnd((NEqual(a, b), NNot(NEqual(NApply("f0", (a,)), NApply("f0", (b,))))))
        result = differential_check(trap)
        assert result.endoxa == "UNSAT"
        assert result.agree

    def test_the_same_shape_without_the_equality_is_satisfiable(self) -> None:
        """Otherwise the check above would pass on a solver that answers UNSAT always."""
        a, b = NAtom("c0"), NAtom("c1")
        loose = NNot(NEqual(NApply("f0", (a,)), NApply("f0", (b,))))
        result = differential_check(loose)
        assert result.endoxa == "SAT"
        assert result.agree

    def test_a_name_reused_at_two_arities_stays_two_functions(self) -> None:
        """Both solvers keep them apart, and the harness has to render them that way.

        If one side merged ``f0/1`` and ``f0/2`` the disagreement would be the
        harness's rather than the solver's, and it would look like a real bug.
        """
        a = NAtom("c0")
        mixed = NEqual(NApply("f0", (a,)), NApply("f0", (a, a)))
        result = differential_check(mixed)
        assert result.endoxa == "SAT", "a unary and a binary f0 were treated as one function"
        assert result.agree
