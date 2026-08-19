import re
from typing import TYPE_CHECKING

from doxa.solver import BOOL_SORT, FuncDecl, USort, global_ctx

if TYPE_CHECKING:
    from doxa.solver import Expr

# Single uninterpreted sort shared by all ground terms in the belief base.
U = USort("U")


def parse_fact_to_expr(fact_str: str) -> Expr:
    """Parse a ground-fact string into an SMT solver Expr object.

    For example, ``human(socrates)`` -> ``FuncDecl("human", (U,), BOOL_SORT)(FuncDecl("socrates", (), U)())``.

    Args:
        fact_str: The fact string to parse.

    Returns:
        The SMT Expr object.
    """
    fact_str = fact_str.strip()
    match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\((.*)\)$", fact_str)
    if match:
        pred_name = match.group(1)
        args_str = match.group(2)
        args = [arg.strip() for arg in args_str.split(",") if arg.strip()]

        arg_exprs = []
        for arg in args:
            arg_decl = FuncDecl(arg, (), U)
            arg_expr = global_ctx.mk_app(arg_decl)
            arg_exprs.append(arg_expr)

        pred_decl = FuncDecl(pred_name, tuple(U for _ in arg_exprs), BOOL_SORT)
        return global_ctx.mk_app(pred_decl, *arg_exprs)

    prop_decl = FuncDecl(fact_str, (), BOOL_SORT)
    return global_ctx.mk_app(prop_decl)
