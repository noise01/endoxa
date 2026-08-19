"""Measures of the agent, imported by nothing it can reach.

Two of them:

- **calibration** -- whether the agent's confidence matches its accuracy, over
  what it claims to know, what it claims to be able to do, and when it chooses
  to ask rather than assert.
- **coverage** -- how densely the agent's rules connect the predicates it uses,
  which is the difference between a glossary and a theory.

Nothing else in doxa imports this package, and that is a rule rather than an
accident: a measure its subject can reach is a measure its subject can move.
"""

__all__: list[str] = []
