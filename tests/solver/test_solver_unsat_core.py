"""An unsat core must name the assumptions that caused the conflict, and only those."""

from doxa.solver import Bool, Eq, Implies, Int, Not, Solver


def test_solver_assumptions_basic():
    """Assumption-based checking and unsat cores over propositional logic."""
    p = Bool("p")
    q = Bool("q")
    r = Bool("r")
    s = Bool("s")  # unrelated to the conflict

    solver = Solver()

    # Standing rules.
    solver.add(Implies(p, q))
    solver.add(Implies(q, r))

    # Assume p, ~r, and the unrelated s. p => q => r, so ~r contradicts, and the
    # core should name exactly the assumptions responsible: [p, ~r].
    res = solver.check(p, Not(r), s)
    assert res == "UNSAT"

    core = solver.unsat_core()
    core_strs = [str(expr) for expr in core]

    assert "p" in core_strs
    assert "(Not r)" in core_strs
    # An unrelated assumption must stay out. This is what keeps belief revision
    # from retracting a bystander.
    assert "s" not in core_strs


def test_solver_assumptions_euf():
    """The same, under the equality theory."""
    solver = Solver()

    a = Int("a")
    b = Int("b")
    c = Int("c")
    d = Int("d")  # unrelated to the conflict

    eq1 = Eq(a, b)
    eq2 = Eq(b, c)
    neq = Not(Eq(a, c))
    eq3 = Eq(c, d)

    res = solver.check(eq1, eq2, neq, eq3)
    assert res == "UNSAT"

    core = solver.unsat_core()
    core_strs = [str(expr) for expr in core]

    # The three that force the contradiction are named.
    assert str(eq1) in core_strs
    assert str(eq2) in core_strs
    assert str(neq) in core_strs
    # The unrelated equality is not.
    assert str(eq3) not in core_strs
