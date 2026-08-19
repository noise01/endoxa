from doxa.solver import Bool, Eq, Implies, Int, Not, Solver


def test_solver_assumptions_basic():
    """検証1: 命題論理での Solver.check(*assumptions) および unsat_core() の基本動作検証。"""
    p = Bool("p")
    q = Bool("q")
    r = Bool("r")
    s = Bool("s")  # 無関係な仮定

    solver = Solver()

    # 恒常的なルール/公理を追加
    solver.add(Implies(p, q))
    solver.add(Implies(q, r))

    # アサンプション: p, ~r, および無関係な s を与える。
    # p => q => r だが、~r なので矛盾(UNSAT)。
    # 原因となったアサンプション [p, ~r] が不充足コアとして特定されるべき。
    res = solver.check(p, Not(r), s)
    assert res == "UNSAT"

    core = solver.unsat_core()
    core_strs = [str(expr) for expr in core]

    # p と ~r は原因なので core に含まれるはず
    assert "p" in core_strs
    assert "(Not r)" in core_strs
    # s は無関係なので含まれてはならない (TMS巻き添え防止の要)
    assert "s" not in core_strs


def test_solver_assumptions_euf():
    """検証2: EUF理論における assumptions と unsat_core() の検証。"""
    solver = Solver()

    a = Int("a")
    b = Int("b")
    c = Int("c")
    d = Int("d")  # 無関係

    # アサンプション: a == b, b == c, a != c, および無関係な c == d
    eq1 = Eq(a, b)
    eq2 = Eq(b, c)
    neq = Not(Eq(a, c))
    eq3 = Eq(c, d)

    res = solver.check(eq1, eq2, neq, eq3)
    assert res == "UNSAT"

    core = solver.unsat_core()
    core_strs = [str(expr) for expr in core]

    # 矛盾を引き起こす eq1, eq2, neq は core に含まれる
    assert str(eq1) in core_strs
    assert str(eq2) in core_strs
    assert str(neq) in core_strs
    # eq3 は無関係なので含まれてはならない
    assert str(eq3) not in core_strs
