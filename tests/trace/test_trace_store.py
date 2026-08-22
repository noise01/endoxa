"""The series and its port, exercised without a database.

The :class:`Proposition` model and the :class:`TraceStore` contract, backed by
an in-memory adapter. A host's own adapter is the host's to test; what is
checked here is what the port promises anyone who implements it.
"""

from typing import Any

import pytest

from endoxa.trace import Proposition, TraceStore


class InMemoryTraceStore:
    """An in-memory :class:`TraceStore`: seq assigned in append order."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self._next_seq = 1

    async def append(self, proposition: Proposition) -> None:
        self.rows.append({"seq": self._next_seq, **proposition.model_dump()})
        self._next_seq += 1

    async def load_recent(self, limit: int) -> list[dict[str, Any]]:
        return sorted(self.rows, key=lambda row: row["seq"])[-limit:]


def _proposition(content_id: str, **overrides: object) -> Proposition:
    fields = {
        "content_id": content_id,
        "kind": "belief",
        "salience": 0.5,
        "confidence": 0.9,
        "source": "Reasoning",
        "session_id": "sess_1",
        "cycle_index": 1,
        "timestamp": 1234.0,
        "payload": {"atom": "mortal(socrates)", "truth_value": True},
    }
    fields.update(overrides)
    return Proposition(**fields)


def test_proposition_carries_body_and_defaults_payload() -> None:
    """A Proposition holds the typed columns and defaults payload to an empty dict."""
    prop = _proposition("c1")
    assert prop.content_id == "c1"
    assert prop.payload == {"atom": "mortal(socrates)", "truth_value": True}
    assert (
        Proposition(
            content_id="c2",
            kind="surprise",
            salience=0.1,
            confidence=0.2,
            source="Intuition",
            session_id="s",
            cycle_index=0,
            timestamp=0.0,
        ).payload
        == {}
    )


@pytest.mark.asyncio
async def test_in_memory_store_conforms_to_port_and_orders_by_seq() -> None:
    """The port appends in order and load_recent returns ascending seq."""
    store: TraceStore = InMemoryTraceStore()  # structural conformance to the port
    await store.append(_proposition("first"))
    await store.append(_proposition("second", cycle_index=2))
    await store.append(_proposition("third", cycle_index=3))

    rows = await store.load_recent(limit=10)
    assert [row["seq"] for row in rows] == [1, 2, 3]
    assert [row["content_id"] for row in rows] == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_load_recent_returns_tail_in_ascending_order() -> None:
    """load_recent bounds to the most recent by seq, still ascending."""
    store = InMemoryTraceStore()
    for i in range(5):
        await store.append(_proposition(f"c{i}", cycle_index=i))

    rows = await store.load_recent(limit=2)
    assert [row["seq"] for row in rows] == [4, 5]
    assert [row["content_id"] for row in rows] == ["c3", "c4"]
