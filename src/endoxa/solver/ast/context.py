import weakref
from typing import Any, cast

from .expr import App, BoundVar, Const, Expr, FuncDecl, Pattern, Quantifier, Var
from .sorts import BOOL_SORT, Sort

AND_DECL = FuncDecl("And", (BOOL_SORT,), BOOL_SORT)
OR_DECL = FuncDecl("Or", (BOOL_SORT,), BOOL_SORT)
NOT_DECL = FuncDecl("Not", (BOOL_SORT,), BOOL_SORT)


class Context:
    def __init__(self) -> None:
        self._pool: weakref.WeakValueDictionary[tuple[type[Expr], Any], Expr] = weakref.WeakValueDictionary()

    def _mk_cached(self, cls: type[Expr], *args: Any) -> Expr:  # noqa: ANN401
        # Recursively convert any list inside args to a tuple to ensure the key is hashable
        def to_tuple(x: Any) -> Any:  # noqa: ANN401
            if isinstance(x, list):
                return tuple(to_tuple(y) for y in x)
            return x

        safe_args = tuple(to_tuple(x) for x in args)
        key = (cls, safe_args)
        if key in self._pool:
            return self._pool[key]

        instance = cls(*safe_args)
        self._pool[key] = instance
        return instance

    def mk_var(self, name: str, sort: Sort) -> Expr:
        return self._mk_cached(Var, name, sort)

    def mk_const(self, value: Any, sort: Sort) -> Expr:  # noqa: ANN401
        return self._mk_cached(Const, value, sort)

    def mk_true(self) -> Expr:
        return self.mk_const(value=True, sort=BOOL_SORT)

    def mk_false(self) -> Expr:
        return self.mk_const(value=False, sort=BOOL_SORT)

    def mk_app(self, decl: FuncDecl, *args: Expr) -> Expr:  # noqa: C901, PLR0912
        if decl.name in ("And", "Or"):
            args = tuple(
                child
                for arg in args
                for child in (arg.args if isinstance(arg, App) and arg.decl.name == decl.name else (arg,))
            )

        match decl.name:
            case "Not":
                match args:
                    case (Const(value=True),):
                        return self.mk_false()
                    case (Const(value=False),):
                        return self.mk_true()
                    case (App(d, (a,)),) if d.name == "Not":
                        return a
            case "And":
                if any(isinstance(a, Const) and a.value is False for a in args):
                    return self.mk_false()

                valid_args = (a for a in args if not (isinstance(a, Const) and a.value is True))
                simplified_args = list(dict.fromkeys(valid_args))
                if not simplified_args:
                    return self.mk_true()
                if len(simplified_args) == 1:
                    return simplified_args[0]

                args = tuple(simplified_args)
            case "Or":
                if any(isinstance(a, Const) and a.value is True for a in args):
                    return self.mk_true()

                valid_args = (a for a in args if not (isinstance(a, Const) and a.value is False))
                simplified_args = list(dict.fromkeys(valid_args))
                if not simplified_args:
                    return self.mk_false()
                if len(simplified_args) == 1:
                    return simplified_args[0]

                args = tuple(simplified_args)

        return self._mk_cached(App, decl, args)

    def mk_bound_var(self, name: str, sort: Sort) -> BoundVar:
        # The hash-cons cache is generic over Expr subclasses and says so. This
        # call fixes the class, so the narrower type is a fact about the argument
        # rather than a hope, and stating it here spares every caller from
        # restating it less truthfully.
        return cast("BoundVar", self._mk_cached(BoundVar, name, sort))

    def mk_pattern(self, *exprs: Expr) -> Expr:
        return self._mk_cached(Pattern, tuple(exprs))

    def mk_quantifier(
        self,
        *,
        is_forall: bool,
        bound_vars: tuple[Expr, ...],
        body: Expr,
        patterns: tuple[Expr, ...] = (),
    ) -> Expr:
        return self._mk_cached(Quantifier, is_forall, bound_vars, body, patterns)


global_ctx = Context()
