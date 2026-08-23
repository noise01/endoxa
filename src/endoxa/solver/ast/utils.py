from .context import global_ctx
from .expr import App, BoundVar, Expr, Quantifier


def substitute(expr: Expr, theta: dict[BoundVar, Expr], cache: dict[Expr, Expr] | None = None) -> Expr:  # noqa: C901
    if not theta:
        return expr

    if cache is None:
        cache = {}

    if expr in cache:
        return cache[expr]

    result = expr
    match expr:
        case BoundVar():
            result = theta.get(expr, expr)
        case App(decl, args):
            new_args = [substitute(arg, theta, cache) for arg in args]
            if not all(old is new for old, new in zip(args, new_args, strict=True)):
                result = global_ctx.mk_app(decl, *new_args)
        case Quantifier(is_forall, bound_vars, body, patterns):
            new_theta = {v: val for v, val in theta.items() if v not in bound_vars}

            if new_theta:
                new_cache: dict[Expr, Expr] = {}
                new_body = substitute(body, new_theta, new_cache)

                new_patterns: list[Expr] = []
                for pattern in patterns:
                    new_exprs = tuple(substitute(e, new_theta, new_cache) for e in pattern.exprs)
                    new_patterns.append(global_ctx.mk_pattern(*new_exprs))

                # Compared as a tuple against a tuple. A list is never equal to a
                # tuple however its contents match, so comparing the two directly
                # made this condition unconditionally true and rebuilt every
                # quantifier the walk touched, substitution or none.
                if new_body is not body or tuple(new_patterns) != patterns:
                    result = global_ctx.mk_quantifier(
                        is_forall=is_forall,
                        bound_vars=bound_vars,
                        body=new_body,
                        patterns=tuple(new_patterns),
                    )
        case _:
            pass

    cache[expr] = result
    return result
