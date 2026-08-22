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

The exports arrive with the port; this module is the facade they will land in.
"""

__all__: list[str] = []
