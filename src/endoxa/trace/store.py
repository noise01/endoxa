"""The persistence port for the series.

This package says *what* it needs from storage as a Protocol and stays free of
any concrete backend; a host supplies the adapter. Keeping the port here is what
lets the series travel to another agent without dragging a database along.

Writes happen at one point only, and the ``seq`` total order is the store's
responsibility, assigned in append order -- so the port takes a bare
:class:`Proposition` and returns nothing.
"""

from typing import Any, Protocol

from endoxa.trace.models import Proposition


class TraceStore(Protocol):
    """Minimal persistence contract for the ordered series of propositions."""

    async def append(self, proposition: Proposition) -> None:
        """Append ``proposition`` to the series, assigning the next ``seq``."""
        ...

    async def load_recent(self, limit: int) -> list[dict[str, Any]]:
        """Return up to ``limit`` recent rows in ascending ``seq`` order.

        Rows are raw dicts, including the store-assigned ``seq``, rather than
        :class:`Proposition` instances: the reader decides how to structure the
        body, and an audit reader wants what was written rather than a model of
        it.
        """
        ...
