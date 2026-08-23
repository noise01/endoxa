from endoxa.solver.ast.context import global_ctx
from endoxa.solver.ast.expr import App, BoundVar, Const, Expr, Quantifier
from endoxa.solver.ast.utils import substitute
from endoxa.solver.theories.euf import EUFSolver


def _contains_bound(e: Expr, bound_vars: set[BoundVar]) -> bool:
    if isinstance(e, BoundVar) and e in bound_vars:
        return True
    if isinstance(e, App):
        return any(_contains_bound(a, bound_vars) for a in e.args)
    return False


def _collect_pattern_candidates(expr: Expr, bound_vars: set[BoundVar], candidates: set[Expr]) -> None:
    if isinstance(expr, App):
        if expr.decl.name not in ("And", "Or", "Not", "Eq", "Implies") and any(
            _contains_bound(arg, bound_vars) for arg in expr.args
        ):
            candidates.add(expr)
        for arg in expr.args:
            _collect_pattern_candidates(arg, bound_vars, candidates)
    elif isinstance(expr, Quantifier):
        _collect_pattern_candidates(expr.body, bound_vars, candidates)


class EMatcher:
    """Quantifier instantiation by E-matching, bounded in both depth and work.

    ``max_depth`` bounds how *deep* an instantiated term may get; it does not
    bound how *many* candidate bindings the search examines. The two are
    independent: a flat set of chained unary rules over many constants generates
    shallow terms in enormous quantity, and enumerating their bindings is
    quadratic in the term count per pattern argument.

    :meth:`match` therefore also takes a work budget. Without it a single call can
    run unbounded, and a budget counted in rounds does not save you: the round cap
    is only tested *between* match calls (``engine.check``), so one round is free
    to blow up inside itself. The work budget makes the anytime guarantee hold at
    the granularity where the blow-up actually happens.
    """

    def __init__(self, euf: EUFSolver, max_depth: int = 5) -> None:
        self.euf = euf
        self.rules: list[Quantifier] = []
        self.instantiated: set[tuple[Quantifier, tuple[Expr, ...]]] = set()

        self.max_depth = max_depth
        self.term_depth: dict[Expr, int] = {}

        # Work budget for the current match() call. ``None`` means unbounded,
        # which keeps the counters off the hot path entirely.
        self._budget: int | None = None
        # Whether the last match() call stopped early on a spent budget. The
        # caller needs this: instantiation had not converged, so a "no model
        # found" verdict is undetermined rather than SAT (engine.check).
        self.truncated = False
        # Candidate bindings examined by the last match() call (0 when unbounded).
        self.matches_used = 0

    def set_term_depth(self, term: Expr, depth: int) -> None:
        if term not in self.term_depth:
            self.term_depth[term] = depth

    def get_term_depth(self, term: Expr) -> int:
        return self.term_depth.get(term, 0)

    def add_rule(self, rule: Quantifier) -> None:
        if rule.is_forall:
            if not rule.patterns:
                candidates: set[Expr] = set()
                _collect_pattern_candidates(rule.body, set(rule.bound_vars), candidates)
                if candidates:
                    pats = [global_ctx.mk_pattern(cand) for cand in candidates]
                    object.__setattr__(rule, "patterns", tuple(pats))
            self.rules.append(rule)

    def _spend(self) -> bool:
        """Consume one unit of match work; False once the budget is spent.

        Every candidate binding the search *considers* costs a unit, not every
        instance it produces: the pathological case enumerates for a long time
        while producing nothing, so counting instances would not bound it.
        """
        if self._budget is None:
            return True
        if self._budget <= 0:
            self.truncated = True
            return False
        self._budget -= 1
        self.matches_used += 1
        return True

    def match(self, *, max_matches: int | None = None) -> list[tuple[Expr, int]]:
        """Return the instances a round of E-matching yields.

        Args:
            max_matches: Upper bound on candidate bindings examined. ``None``
                (the default) leaves the search unbounded and byte-identical to
                the original behaviour. When the bound is hit the search stops
                and returns the instances found *so far* -- a partial result,
                flagged by :attr:`truncated`, never an exception.
        """
        self._budget = max_matches
        self.truncated = False
        self.matches_used = 0
        new_instances: list[tuple[Expr, int]] = []

        for rule in self.rules:
            if self.truncated:
                break
            if not rule.patterns:
                continue

            for pattern in rule.patterns:
                if self.truncated:
                    break
                thetas = self._match_multi_pattern(pattern.exprs, 0, {})

                for theta in thetas:
                    instance = self._instantiate(rule, theta)
                    if instance is not None:
                        new_instances.append(instance)

        return new_instances

    def _instantiate(self, rule: Quantifier, theta: dict[BoundVar, Expr]) -> tuple[Expr, int] | None:
        """Build the instance a binding yields, or None if it is skipped.

        Skipped when the resulting term would exceed ``max_depth``, when the
        binding does not cover every bound variable, or when this exact instance
        was already produced.
        """
        max_theta_depth = 0
        for val in theta.values():
            d = self.get_term_depth(val)
            max_theta_depth = max(max_theta_depth, d)

        new_depth = max_theta_depth + 1
        if new_depth > self.max_depth:
            return None

        try:
            inst_key = (rule, tuple(theta[v] for v in rule.bound_vars))
        except KeyError:
            return None

        if inst_key in self.instantiated:
            return None
        self.instantiated.add(inst_key)

        return substitute(rule.body, theta), new_depth

    def _match_multi_pattern(
        self,
        exprs: tuple[Expr, ...],
        idx: int,
        theta: dict[BoundVar, Expr],
    ) -> list[dict[BoundVar, Expr]]:
        if idx == len(exprs):
            return [theta]

        pat_expr = exprs[idx]
        results: list[dict[BoundVar, Expr]] = []

        if not isinstance(pat_expr, App):
            return []

        for app in self.euf.term_to_app.values():
            if not self._spend():
                break
            if app.decl == pat_expr.decl:
                curr_thetas = [theta]
                for p_arg, t_arg in zip(pat_expr.args, app.args, strict=True):
                    next_thetas: list[dict[BoundVar, Expr]] = []
                    for th in curr_thetas:
                        next_thetas.extend(self._match_arg(p_arg, t_arg, th))
                    curr_thetas = next_thetas
                    if not curr_thetas:
                        break

                for th_next in curr_thetas:
                    results.extend(self._match_multi_pattern(exprs, idx + 1, th_next))

        return results

    def _match_arg(self, pattern: Expr, target: Expr, theta: dict[BoundVar, Expr]) -> list[dict[BoundVar, Expr]]:  # noqa: C901, PLR0912
        match pattern:
            case BoundVar():
                if pattern in theta:
                    t1 = self.euf.expr_to_term.get(theta[pattern])
                    t2 = self.euf.expr_to_term.get(target)
                    if t1 is not None and t2 is not None and self.euf.find(t1) == self.euf.find(t2):
                        return [theta]
                else:
                    new_theta = theta.copy()
                    new_theta[pattern] = target
                    return [new_theta]
            case App():
                results = []
                target_id = self.euf.expr_to_term.get(target)
                if target_id is None:
                    return []

                target_root = self.euf.find(target_id)

                for t_id, app in self.euf.term_to_app.items():
                    if not self._spend():
                        break
                    if app.decl == pattern.decl and self.euf.find(t_id) == target_root:
                        curr_thetas = [theta]
                        for p_arg, t_arg in zip(pattern.args, app.args, strict=True):
                            next_thetas: list[dict[BoundVar, Expr]] = []
                            for th in curr_thetas:
                                next_thetas.extend(self._match_arg(p_arg, t_arg, th))
                            curr_thetas = next_thetas
                            if not curr_thetas:
                                break
                        results.extend(curr_thetas)
                return results
            case Const() if isinstance(target, Const):
                if pattern.value == target.value:
                    return [theta]
                return []

        return []
