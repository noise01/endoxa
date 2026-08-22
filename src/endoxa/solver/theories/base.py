from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from endoxa.solver.sat.types import Clause, Lit


class TheorySolver(ABC):
    @abstractmethod
    def assert_literal(self, lit: Lit) -> tuple[bool, list[Lit]]: ...

    @abstractmethod
    def explain_propagation(self, p_lit: Lit) -> Clause: ...

    @abstractmethod
    def check(self) -> list[Clause]: ...

    @abstractmethod
    def push(self) -> None: ...

    @abstractmethod
    def pop(self, num_levels: int) -> None: ...
