"""A self-contained SMT engine.

Satisfiability modulo theories with assumption-based solving, an equality
(EUF) theory, quantifier instantiation by E-matching under an explicit round
budget, and a TPTP front end. It carries no dependency on the rest of doxa and
answers three ways -- satisfiable, unsatisfiable, or unknown when the budget
runs out, which is a real answer and not a failure.

Its correctness is asserted differentially against Z3 rather than by its own
suite alone; those tests are dev-only and live outside the shipped package.
"""

__all__: list[str] = []
