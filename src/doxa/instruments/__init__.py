"""Measures of the agent, imported by nothing it can reach.

Where governance is the thing an agent owns, instruments is what says how well it
is doing: the pure accounting behind "does this agent know what it does not know"
and "are its rules actually connected to one another".

- **calibration** -- whether confidence matched accuracy, over what the agent
  claims to know, what it claims to be able to do, and when it chooses to ask
  rather than assert. Cumulative, and recomputed over windows so that an
  improvement curve can be drawn rather than a single running mean.
- **coverage** -- how densely the rules connect the predicates, which is the
  difference between a glossary and a theory.

Its place in the package's dependency order is the mirror image of the solver's.
The solver sits below everything and is imported by everything; instruments sits
above everything and is imported by *nothing*. That direction is the point rather
than an accident: something that depended on its own instrument could not be
measured independently of it. The dependency is forbidden by contract and checked
in CI.

Pure: the instruments compute over snapshots handed to them and know nothing of
storage, concurrency or models.
"""
