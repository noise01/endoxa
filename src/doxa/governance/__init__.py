"""The decision surface, the ledger, and the revision machinery.

Three things that only make sense together:

- **The decision.** Given beliefs and the constraints they live under, decide
  whether they are consistent and, if not, what to give up. The answer is a list
  of operations, not a mutated state.
- **The ledger.** Those operations are an append-only series. Nothing is edited
  and nothing disappears: a retracted belief keeps its row and stops counting, so
  the record of why the agent believes what it believes survives the change.
- **The revision machinery.** The consistency check, the search for what is
  actually to blame, the preference ordering over what may be given up, and the
  detection of the case where two beliefs are equally credible and the conflict
  cannot be settled from the inside.

Beliefs and rules are separable on purpose: a rule may be *defeasible*, meaning
the agent learned it and may give it up, or hard, meaning it may not.
"""

__all__: list[str] = []
