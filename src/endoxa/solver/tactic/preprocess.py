from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from endoxa.solver.sat.types import Lit, VarId


class PreprocessorStats(TypedDict):
    pre_removed_clauses: int
    pre_fixed_vars: int
    pre_pure_literals: int


class Preprocessor:
    def __init__(self, clauses: list[list[Lit]], protected_vars: set[VarId] | None = None) -> None:
        self.clauses = clauses
        self.protected_vars = protected_vars or set()

        self.stats: PreprocessorStats = {
            "pre_removed_clauses": 0,
            "pre_fixed_vars": 0,
            "pre_pure_literals": 0,
        }

    def run(self) -> list[list[Lit]]:
        changed = True
        while changed:
            changed = False

            unit_changed, is_unsat = self._apply_unit_clauses()
            if is_unsat:
                return [[]]
            changed |= unit_changed

            pure_changed = self._apply_pure_literals()
            changed |= pure_changed

        return self.clauses

    def _apply_unit_clauses(self) -> tuple[bool, bool]:
        unit_lits = {c[0] for c in self.clauses if len(c) == 1}
        if not unit_lits:
            return False, False

        for lit in unit_lits:
            if (lit ^ 1) in unit_lits:
                return False, True

        new_clauses: list[list[Lit]] = []
        changed = False

        for c in self.clauses:
            if any(lit in unit_lits for lit in c):
                if len(c) > 1:
                    self.stats["pre_removed_clauses"] += 1
                    changed = True
                else:
                    new_clauses.append(c)
                continue

            new_c = [lit for lit in c if (lit ^ 1) not in unit_lits]

            if len(new_c) == 0 and len(c) > 0:
                return False, True

            if len(new_c) < len(c):
                changed = True

            new_clauses.append(new_c)

        self.clauses = new_clauses
        self.stats["pre_fixed_vars"] += len(unit_lits)
        return changed, False

    def _apply_pure_literals(self) -> bool:
        pos_vars: set[int] = set()
        neg_vars: set[int] = set()

        for c in self.clauses:
            for lit in c:
                var = lit >> 1
                if (lit & 1) == 0:
                    pos_vars.add(var)
                else:
                    neg_vars.add(var)

        pure_vars = pos_vars ^ neg_vars
        pure_vars -= self.protected_vars

        if not pure_vars:
            return False

        pure_lits = {(v << 1) | 0 if v in pos_vars else (v << 1) | 1 for v in pure_vars}
        new_clauses = [c for c in self.clauses if not any(lit in pure_lits for lit in c)]

        removed_count = len(self.clauses) - len(new_clauses)
        if removed_count > 0:
            self.stats["pre_removed_clauses"] += removed_count
            self.stats["pre_pure_literals"] += len(pure_lits)
            self.clauses = new_clauses
            return True

        return False
