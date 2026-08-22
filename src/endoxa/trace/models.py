"""The data model for one entry in the series.

A :class:`Proposition` is one entry in the single ordered series -- the line of
thought. Exactly one is produced per cognitive cycle, so the series is what the
agent took to be the case, in the order it came to be the case.

Pure: it imports nothing from a host, from persistence, or from the rest of endoxa.
The body is carried as the originating ``payload`` dict verbatim rather than as a
structured symbol list, because the payload's shape varies by what the entry is
about and the typed columns below are what can be relied on across all of them.
Extracting structure from the body is a reader's concern.

The ordering key ``seq`` is deliberately *not* a field here: it is assigned by the
store at append time and returned on read, so a proposition a host constructs
carries no premature sequence number.
"""

from typing import Any

from pydantic import BaseModel, Field


class Proposition(BaseModel):
    """One entry in the ordered series of propositions.

    Attributes:
        content_id: Identifier of the content this entry is about.
        kind: What the entry is about ("belief"/"surprise"/"contradiction").
        salience: How strongly this entry pushed itself forward, at the moment it
            was recorded.
        confidence: Confidence carried by the proposition.
        source: Name of the process that raised it.
        session_id: The session the entry belongs to.
        cycle_index: Monotonic index of the cognitive cycle within the OS instance
            that produced this entry (resets across restarts; the persisted
            total order is the store-assigned ``seq``, not this).
        timestamp: Wall-clock time of the entry (epoch seconds).
        payload: The body, carried verbatim.
    """

    content_id: str
    kind: str
    salience: float
    confidence: float
    source: str
    session_id: str
    cycle_index: int
    timestamp: float
    payload: dict[str, Any] = Field(default_factory=dict)
