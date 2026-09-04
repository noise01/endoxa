"""The fixed set of names for where a belief came from.

Two questions look alike and are not: *who asserted this* and *what brought it
back into view*. A single ``source`` field ends up answering both -- a belief
restored from long-term storage overwrites its own origin with the mechanism that
restored it, and the record of who said it in the first place is gone. So the two
have separate vocabularies here, and the mechanism belongs in a field of its own.

Fixing the names is the whole of this module. Deciding which one applies is the
host's business: the roles a host writes under are its own, and a mapping from
them onto these names cannot be written here without naming a vocabulary that
only exists somewhere else.
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
