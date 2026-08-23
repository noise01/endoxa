"""A congruence merge has to name the terms it rests on, and now says so.

The explanation walk reads those two terms back out of every edge it crosses.
When the edge came from congruence there is no literal to fall back on, so an
edge that carries neither is an edge the walk cannot explain.

It used to be representable. The edge type allowed ``None`` there, and the walk
defended itself with a guard that skipped such an edge -- without advancing to
the next one, so the guard was a non-terminating loop rather than a recovery.
Nothing ever built such an edge, which is why it was never found by running the
code. The contract is enforced at the write now, and the type says so.
"""

import pytest

from endoxa.errors import InternalError
from endoxa.solver import INT_SORT, Eq, Function, Int, Not, Solver
from endoxa.solver.sat.types import NULL_LITERAL
from endoxa.solver.theories.euf import EUFSolver


def test_a_congruence_merge_without_its_terms_is_refused():
    euf = EUFSolver()
    a, b = euf.register_term(Int("a")), euf.register_term(Int("b"))

    with pytest.raises(InternalError, match="must name the terms it rests on"):
        euf._merge(a, b, NULL_LITERAL)


def test_a_congruence_merge_that_names_them_is_accepted():
    euf = EUFSolver()
    a, b = euf.register_term(Int("a")), euf.register_term(Int("b"))

    euf._merge(a, b, NULL_LITERAL, eq_t1=a, eq_t2=b)

    assert euf.find(a) == euf.find(b)
    assert all(u is not None and v is not None for _, _, u, v in euf.parent_edge.values())


def test_congruence_still_closes_over_equal_arguments():
    """The path behind the refusal: ``f(a) = f(b)`` has to follow from ``a = b``.

    Nothing here supplies a literal for the congruence edge, so this is the case
    that reaches the enforced branch in ordinary use. Asserted as an entailment
    rather than as satisfiability -- SAT would also hold if congruence had
    stopped working altogether.
    """
    f = Function("f", INT_SORT, INT_SORT)
    a, b = Int("a"), Int("b")

    solver = Solver()
    solver.add(Eq(a, b))

    assert solver.check(Not(Eq(f(a), f(b)))) == "UNSAT"

    # And the control: without an equality to close over, the same query is open.
    # Otherwise UNSAT above would prove only that everything is UNSAT.
    assert solver.check(Not(Eq(f(a), f(Int("c"))))) == "SAT"
