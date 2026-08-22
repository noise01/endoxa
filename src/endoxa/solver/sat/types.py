from dataclasses import dataclass

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
