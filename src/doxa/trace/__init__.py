"""The ordered series of an agent's propositions.

One entry per cognitive cycle: the line of thought as an append-only series
rather than a log to grep. Persistence is a port the host implements, and the
store owns the total order -- doxa does not choose where the series lives.

Requires the ``trace`` extra.
"""

__all__: list[str] = []
