"""endoxa -- governed beliefs for agents.

An agent that asserts things needs somewhere for those assertions to be checked,
recorded, and given up when they turn out to conflict. This package is that
somewhere: hand it beliefs and the constraints they live under, and it answers in
operations -- what to retract, what to hold, what stands -- and writes each one
to an append-only ledger you can read back.

The five packages are a DAG, listed here bottom-up:

- ``endoxa.syntax`` -- the shape of an atom: predicate, arity, arguments.
- ``endoxa.solver`` -- a self-contained SMT engine deciding satisfiability.
- ``endoxa.governance`` -- the decision surface, the ledger it writes, and the
  revision machinery that picks what to give up.
- ``endoxa.trace`` -- the ordered series of an agent's conscious propositions.
- ``endoxa.instruments`` -- calibration and coverage measures, imported by nothing
  else, because a measure its subject can reach is a measure its subject can
  move.

Nothing is re-exported here, and that is the decision rather than an unfinished
one: import from the package you mean. A top-level facade would give every name a
second address, and the layer a name belongs to is the most useful thing its
address can tell you -- ``from endoxa.governance import govern`` says where the
judgement is made, where ``from endoxa import govern`` says only that it exists.
"""

__all__: list[str] = []
