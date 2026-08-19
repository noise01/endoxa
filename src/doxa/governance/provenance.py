"""The fixed set of names for where a belief came from.

Two questions look alike and are not: *who asserted this* and *what brought it
back into view*. A single ``source`` field ends up answering both -- a belief
restored from long-term storage overwrites its own origin with the mechanism that
restored it, and the record of who said it in the first place is gone. So the two
have separate vocabularies here, and the mechanism belongs in a field of its own.

Fixing the names is the whole of this module. Deciding which one applies is the
host's business; deciding what the words may be is the ledger's.
"""

#: Where a belief originated. One of these is stamped at birth by whatever wrote
#: it, and ``unknown`` is the fallback for a row that predates the distinction or
#: a caller that does not specify.
SOURCE_KINDS = frozenset(
    {
        "user",
        "tool",
        "corpus",
        "consolidation",
        "derivation",
        "seed",
        "unknown",
    },
)

#: How an existing belief was brought back into view, which never changes who
#: originally asserted it. ``conflict_check`` is the restore that pages a belief
#: back in to compare it against something that contradicts it.
RETRIEVAL_KINDS = frozenset({"read_through", "spreading_activation", "conflict_check"})

#: The properties fixed at birth that a later update must not overwrite. A
#: restore re-attaches these from the stored row rather than replacing them --
#: which is the mechanical form of the distinction this module exists to keep.
PROVENANCE_KEYS = frozenset({"source", "session_id", "origin_event_id"})

#: Fallback mapping from the role a write carried to a source kind, used whenever
#: a caller does not pass an explicit source.
_ROLE_TO_SOURCE_KIND: dict[str, str] = {
    "user": "user",
    "conjecture": "user",
    "corpus": "corpus",
    "observation": "tool",
    "agent": "derivation",
}


def source_kind_for_role(role: str) -> str:
    """Map the role a belief was written under to a source kind.

    Used as the birth-time fallback when a write carries no explicit ``source``:
    something a person said or conjectured is ``user``, something read from a
    corpus is ``corpus``, an observation from a tool is ``tool``, and anything the
    agent derived or restored for itself is ``derivation``.

    Args:
        role: The role carried on the write.

    Returns:
        A value from :data:`SOURCE_KINDS`; ``"unknown"`` for any role not in the
        fallback mapping.
    """
    return _ROLE_TO_SOURCE_KIND.get(role, "unknown")


def episode_source_kind(kind: str, source: str) -> str:
    """Map an episode's kind and source onto the source kind it should record.

    When the episode is about a belief, ``source`` carries the role the belief was
    written under, so the same role mapping applies. Every other kind of episode --
    a surprise, a contradiction, an error -- is something the agent worked out
    internally rather than something a role authored, so it is ``derivation``.

    Args:
        kind: What the episode was about.
        source: Where it came from, for a belief episode.

    Returns:
        A value from :data:`SOURCE_KINDS`.
    """
    if kind == "belief":
        return source_kind_for_role(source)
    return "derivation"
