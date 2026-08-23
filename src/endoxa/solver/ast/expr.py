from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from endoxa.errors import ArityMismatchError, SortMismatchError

from .sorts import BOOL_SORT, Sort


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Expr(ABC):
    @property
    @abstractmethod
    def sort(self) -> Sort: ...

    @property
    def children(self) -> tuple[Expr, ...]:
        if isinstance(self, App):
            return self.args
        if isinstance(self, Quantifier):
            return (self.body,)
        return ()

    def __and__(self, other: Expr) -> Expr:
        from .context import AND_DECL, global_ctx  # noqa: PLC0415

        return global_ctx.mk_app(AND_DECL, self, other)

    def __or__(self, other: Expr) -> Expr:
        from .context import OR_DECL, global_ctx  # noqa: PLC0415

        return global_ctx.mk_app(OR_DECL, self, other)

    def __invert__(self) -> Expr:
        from .context import NOT_DECL, global_ctx  # noqa: PLC0415

        return global_ctx.mk_app(NOT_DECL, self)


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Var(Expr):
    name: str
    _sort: Sort

    @property
    def sort(self) -> Sort:
        return self._sort

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Const(Expr):
    value: Any
    _sort: Sort

    @property
    def sort(self) -> Sort:
        return self._sort

    def __str__(self) -> str:
        if isinstance(self.value, bool):
            return "true" if self.value else "false"
        return str(self.value)


@dataclass(frozen=True, slots=True)
class FuncDecl:
    name: str
    domain: tuple[Sort, ...]
    range_: Sort

    def __call__(self, *args: Expr) -> Expr:
        from .context import global_ctx  # noqa: PLC0415

        return global_ctx.mk_app(self, *args)


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class App(Expr):
    decl: FuncDecl
    args: tuple[Expr, ...]

    @property
    def sort(self) -> Sort:
        return self.decl.range_

    def __post_init__(self) -> None:
        if self.decl.name in ("And", "Or"):
            sort = self.decl.domain[0]
            for i, arg in enumerate(self.args):
                if arg.sort != sort:
                    msg = f"Type mismatch in argument {i} of N-ary '{self.decl.name}': expected {sort}, got {arg.sort}"
                    raise SortMismatchError(msg)
        else:
            if len(self.args) != len(self.decl.domain):
                msg = f"Arity mismatch for '{self.decl.name}': expected {len(self.decl.domain)}, got {len(self.args)}"
                raise ArityMismatchError(msg)
            for i, (arg, sort) in enumerate(zip(self.args, self.decl.domain, strict=True)):
                if arg.sort != sort:
                    msg = f"Type mismatch in argument {i} of '{self.decl.name}': expected {sort}, got {arg.sort}"
                    raise SortMismatchError(msg)

    def __str__(self) -> str:
        if not self.args:
            return self.decl.name

        args_str = ", ".join(str(arg) for arg in self.args)
        return f"({self.decl.name} {args_str})"


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class BoundVar(Expr):
    name: str
    sort: Sort

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Pattern(Expr):
    exprs: tuple[Expr, ...]

    @property
    def sort(self) -> Sort:
        return BOOL_SORT

    def __str__(self) -> str:
        return f"Pattern({', '.join(str(e) for e in self.exprs)})"


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Quantifier(Expr, ABC):
    is_forall: bool
    bound_vars: tuple[BoundVar, ...]
    body: Expr
    patterns: tuple[Pattern, ...]

    @property
    def sort(self) -> Sort:
        return BOOL_SORT

    def __str__(self) -> str:
        quant = "ForAll" if self.is_forall else "Exists"
        vars_str = ", ".join(f"{v.name}" for v in self.bound_vars)
        res = f"({quant} ({vars_str}) {self.body})"

        if self.patterns:
            pats_str = ", ".join(str(p) for p in self.patterns)
            res = f"(! {res} :pattern ({pats_str}))"
        return res
