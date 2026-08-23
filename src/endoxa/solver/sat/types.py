from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

type VarId = int
type Lit = int
type LBool = int

L_FALSE: LBool = -1
L_UNDEF: LBool = 0
L_TRUE: LBool = 1

NULL_LITERAL: Lit = -1
UNSAT_LITERAL: Lit = -2


@dataclass(slots=True)
class Clause:
    literals: list[Lit]
    is_learned: bool = False

    activity: float = 0.0
    lbd: int = 0
    is_deleted: bool = False

    def __str__(self) -> str:
        return f"Clause({self.literals})"


#: Called on every assignment the trail makes, for a host watching the search:
#: the variable, the value it took, the decision level, and the clause that forced
#: it (``None`` for a decision, which nothing forced).
type AssignHook = Callable[[VarId, LBool, int, Clause | None], None]

#: Optional hooks into the search, keyed by name: ``on_assign``, ``on_conflict``,
#: ``on_learn``, ``on_backtrack``. Their signatures differ, so what is stated here
#: is that the values are callable and the keys are the four above.
type Callbacks = dict[str, Callable[..., Any]]
