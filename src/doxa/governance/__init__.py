"""Belief-governance asset: the ledger, the view derived from it, and the machinery (RFC-0063).

Asset ② of RFC-0026's four. The governance *machinery* has existed since the
sixth period -- TMS revision, preference bands, evidence updates, tie questions --
but scattered across the host's domain modules, which is why "the governance
layer can be attached to any agent" (RFC-0026 Decision 4) has never been
testable. This package gives that machinery a public shape:

- :mod:`~doxa.governance.ledger` declares the seven operations as
  an append-only schema (RFC-0063 §2).
- :mod:`~doxa.governance.derive` recovers the operation series
  from the host's audit log, read-only (RFC-0063 §4's intermediate form: the
  ledger is the source of truth on the API, the board still is in the
  implementation).
- :mod:`~doxa.governance.view` folds the series back into the
  current view, where an unsettleable tie is finally a state with a name
  (:data:`~doxa.governance.view.UNRESOLVED`).
- :mod:`~doxa.governance.resolution` is the decision surface: hand
  it beliefs and the constraints they live under and it answers in ledger
  operations (RFC-0063 §5 increment 2). Reading a ledger is not yet being
  governed; this is what makes an external host governable.
- :mod:`~doxa.governance.support` reads a belief's footing off
  what became of its supports (RFC-0064 §3-2): had none, still standing, lost
  them all, or lost them to a board that no longer holds the antecedent -- the
  last being why "gone" and "refuted" must not share a name (ADR-0131).

- :mod:`~doxa.governance.revision` is that machinery itself: the
  consistency check, the culprit searches, the preference bands and the tie
  detection every operation above is decided by.
- :mod:`~doxa.governance.provenance` is the vocabulary of belief
  origins (which source kind, which retrieval kind) that the ledger records.
- :mod:`~doxa.governance.knowledge` names where a belief sits
  relative to the knowledge boundary -- a fact about the belief set, so the
  schema lives with it while the classifying policy stays in the host
  (RFC-0026 Decision 4 (c), ADR-0125).

The last two arrived in RFC-0028 Phase 2's final migration (ADR-0125), which is
what made the boundary statable as one sentence: **the kernel imports nothing
outside the kernel**, now a single import-linter contract rather than a list of
forbidden hosts (RFC-0028 §2 principle 1, ADR-0122 decision 3).

They are residents of this namespace, not flattened into it -- the same shape
``kernel/lib`` and ``kernel/instruments`` took (ADR-0122 decision 1, ADR-0124
decision 1). What this package's own ``__all__`` exports is the *API*: the ledger
schema, the derived view, and the decision surface.
"""

from doxa.governance.derive import LEDGER_EVENT_TYPES, DerivedLedger, derive_ledger
from doxa.governance.knowledge import EpistemicStatus
from doxa.governance.ledger import (
    EVIDENCE_REASONS,
    LEDGER_OPS,
    REASON_REASSERTION,
    REASON_REVISION_SURVIVED,
    REASON_RULE_RETRACTED,
    REASON_SUPPORT_LOST,
    EvidenceReason,
    LedgerOp,
    OpKind,
    SupportKind,
    SupportRef,
    TargetKind,
)
from doxa.governance.resolution import (
    GOVERNANCE_ACTOR,
    RETRACTED_RULE_CONFIDENCE,
    Belief,
    Constraints,
    ContradictionTie,
    GovernanceOutcome,
    Rule,
    govern,
)
from doxa.governance.support import (
    ABSENT,
    ALIVE,
    DEAD,
    IN,
    INDETERMINATE,
    OUT,
    UNSUPPORTED,
    SupportState,
    SupportVerdict,
    support_verdict,
)
from doxa.governance.view import (
    HELD,
    UNRESOLVED,
    BeliefState,
    ViewEquivalence,
    compare_to_state,
    reconstruct_view,
)

__all__ = [
    "ABSENT",
    "ALIVE",
    "DEAD",
    "EVIDENCE_REASONS",
    "GOVERNANCE_ACTOR",
    "HELD",
    "IN",
    "INDETERMINATE",
    "LEDGER_EVENT_TYPES",
    "LEDGER_OPS",
    "OUT",
    "REASON_REASSERTION",
    "REASON_REVISION_SURVIVED",
    "REASON_RULE_RETRACTED",
    "REASON_SUPPORT_LOST",
    "RETRACTED_RULE_CONFIDENCE",
    "UNRESOLVED",
    "UNSUPPORTED",
    "Belief",
    "BeliefState",
    "Constraints",
    "ContradictionTie",
    "DerivedLedger",
    "EpistemicStatus",
    "EvidenceReason",
    "GovernanceOutcome",
    "LedgerOp",
    "OpKind",
    "Rule",
    "SupportKind",
    "SupportRef",
    "SupportState",
    "SupportVerdict",
    "TargetKind",
    "ViewEquivalence",
    "compare_to_state",
    "derive_ledger",
    "govern",
    "reconstruct_view",
    "support_verdict",
]
