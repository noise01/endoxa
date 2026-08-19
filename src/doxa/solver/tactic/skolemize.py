from doxa.solver.ast.context import AND_DECL, NOT_DECL, OR_DECL, global_ctx
from doxa.solver.ast.expr import App, BoundVar, Expr, FuncDecl, Quantifier
from doxa.solver.ast.utils import substitute


class Skolemizer:
    def __init__(self) -> None:
        self.skolem_counter = 0

    def run(self, formula: Expr) -> Expr:  # noqa: C901, PLR0912, PLR0915
        stack: list[tuple[Expr, bool, list[BoundVar], bool]] = [(formula, True, [], False)]
        ret_stack: list[Expr] = []

        while stack:
            expr, polarity, univ_vars, processed = stack.pop()

            if not processed:
                match expr:
                    case App(decl, args):
                        match decl.name:
                            case "Not":
                                stack.append((args[0], not polarity, univ_vars, False))
                            case "And" | "Or":
                                stack.append((expr, polarity, univ_vars, True))
                                stack.extend((arg, polarity, univ_vars, False) for arg in args)
                            case "Implies":
                                p, q = args
                                stack.append((expr, polarity, univ_vars, True))
                                if polarity:
                                    stack.append((p, False, univ_vars, False))
                                    stack.append((q, True, univ_vars, False))
                                else:
                                    stack.append((p, True, univ_vars, False))
                                    stack.append((q, False, univ_vars, False))
                            case _:
                                ret_stack.append(expr if polarity else global_ctx.mk_app(NOT_DECL, expr))

                    case Quantifier(is_forall, bound_vars, body, _):
                        is_effective_forall = is_forall if polarity else not is_forall
                        if is_effective_forall:
                            new_univ = univ_vars + list(bound_vars)
                            stack.append((expr, polarity, univ_vars, True))
                            stack.append((body, polarity, new_univ, False))
                        else:
                            theta: dict[BoundVar, Expr] = {}
                            for v in bound_vars:
                                self.skolem_counter += 1
                                sk_name = f"sk_{self.skolem_counter}_{v.name}"
                                if not univ_vars:
                                    sk_decl = FuncDecl(sk_name, (), v.sort)
                                    sk_term = global_ctx.mk_app(sk_decl)
                                else:
                                    arg_sorts = tuple(uv.sort for uv in univ_vars)
                                    sk_decl = FuncDecl(sk_name, arg_sorts, v.sort)
                                    sk_term = global_ctx.mk_app(sk_decl, *univ_vars)
                                theta[v] = sk_term

                            sk_body = substitute(body, theta)
                            stack.append((sk_body, True, univ_vars, False))

                    case _:
                        ret_stack.append(expr if polarity else global_ctx.mk_app(NOT_DECL, expr))

            else:
                match expr:
                    case App(decl, args):
                        if decl.name == "And":
                            new_args = [ret_stack.pop() for _ in args]
                            ret_stack.append(
                                global_ctx.mk_app(AND_DECL, *new_args)
                                if polarity
                                else global_ctx.mk_app(OR_DECL, *new_args),
                            )
                        elif decl.name == "Or":
                            new_args = [ret_stack.pop() for _ in args]
                            ret_stack.append(
                                global_ctx.mk_app(OR_DECL, *new_args)
                                if polarity
                                else global_ctx.mk_app(AND_DECL, *new_args),
                            )
                        elif decl.name == "Implies":
                            new_p = ret_stack.pop()
                            new_q = ret_stack.pop()
                            if polarity:
                                ret_stack.append(global_ctx.mk_app(OR_DECL, new_p, new_q))
                            else:
                                ret_stack.append(global_ctx.mk_app(AND_DECL, new_p, new_q))

                    case Quantifier():
                        new_body = ret_stack.pop()
                        ret_stack.append(
                            global_ctx.mk_quantifier(
                                is_forall=True,
                                bound_vars=expr.bound_vars,
                                body=new_body,
                                patterns=expr.patterns,
                            ),
                        )

        return ret_stack[0]
