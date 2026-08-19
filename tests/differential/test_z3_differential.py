"""Property-based Z3 differential test for the solver.

hypothesis generates thousands of random propositional formulas; each is rendered
into both this package's solver and Z3, and their verdicts must agree. When a
disagreement is found, hypothesis shrinks it to a minimal counterexample -- which is
why this exists alongside the fixed seeded batch next door rather than replacing it.
A shrunk formula is a bug report; a random one is a puzzle.
"""

import random

import hypothesis.strategies as st
from hypothesis import given, settings

from tests.differential.formula import And as NAnd
from tests.differential.formula import Implies as NImplies
from tests.differential.formula import Not as NNot
from tests.differential.formula import Or as NOr
from tests.differential.formula import Var as NVar
from tests.differential.formula import generate_formula
from tests.differential.z3_differential import differential_check

_ATOM_NAMES = st.sampled_from([f"p{i}" for i in range(4)])


def _formulas() -> st.SearchStrategy:
    return st.recursive(
        st.builds(NVar, _ATOM_NAMES),
        lambda children: st.one_of(
            st.builds(NNot, children),
            st.builds(NImplies, children, children),
            st.builds(lambda a, b: NAnd((a, b)), children, children),
            st.builds(lambda a, b: NOr((a, b)), children, children),
        ),
        max_leaves=25,
    )


@given(_formulas())
@settings(max_examples=1500, deadline=None)
def test_doxa_solver_agrees_with_z3(formula) -> None:
    """The frozen doxa solver must return the same SAT/UNSAT verdict as Z3."""
    result = differential_check(formula)
    assert result.agree, f"solver disagreement: doxa={result.doxa} z3={result.z3} on {result.formula_repr}"


def test_generator_produces_both_verdicts() -> None:
    """Guard against a degenerate generator.

    A seeded batch must contain both SAT and UNSAT instances, else the agreement
    property above would be vacuously easy.
    """
    rng = random.Random(20260720)
    verdicts = {differential_check(generate_formula(rng)).doxa for _ in range(500)}
    assert "SAT" in verdicts, "generator produced no satisfiable formulas"
    assert "UNSAT" in verdicts, "generator produced no unsatisfiable formulas"
