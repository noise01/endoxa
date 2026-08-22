"""The ordered series of an agent's propositions.

One entry per cognitive cycle: the line of thought as an append-only series
rather than a log to grep. What the agent took to be the case, in the order it
came to be the case.

Persistence is a port (:class:`TraceStore`) that a host implements, and the store
owns the total order. This package does not choose where the series lives, only
what a store has to be able to do.

Requires the ``trace`` extra.
"""

from endoxa.trace.models import Proposition
from endoxa.trace.store import TraceStore

__all__ = [
    "Proposition",
    "TraceStore",
]
