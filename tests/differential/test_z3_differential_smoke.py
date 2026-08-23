"""A fast, deterministic Z3 differential guard.

The solver is frozen, so what it needs is not new capability but evidence that it
has not drifted. The generative sweep next door explores broadly; this fixed-seed
batch runs the same generator and oracle through a plain seeded loop, so a
regression surfaces as the same failing formulas every time rather than as a fresh
random one each run.

The batch also asserts that it produced both verdicts. A differential guard that
happened to generate only satisfiable formulas would agree with anything.
"""

import random

import pytest

pytest.importorskip("z3", reason="z3-solver is a dev dependency; the differential oracle needs it")

from tests.differential.formula import generate_formula
from tests.differential.z3_differential import differential_check

_SMOKE_SEED = 20260720
_SMOKE_COUNT = 60


def test_the_solver_agrees_with_z3_on_seeded_batch() -> None:
    """A fixed seeded batch of propositional formulas must agree between solvers."""
    rng = random.Random(_SMOKE_SEED)
    verdicts: set[str] = set()
    disagreements = []
    for _ in range(_SMOKE_COUNT):
        result = differential_check(generate_formula(rng))
        verdicts.add(result.endoxa)
        if not result.agree:
            disagreements.append(f"endoxa={result.endoxa} z3={result.z3} on {result.formula_repr}")

    assert not disagreements, "solver differential disagreement(s):\n" + "\n".join(disagreements)
    # Sanity: the seeded batch must exercise both verdicts, else the guard is vacuous.
    assert {"SAT", "UNSAT"} <= verdicts, f"seeded smoke batch did not cover both verdicts: {verdicts}"
