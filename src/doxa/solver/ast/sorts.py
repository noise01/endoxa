from abc import ABC
from dataclasses import dataclass


class Sort(ABC):  # noqa: B024
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class BoolSort(Sort):
    def __str__(self) -> str:
        return "Bool"


@dataclass(frozen=True, slots=True)
class IntSort(Sort):
    def __str__(self) -> str:
        return "Int"


@dataclass(frozen=True, slots=True)
class USort(Sort):
    name: str

    def __str__(self) -> str:
        return self.name


BOOL_SORT = BoolSort()
INT_SORT = IntSort()
