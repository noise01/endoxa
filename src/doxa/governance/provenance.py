"""Controlled vocabulary for belief/memory provenance (Stage 1).

Before this increment ``BeliefNode.source`` mixed two unrelated concerns in one
field: the *origin kind* of a belief (who asserted it) and the *retrieval
mechanism* that re-materialized it from LTM (``"LTM_ReadThrough"``,
``"LTM_SpreadingActivation"``). This module fixes the vocabulary for the
former and the pure mapping functions used to derive it at write time; the
retrieval mechanism now lives in the separate ``retrieved_via`` field (see
``runtime/blackboard.py``) so it can never again overwrite the origin.
"""

from __future__ import annotations

# The four write systems (Perception, Actuator, Consolidation, Memory seeding)
# each stamp one of these at birth. "unknown" is the fallback for legacy rows
# and any caller that does not specify an origin.
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

# Retrieval mechanisms that re-materialize an existing belief without
# changing who originally asserted it. Distinct from SOURCE_KINDS: these
# describe *how* a node reappeared, not *who* it came from. "conflict_check"
# is the reversal-conflict restore that pages a user belief back in to compare
# against a contradicting assertion.
RETRIEVAL_KINDS = frozenset({"read_through", "spreading_activation", "conflict_check"})

# Belief-node property keys that are fixed at birth and never overwritten by
# a later update (see Blackboard._add_atom). Read-through/spreading-activation
# restore these from the LTM row rather than replacing them.
PROVENANCE_KEYS = frozenset({"source", "session_id", "origin_event_id"})

# Fallback mapping from an AddAtomMessage/Coalition "role" to a controlled
# source kind, used whenever a caller does not pass an explicit "source".
_ROLE_TO_SOURCE_KIND: dict[str, str] = {
    "user": "user",
    "conjecture": "user",
    "corpus": "corpus",
    "observation": "tool",
    "agent": "derivation",
}


def source_kind_for_role(role: str) -> str:
    """Map a belief-write role to its controlled-vocabulary source kind.

    Used as the birth-time fallback when a write does not carry an explicit
    ``source`` property (see Blackboard._add_atom): the user-message and
    ask-user grounding paths write with ``role="user"``/``"conjecture"``,
    corpus writes with ``role="corpus"``, tool observations with
    ``role="observation"``, and derived/LTM-restored writes with
    ``role="agent"``.

    Args:
        role: The role carried on the write (AddAtomMessage.role).

    Returns:
        A value from :data:`SOURCE_KINDS`; ``"unknown"`` for any role not in
        the fallback mapping.
    """
    return _ROLE_TO_SOURCE_KIND.get(role, "unknown")


def episode_source_kind(kind: str, source: str) -> str:
    """Map a conscious broadcast's coalition kind/source to an episode's source kind.

    For a ``"belief"`` coalition, ``source`` carries the originating write's
    role (see ``GlobalWorkspace.on_atom_added``), so the same role mapping
    applies. Every other coalition kind (surprise, contradiction,
    revision_conflict, error, semantic) is an agent-internal derived signal
    rather than something a role authored, so it is tagged ``"derivation"``.

    Args:
        kind: The winning coalition's kind (``event.kind`` on
            ``CoalitionBroadcastEvent``).
        source: The winning coalition's source (``event.source``).

    Returns:
        A value from :data:`SOURCE_KINDS`.
    """
    if kind == "belief":
        return source_kind_for_role(source)
    return "derivation"
