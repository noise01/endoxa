"""Random propositional-formula generator for the Z3 differential oracle.

Produces a *backend-neutral* AST (the small frozen node types below) so a single
generated structure can be rendered into both the frozen doxa solver
(``doxa.solver``) and Z3 by ``tests.differential.z3_differential``. That
double-render is the crux of differential testing: the two solvers see the same
formula and must agree on SAT/UNSAT.

The fragment is deliberately restricted to quantifier-free propositional logic
(boolean variables under And/Or/Not/Implies). Both the doxa CDCL SAT core and
Z3 are *complete* on this fragment, so any SAT/UNSAT disagreement is a genuine
solver bug rather than an incompleteness artefact (reliability guard).

This module is pure and framework-free: it depends only on ``random`` and does not
import z3, hypothesis, or the host. hypothesis strategies that wrap it live in the
evals test modules, keeping the generator reusable by the tests/ CI smoke.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import random


@dataclass(frozen=True, slots=True)
class Var:
    """A boolean variable (propositional atom)."""

    name: str


@dataclass(frozen=True, slots=True)
class Not:
    child: Formula


@dataclass(frozen=True, slots=True)
class And:
    children: tuple[Formula, ...]


@dataclass(frozen=True, slots=True)
class Or:
    children: tuple[Formula, ...]


@dataclass(frozen=True, slots=True)
class Implies:
    left: Formula
    right: Formula


Formula = Var | Not | And | Or | Implies

# Compact infix rendering, used for stable counterexample reprs when a
# differential disagreement is reported (shrinking surfaces a minimal formula).
_CONNECTIVE = {And: " & ", Or: " | "}


def format_formula(node: Formula) -> str:
    """Render a formula to a compact parenthesised infix string (for diagnostics)."""
    match node:
        case Var(name):
            return name
        case Not(child):
            return f"~{format_formula(child)}"
        case Implies(left, right):
            return f"({format_formula(left)} -> {format_formula(right)})"
        case And(children) | Or(children):
            joiner = _CONNECTIVE[type(node)]
            return "(" + joiner.join(format_formula(c) for c in children) + ")"
    msg = f"Unknown formula node: {node!r}"
    raise TypeError(msg)


def generate_formula(
    rng: random.Random,
    *,
    num_atoms: int = 4,
    max_depth: int = 4,
    leaf_probability: float = 0.3,
    max_arity: int = 3,
) -> Formula:
    """Generate one random propositional formula over ``num_atoms`` variables.

    Deterministic in ``rng``: the same ``random.Random(seed)`` yields the same
    formula, so batches are reproducible. A small atom count with moderate depth
    reliably produces a healthy mix of SAT and UNSAT instances -- the property the
    differential oracle exercises.
    """
    if num_atoms < 1:
        msg = "num_atoms must be >= 1"
        raise ValueError(msg)
    atoms = [f"p{i}" for i in range(num_atoms)]

    def rec(depth: int) -> Formula:
        if depth <= 0 or rng.random() < leaf_probability:
            return Var(rng.choice(atoms))
        kind = rng.choice(("not", "and", "or", "implies"))
        if kind == "not":
            return Not(rec(depth - 1))
        if kind == "implies":
            return Implies(rec(depth - 1), rec(depth - 1))
        arity = rng.randint(2, max_arity)
        children = tuple(rec(depth - 1) for _ in range(arity))
        return And(children) if kind == "and" else Or(children)

    # Force the root to be a connective so single-variable formulas (trivially
    # SAT, low signal) are rare rather than ~leaf_probability of the batch.
    root = rec(max_depth)
    if isinstance(root, Var):
        return Not(root) if rng.random() < 0.5 else And((root, rec(max_depth - 1)))
    return root
