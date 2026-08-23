"""Random propositional-formula generator for the Z3 differential oracle.

Produces a *backend-neutral* AST (the small frozen node types below) so a single
generated structure can be rendered into both the frozen endoxa solver
(``endoxa.solver``) and Z3 by ``tests.differential.z3_differential``. That
double-render is the crux of differential testing: the two solvers see the same
formula and must agree on SAT/UNSAT.

Two fragments, both quantifier-free, and both chosen because *both solvers are
complete on them* -- so a SAT/UNSAT disagreement is a genuine bug rather than an
incompleteness artefact:

- **propositional**: boolean variables under And/Or/Not/Implies, decided by the
  CDCL core.
- **equality with uninterpreted functions**: constants and function applications
  over one uninterpreted sort, compared with ``=``, decided by the congruence
  closure underneath. Nothing in it constrains a term to a value, so the two
  solvers are being asked the same question about equality alone.

Quantifiers are deliberately outside both. Instantiation here is *anytime* and
answers UNKNOWN when its budget runs out, which is a correct answer and not one a
verdict comparison can score -- that fragment needs a different kind of test, not
this one.

This module is pure and framework-free: it depends only on ``random`` and imports
neither z3 nor hypothesis. The strategies that wrap it live beside the tests that
use them, which is what lets the same generator feed both a seeded batch and a
property sweep.
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


@dataclass(frozen=True, slots=True)
class Atom:
    """A constant of the uninterpreted sort -- a term, not a proposition."""

    name: str


@dataclass(frozen=True, slots=True)
class Apply:
    """An uninterpreted function applied to terms."""

    fn: str
    args: tuple[Term, ...]


@dataclass(frozen=True, slots=True)
class Equal:
    """Two terms asserted equal. The only predicate over terms in this fragment."""

    left: Term
    right: Term


Term = Atom | Apply
Formula = Var | Not | And | Or | Implies | Equal

# Compact infix rendering, used for stable counterexample reprs when a
# differential disagreement is reported (shrinking surfaces a minimal formula).
_CONNECTIVE = {And: " & ", Or: " | "}


def format_term(node: Term) -> str:
    """Render a term for diagnostics."""
    match node:
        case Atom(name):
            return name
        case Apply(fn, args):
            return f"{fn}({', '.join(format_term(a) for a in args)})"
    msg = f"Unknown term node: {node!r}"
    raise TypeError(msg)


def format_formula(node: Formula) -> str:
    """Render a formula to a compact parenthesised infix string (for diagnostics)."""
    match node:
        case Var(name):
            return name
        case Equal(left, right):
            return f"({format_term(left)} = {format_term(right)})"
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


#: A term stops descending, or a trap picks its congruence form, on a coin flip.
#: Named so the two uses read as the same decision rather than as a magic number.
_LEAF_ODDS = 0.5

#: An equality needs two things to be about.
_MIN_CONSTANTS = 2


@dataclass(frozen=True, slots=True)
class EufShape:
    """The knobs on :func:`generate_euf_formula`, bundled so it takes two arguments.

    Attributes:
        num_constants: How many distinct constants a formula may name. Few, on
            purpose: what makes an EUF instance hard is how often distinct-looking
            terms are forced equal, and that comes from a small vocabulary rather
            than from deep nesting.
        num_functions: How many uninterpreted function names, each usable at
            either arity.
        max_depth: Depth of the propositional structure above the equalities.
        max_term_depth: Depth of the terms inside them.
        trap_probability: How often a subformula is a :func:`_congruence_trap`
            instead of a random equality. What keeps a batch from being one
            verdict throughout.
    """

    num_constants: int = 4
    num_functions: int = 2
    max_depth: int = 3
    max_term_depth: int = 2
    trap_probability: float = 0.35


def _random_term(rng: random.Random, shape: EufShape, depth: int) -> Term:
    """Build one term: a constant, or a function over shallower terms."""
    constants = [Atom(f"c{i}") for i in range(shape.num_constants)]
    functions = [f"f{i}" for i in range(shape.num_functions)]
    if depth <= 0 or not functions or rng.random() < _LEAF_ODDS:
        return rng.choice(constants)
    arity = rng.randint(1, 2)
    return Apply(rng.choice(functions), tuple(_random_term(rng, shape, depth - 1) for _ in range(arity)))


def _congruence_trap(rng: random.Random, shape: EufShape) -> Formula:
    """Build a pair of conjuncts that cannot both hold, if the theory is working.

    Random equalities over random terms are almost always satisfiable -- 98% of a
    batch, measured -- so a generator without this exercises the easy half of the
    solver and calls it coverage. The two shapes built here need congruence and
    transitivity respectively.

    Not unsatisfiable by construction: what the surrounding tree does with the
    pair decides that. Under a conjunction it contradicts; under a disjunction the
    other side can rescue it.
    """
    t1, t2, t3 = (_random_term(rng, shape, 1) for _ in range(3))
    if shape.num_functions and rng.random() < _LEAF_ODDS:
        fn = rng.choice([f"f{i}" for i in range(shape.num_functions)])
        return And((Equal(t1, t2), Not(Equal(Apply(fn, (t1,)), Apply(fn, (t2,))))))
    return And((Equal(t1, t2), Equal(t2, t3), Not(Equal(t1, t3))))


def generate_euf_formula(rng: random.Random, shape: EufShape | None = None) -> Formula:
    """Generate one random quantifier-free EUF formula.

    Deterministic in ``rng``, like :func:`generate_formula`.
    """
    shape = shape or EufShape()
    if shape.num_constants < _MIN_CONSTANTS:
        msg = "num_constants must be >= 2"
        raise ValueError(msg)

    def rec(depth: int) -> Formula:
        if depth <= 0:
            return _equality(rng, shape)
        if rng.random() < shape.trap_probability:
            return _congruence_trap(rng, shape)
        kind = rng.choice(("equal", "not", "and", "or", "implies"))
        if kind == "equal":
            return _equality(rng, shape)
        if kind == "not":
            return Not(rec(depth - 1))
        if kind == "implies":
            return Implies(rec(depth - 1), rec(depth - 1))
        children = (rec(depth - 1), rec(depth - 1))
        return And(children) if kind == "and" else Or(children)

    return rec(shape.max_depth)


def _equality(rng: random.Random, shape: EufShape) -> Formula:
    """Two independently drawn terms, asserted equal."""
    return Equal(
        _random_term(rng, shape, shape.max_term_depth),
        _random_term(rng, shape, shape.max_term_depth),
    )
