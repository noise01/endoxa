from pathlib import Path

from lark import Lark, Token, Transformer, v_args

from doxa.solver.api import And, Eq, Exists, ForAll, Implies, Not, Or
from doxa.solver.ast.context import FuncDecl, global_ctx
from doxa.solver.ast.expr import App, BoundVar, Const, Expr, Quantifier, Var
from doxa.solver.ast.sorts import BOOL_SORT, USort

U = USort("U")


@v_args(inline=True)
class FofTransformer(Transformer):
    def var_expr(self, name: Token) -> BoundVar:
        return global_ctx.mk_bound_var(str(name), U)

    def var_list(self, *names: Token) -> list[BoundVar]:
        return [global_ctx.mk_bound_var(str(v_name), U) for v_name in names]

    def term_list(self, *terms: Token) -> tuple[Token, ...]:
        return terms

    def const_term(self, functor: Token) -> tuple[str, tuple]:
        return (str(functor), ())

    def app_term(self, functor: Token, terms: Token) -> tuple[str, tuple]:
        return (str(functor), tuple(terms))

    def term_expr(self, term_tuple: tuple[str, tuple[Expr, ...]]) -> Expr:
        functor, args = term_tuple
        decl = FuncDecl(functor, tuple(arg.sort for arg in args), U)
        return global_ctx.mk_app(decl, *args)

    def pred_expr(self, term_tuple: tuple[str, tuple[Expr, ...]]) -> Expr:
        functor, args = term_tuple
        decl = FuncDecl(functor, tuple(arg.sort for arg in args), BOOL_SORT)
        return global_ctx.mk_app(decl, *args)

    def eq_expr(self, left: Expr, right: Expr) -> Expr:
        return Eq(left, right)

    def neq_expr(self, left: Expr, right: Expr) -> Expr:
        return Not(Eq(left, right))

    def not_expr(self, expr: Expr) -> Expr:
        return Not(expr)

    def and_expr(self, left: Expr, right: Expr) -> Expr:
        return And(left, right)

    def or_expr(self, left: Expr, right: Expr) -> Expr:
        return Or(left, right)

    def implies_expr(self, left: Expr, right: Expr) -> Expr:
        return Implies(left, right)

    def forall_expr(self, vars_list: list[BoundVar], body: Expr) -> Expr:
        return ForAll(vars_list, body)

    def exists_expr(self, vars_list: list[BoundVar], body: Expr) -> Expr:
        return Exists(vars_list, body)

    def fof_annotated(self, name: Token, role: Token, formula: Expr) -> tuple[str, str, Expr]:
        return (str(name), str(role), formula)


grammar_path = Path(__file__).parent.joinpath("tptp.lark")

parser = Lark(grammar_path.read_text(), parser="lalr", transformer=FofTransformer())


def parse_fof(input_str: str) -> tuple[str, str, Expr]:
    tree: tuple[str, str, Expr] = parser.parse(input_str)  # ty:ignore[invalid-assignment]
    return tree


def _app_to_tptp(expr: App) -> str:
    name = expr.decl.name
    if name == "And":
        return f"({to_tptp(expr.args[0])} & {to_tptp(expr.args[1])})"
    if name == "Or":
        lhs = expr.args[0]
        rhs = expr.args[1]
        if isinstance(lhs, App) and lhs.decl.name == "Not":
            return f"({to_tptp(lhs.args[0])} => {to_tptp(rhs)})"
        return f"({to_tptp(lhs)} | {to_tptp(rhs)})"
    if name == "Not":
        return f"~{to_tptp(expr.args[0])}"
    if name == "Implies":
        return f"({to_tptp(expr.args[0])} => {to_tptp(expr.args[1])})"
    if name == "Eq":
        return f"({to_tptp(expr.args[0])} = {to_tptp(expr.args[1])})"

    if not expr.args:
        return name
    args_str = ", ".join(to_tptp(arg) for arg in expr.args)
    return f"{name}({args_str})"


def to_tptp(expr: Expr) -> str:
    if isinstance(expr, Const):
        if isinstance(expr.value, bool):
            return "$true" if expr.value else "$false"
        return str(expr.value)

    if isinstance(expr, (Var, BoundVar)):
        return expr.name

    if isinstance(expr, App):
        return _app_to_tptp(expr)

    if isinstance(expr, Quantifier):
        quant = "!" if expr.is_forall else "?"
        vars_str = ", ".join(v.name for v in expr.bound_vars)
        return f"({quant} [{vars_str}] : {to_tptp(expr.body)})"

    return str(expr)
