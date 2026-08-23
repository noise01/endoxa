from typing import Any, TypedDict

from endoxa.solver.ast.expr import App, Expr
from endoxa.solver.sat.types import NULL_LITERAL, Clause, Lit, VarId

from .base import TheorySolver


class EUFStats(TypedDict):
    euf_merges: int
    euf_congruence_hits: int
    euf_conflicts: int


type TermId = int


def _edge_terms(
    t1: TermId,
    t2: TermId,
    reason_lit: Lit,
    eq_t1: TermId | None,
    eq_t2: TermId | None,
) -> tuple[TermId, TermId]:
    """Resolve the pair of terms the explanation walk reads back off an edge.

    An edge asserted by a literal rests on the two terms that literal equates. A
    congruence edge carries no literal, so the caller has to name them, and there
    is nothing to fall back on if it does not: the walk crosses every edge and
    explains it in terms of this pair.

    Refused rather than allowed through as ``None``. The walk cannot represent
    their absence -- the guard that used to stand in for that skipped the edge
    without advancing to the next one, which is a loop rather than a recovery --
    so the absence is stopped at the write, where it can still be attributed.
    """
    if reason_lit != NULL_LITERAL:
        return t1, t2
    if eq_t1 is None or eq_t2 is None:
        msg = "a congruence merge must name the terms it rests on"
        raise ValueError(msg)
    return eq_t1, eq_t2


