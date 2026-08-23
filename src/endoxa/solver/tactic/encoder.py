from typing import TypedDict

from endoxa.solver.ast.expr import App, Const, Expr, Quantifier, Var
from endoxa.solver.ast.sorts import BoolSort
from endoxa.solver.sat.types import Lit, VarId


class EncoderStats(TypedDict):
    num_vars: int
    num_clauses: int


class TseitinEncoder:
    def __init__(self, start_var: VarId = 0) -> None:
        self.clauses: list[list[Lit]] = []
        self.expr_to_var: dict[Expr, VarId] = {}
        self.var_to_expr: list[Expr] = []
        self.next_var = start_var

        self.stats: EncoderStats = {"num_vars": 0, "num_clauses": 0}

    def run(self, formula: Expr) -> tuple[int, list[list[Lit]]]:
        num_vars, _, _ = self.run_incremental(formula)
        return num_vars, self.clauses

    def run_incremental(self, formula: Expr, *, is_assumption: bool = False) -> tuple[int, list[list[Lit]], Lit]:
        old_clause_count = len(self.clauses)
        root_lit = self._encode(formula)
        if not is_assumption:
            self.clauses.append([root_lit])
        num_vars = self.next_var

        self.stats["num_vars"] = num_vars
        self.stats["num_clauses"] = len(self.clauses)

        return num_vars, self.clauses[old_clause_count:], root_lit

    def _encode(self, root_expr: Expr) -> Lit:  # noqa: C901, PLR0912, PLR0915
        stack: list[tuple[Expr, bool]] = [(root_expr, False)]

        def get_lit(e: Expr) -> Lit:
            invert_count = 0
            while isinstance(e, App) and e.decl.name == "Not":
                invert_count += 1
                e = e.args[0]
            base_lit = (self.expr_to_var[e] << 1) | 0
            return base_lit ^ (invert_count % 2)

        while stack:
            expr, children_processed = stack.pop()

            if expr in self.expr_to_var:
                continue

            if isinstance(expr, App) and expr.decl.name == "Not":
                arg = expr.args[0]
                if arg not in self.expr_to_var:
                    stack.append((arg, False))
                continue

            if not children_processed:
                stack.append((expr, True))

                if isinstance(expr, App) and expr.decl.name in ("And", "Or"):
                    stack.extend((arg, False) for arg in expr.args if arg not in self.expr_to_var)
            else:
                if expr in self.expr_to_var:
                    continue

                var = self.next_var
                self.next_var += 1
                self.expr_to_var[expr] = var
                self.var_to_expr.append(expr)

                pos_lit = (var << 1) | 0
                neg_lit = (var << 1) | 1

                match expr:
                    case Var():
                        pass
                    case Const(value=True):
                        self.clauses.append([pos_lit])
                    case Const(value=False):
                        self.clauses.append([neg_lit])
                    case App(decl, args):
                        if decl.name == "And":
                            arg_lits = [get_lit(arg) for arg in args]
                            for x_i in arg_lits:
                                self.clauses.append([neg_lit, x_i])
                            clause = [x ^ 1 for x in arg_lits] + [pos_lit]
                            self.clauses.append(clause)
                        elif decl.name == "Or":
                            arg_lits = [get_lit(arg) for arg in args]
                            clause = [neg_lit, *arg_lits]
                            self.clauses.append(clause)
                            for x_i in arg_lits:
                                self.clauses.append([x_i ^ 1, pos_lit])
                        elif not isinstance(expr.sort, BoolSort):
                            msg = f"Cannot encode unknown AST node: {expr}"
                            raise ValueError(msg)
                    case Quantifier():
                        pass
                    case _:
                        msg = f"Cannot encode unknown AST node: {expr}"
                        raise ValueError(msg)

        return get_lit(root_expr)
