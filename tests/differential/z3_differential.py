"""Z3 differential oracle for the frozen homemade SMT solver (ADR-0058, ADR-0050).

Renders one backend-neutral :mod:`tests.differential.formula` AST into both the
homemade solver (``doxa.solver``) and Z3, checks satisfiability with
each, and compares the verdicts. On the quantifier-free propositional fragment both
solvers are complete, so the contract is strict: verdicts must both be decisive
(SAT/UNSAT) and equal. A homemade UNKNOWN is recorded as an *incompleteness*
(``agree=False``) rather than silently tolerated -- that too is a signal worth a red.

Only the SAT/UNSAT *verdict* is compared, never the satisfying model: distinct
solvers legitimately return different models for the same SAT formula.

This module discharges ADR-0050's commitment that the frozen solver's reliability
is guarded by a Z3 differential oracle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import z3

from doxa.solver import And, Bool, Implies, Not, Or, Solver
from tests.differential.formula import And as NAnd
from tests.differential.formula import Formula, format_formula
from tests.differential.formula import Implies as NImplies
from tests.differential.formula import Not as NNot
from tests.differential.formula import Or as NOr
from tests.differential.formula import Var as NVar

if TYPE_CHECKING:
    from doxa.solver import Expr

Verdict = Literal["SAT", "UNSAT", "UNKNOWN"]


def render_homemade(node: Formula) -> Expr:
    """Render a neutral formula AST into a homemade-solver expression."""
    match node:
        case NVar(name):
            return Bool(name)
        case NNot(child):
            return Not(render_homemade(child))
        case NImplies(left, right):
            return Implies(render_homemade(left), render_homemade(right))
        case NAnd(children):
            return And(*(render_homemade(c) for c in children))
        case NOr(children):
            return Or(*(render_homemade(c) for c in children))
    msg = f"Unknown formula node: {node!r}"
    raise TypeError(msg)


def render_z3(node: Formula) -> z3.BoolRef:
    """Render the same neutral formula AST into a Z3 expression."""
    match node:
        case NVar(name):
            return z3.Bool(name)
        case NNot(child):
            return z3.Not(render_z3(child))
        case NImplies(left, right):
            return z3.Implies(render_z3(left), render_z3(right))
        case NAnd(children):
            return z3.And(*(render_z3(c) for c in children))
        case NOr(children):
            return z3.Or(*(render_z3(c) for c in children))
    msg = f"Unknown formula node: {node!r}"
    raise TypeError(msg)


def _z3_verdict(node: Formula) -> Verdict:
    solver = z3.Solver()
    solver.add(render_z3(node))
    result = solver.check()
    if result == z3.sat:
        return "SAT"
    if result == z3.unsat:
        return "UNSAT"
    return "UNKNOWN"


def _homemade_verdict(node: Formula) -> Verdict:
    solver = Solver()
    solver.add(render_homemade(node))
    return solver.check()


@dataclass(frozen=True, slots=True)
class DifferentialResult:
    """Outcome of checking one formula against both solvers."""

    formula_repr: str
    homemade: Verdict
    z3: Verdict
    agree: bool


def differential_check(node: Formula) -> DifferentialResult:
    """Check ``node`` with both solvers and compare their SAT/UNSAT verdicts.

    ``agree`` is True only when both verdicts are decisive (SAT/UNSAT) and equal.
    A homemade UNKNOWN on this complete fragment counts as a disagreement.
    """
    homemade = _homemade_verdict(node)
    z3_result = _z3_verdict(node)
    agree = homemade == z3_result and homemade in ("SAT", "UNSAT")
    return DifferentialResult(
        formula_repr=format_formula(node),
        homemade=homemade,
        z3=z3_result,
        agree=agree,
    )