class EUFSolver(TheorySolver):
    def __init__(self) -> None:
        self.var_to_eq: dict[VarId, tuple[TermId, TermId]] = {}
        self.expr_to_term: dict[Expr, TermId] = {}
        self.parent: list[TermId] = []
        self.size: list[int] = []
        self.parent_edge: dict[TermId, tuple[TermId, Lit, TermId, TermId]] = {}

        self.history: list[tuple[str, Any]] = []
        self.history_limits: list[int] = []
        self.disequalities: list[tuple[TermId, TermId, Lit]] = []

        # --- Congruence Closure ---
        self.term_to_app: dict[TermId, App] = {}
        self.use_list: list[list[TermId]] = []

        # --- Theory Propagation ---
        self.eq_to_lit: dict[tuple[TermId, TermId], Lit] = {}
        self.class_list: list[list[TermId]] = []
        self.pending_prop: list[Lit] = []

        self.stats: EUFStats = {"euf_merges": 0, "euf_congruence_hits": 0, "euf_conflicts": 0}

    def register_term(self, expr: Expr) -> TermId:
        if expr in self.expr_to_term:
            return self.expr_to_term[expr]

        term_id = len(self.parent)
        self.parent.append(term_id)
        self.size.append(1)
        self.use_list.append([])
        self.class_list.append([term_id])

        self.expr_to_term[expr] = term_id

        if isinstance(expr, App) and expr.decl.name not in ("And", "Or", "Not", "Eq", "Implies"):
            self.term_to_app[term_id] = expr
            for arg in expr.args:
                arg_term = self.register_term(arg)
                self.use_list[arg_term].append(term_id)

            for arg in expr.args:
                arg_term = self.expr_to_term[arg]
                root_arg = self.find(arg_term)
                for class_member in self.class_list[root_arg]:
                    for u in self.use_list[class_member]:
                        if u != term_id and self.find(u) != self.find(term_id) and self._are_congruent(u, term_id):
                            self._merge(u, term_id, NULL_LITERAL, eq_t1=u, eq_t2=term_id)

        return term_id

    def register_equality(self, eq_var: VarId, left: Expr, right: Expr) -> None:
        t1 = self.register_term(left)
        t2 = self.register_term(right)

        self.var_to_eq[eq_var] = (t1, t2)

        pos_lit = (eq_var << 1) | 0
        self.eq_to_lit[(t1, t2)] = pos_lit
        self.eq_to_lit[(t2, t1)] = pos_lit

    def find(self, t: TermId) -> TermId:
        while t != self.parent[t]:
            t = self.parent[t]
        return t

    def _are_congruent(self, t1: TermId, t2: TermId) -> bool:
        app1 = self.term_to_app.get(t1)
        app2 = self.term_to_app.get(t2)

        if not app1 or not app2 or app1.decl != app2.decl:
            return False

        for arg1, arg2 in zip(app1.args, app2.args, strict=True):
            if self.find(self.expr_to_term[arg1]) != self.find(self.expr_to_term[arg2]):
                return False

        return True

    def _merge(
        self,
        t1: TermId,
        t2: TermId,
        reason_lit: Lit,
        eq_t1: TermId | None = None,
        eq_t2: TermId | None = None,
    ) -> None:
        root1 = self.find(t1)
        root2 = self.find(t2)
        if root1 == root2:
            return

        if self.size[root1] < self.size[root2]:
            root1, root2 = root2, root1
            t1, t2 = t2, t1
            eq_t1, eq_t2 = eq_t2, eq_t1

        self.history.append(
            ("MERGE", (root1, root2, self.size[root1], self.use_list[root1].copy(), self.class_list[root1].copy())),
        )

        self.parent[root2] = root1
        self.size[root1] += self.size[root2]

        u, v = _edge_terms(t1, t2, reason_lit, eq_t1, eq_t2)
        self.parent_edge[root2] = (root1, reason_lit, u, v)

        old_use_list = self.use_list[root2]
        old_class_list = self.class_list[root2]

        for u_term in self.class_list[root1]:
            for v_term in old_class_list:
                lit = self.eq_to_lit.get((u_term, v_term))
                if lit is not None:
                    self.pending_prop.append(lit)

        self.class_list[root1].extend(old_class_list)
        self.use_list[root1].extend(old_use_list)

        for u1 in old_use_list:
            for u2 in self.use_list[root1]:
                if self.find(u1) != self.find(u2) and self._are_congruent(u1, u2):
                    self._merge(u1, u2, NULL_LITERAL, eq_t1=u1, eq_t2=u2)

    def assert_literal(self, lit: Lit) -> tuple[bool, list[Lit]]:
        self.pending_prop.clear()

        var = lit >> 1
        sign = lit & 1

        if var not in self.var_to_eq:
            return True, self.pending_prop.copy()

        t1, t2 = self.var_to_eq[var]

        if sign == 0:
            self._merge(t1, t2, lit)
        else:
            self.disequalities.append((t1, t2, lit))
            self.history.append(("DISEQ", None))

            if self.find(t1) == self.find(t2):
                return False, []

        return True, self.pending_prop.copy()

    def _explain_edge(self, curr: TermId, nxt: TermId, lit: Lit, u: TermId, v: TermId) -> list[Lit]:
        reasons = []

        reasons.extend(self._explain_equality(curr, v))
        if lit != NULL_LITERAL:
            reasons.append(lit)
        else:
            app1 = self.term_to_app[u]
            app2 = self.term_to_app[v]
            for arg1, arg2 in zip(app1.args, app2.args, strict=True):
                reasons.extend(self._explain_equality(self.expr_to_term[arg1], self.expr_to_term[arg2]))

        reasons.extend(self._explain_equality(u, nxt))
        return reasons

    def _explain_equality(self, t1: TermId, t2: TermId) -> list[Lit]:
        if t1 == t2:
            return []

        reasons: list[Lit] = []
        path1: dict[TermId, tuple[TermId, Lit, TermId, TermId]] = {}

        curr = t1
        while curr in self.parent_edge:
            nxt, lit, u, v = self.parent_edge[curr]
            path1[curr] = (nxt, lit, u, v)
            curr = nxt

        curr = t2
        edges2 = []
        while curr not in path1 and curr in self.parent_edge:
            nxt, lit, u, v = self.parent_edge[curr]
            edges2.append((curr, nxt, lit, u, v))
            curr = nxt

        lca = curr

        curr = t1
        while curr != lca:
            nxt, lit, u, v = path1[curr]
            reasons.extend(self._explain_edge(curr, nxt, lit, u, v))
            curr = nxt

        for curr_v, nxt_v, lit_v, u_v, v_v in reversed(edges2):
            reasons.extend(self._explain_edge(curr_v, nxt_v, lit_v, u_v, v_v))

        return reasons

    def explain_propagation(self, p_lit: Lit) -> Clause:
        var = p_lit >> 1
        t1, t2 = self.var_to_eq[var]

        eq_reasons = self._explain_equality(t1, t2)

        lits = [p_lit] + [(r ^ 1) for r in eq_reasons]
        return Clause(lits, is_learned=True)

    def check(self) -> list[Clause]:
        for t1, t2, diseq_lit in self.disequalities:
            if self.find(t1) == self.find(t2):
                eq_reasons = self._explain_equality(t1, t2)
                self.stats["euf_conflicts"] += 1

                lits = [(r ^ 1) for r in eq_reasons]
                lits.append(diseq_lit ^ 1)

                return [Clause(lits, is_learned=True)]

        return []

    def push(self) -> None:
        self.history_limits.append(len(self.history))
        self.history.append(("LIMIT", None))

    def pop(self, num_levels: int) -> None:
        if num_levels == 0 or not self.history_limits:
            return

        target_limit = self.history_limits[-num_levels]

        while len(self.history) > target_limit:
            op, data = self.history.pop()
            match op:
                case "MERGE":
                    root_x, root_y, old_size_x, old_use_list_x, old_class_list_x = data
                    self.parent[root_y] = root_y
                    self.size[root_x] = old_size_x
                    self.use_list[root_x] = old_use_list_x
                    self.class_list[root_x] = old_class_list_x
                    del self.parent_edge[root_y]
                case "DISEQ":
                    self.disequalities.pop()

        del self.history_limits[-num_levels:]
