"""Recovering the ledger from what the host already records (RFC-0063 §4, ADR-0119).

The intermediate form RFC-0063 §4 chose separates *the source of truth on the
API* from *the source of truth in the implementation*: the ledger is the former,
the blackboard and the existing stores stay the latter. This module is what makes
that separation cost nothing at the write side -- it is a **read-only derivation**
of the operation series from the host's persisted audit log. No write path
changes; the ledger is a way of reading what already happened.

**Why the event log and not the current state.** RFC-0063 §4 names "blackboard,
TMS, evidence counters, trace" as the derivation's inputs, but the current state
alone cannot yield the series: a retraction is a flip that leaves no trace of
the flip, and the reconstruction check (RFC-0063 §7 criterion 3) needs a series
to reconstruct *from*. The audit log is the only place the host keeps the order
of what it did, so it is the primary input; the board is what the derived view is
then checked against (:func:`~doxa.governance.view.compare_to_state`).

**The horizon.** The retention sweep (ADR-0085) prunes by event type, and until
RFC-0065 increment ② its keep set was the three calibration types plus
``MessageReceivedEvent`` -- not a single ledger-bearing type was in it. A host
running that policy can have had governance operations pruned out from under it,
and a derivation that stayed silent about that would be claiming a completeness
it does not have. :class:`DerivedLedger` therefore reports the horizon (the
earliest row it saw) rather than pretending the series starts at the beginning of
time.

**The horizon does not go away now that the sweep keeps these rows.** The host
took :data:`LEDGER_EVENT_TYPES` into its keep set as a third consumer
(``domains/memory/retention.py``, RFC-0065 §3-3), which is a measure that acts
**forward**: runs already swept cannot be un-pruned, and a host is free to
configure a policy that keeps less (the keep set is an argument, not a law here).
So the horizon keeps meaning exactly what it meant -- the earliest row this
derivation could read, which is not a claim of completeness (RFC-0065 §9-3).

**Reading the host's event names.** An asset may not import
``doppelganger.events`` (the import-linter boundary; the asset has to travel to
another host without the control plane), so the event type names live here as
string constants. A host-side test pins them against the real classes'
``__name__`` so a rename cannot silently empty the ledger.

Pure and basis-independent (stdlib only): the input is the raw row shape the
event store returns, exactly as :func:`~doppelganger.kernel.trace.render_diary`
takes raw trace rows (ADR-0118 decision 2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from doxa.governance.ledger import EVIDENCE_REASONS, EvidenceReason, LedgerOp, SupportRef

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: Host event class names the derivation reads. Pinned against the real classes
#: by a host-side test (see the module docstring).
ATOM_ADDED = "AtomAddedEvent"
BELIEF_EVIDENCE_BOOKED = "BeliefEvidenceBookedEvent"
BELIEF_EVIDENCE_RECORDED = "BeliefEvidenceRecordedEvent"
BELIEF_SUPPORT_RECORDED = "BeliefSupportRecordedEvent"
CONTRADICTION_TIE_DETECTED = "ContradictionTieDetectedEvent"
MEMORY_BATCH_GET_RESPONSE = "MemoryBatchGetResponseEvent"
MEMORY_BATCH_UPDATE_REQUEST = "MemoryBatchUpdateRequestEvent"

#: The event types a ledger derivation reads. Handed to the store's type-filtered
#: read so a diagnostic run does not drag the whole audit log into memory.
#:
#: ``BeliefSupportRecordedEvent`` is the odd one: it yields **no operation at
#: all** (ADR-0133). A derivation reaching a belief already on the board changes
#: no claim and no credence (ADR-0130), so it is read for the support state it
#: carries and for nothing else -- the first row type here that is state without
#: being an operation.
#:
#: ``BeliefEvidenceBookedEvent`` is the write side breaking its own silence
#: (RFC-0065 increment 1, ADR-0135). It maps onto exactly the same operations as
#: ``BeliefEvidenceRecordedEvent``; the two are separate classes only because
#: the board subscribes to the latter, so re-using it would fold the evidence a
#: second time. The distinction is a host wiring detail, and the derivation is
#: deliberately blind to it.
LEDGER_EVENT_TYPES: frozenset[str] = frozenset(
    {
        ATOM_ADDED,
        BELIEF_EVIDENCE_BOOKED,
        BELIEF_EVIDENCE_RECORDED,
        BELIEF_SUPPORT_RECORDED,
        CONTRADICTION_TIE_DETECTED,
        MEMORY_BATCH_GET_RESPONSE,
        MEMORY_BATCH_UPDATE_REQUEST,
    },
)

#: Property name the board writes its support record under, and the keys of one
#: record (``domains.blackboard.support``, ADR-0129). String constants for the
#: same reason the event names are: the asset cannot import the host.
SUPPORTED_BY_KEY = "supported_by"
_SUPPORT_KIND_KEY = "kind"
_SUPPORT_REF_KEY = "ref"

#: Correlation id Reasoning stamps on its axiom batch-get (host constant, pinned
#: by the same host-side test). The response to *this* request is the moment the
#: rule store's content enters the ledger as beliefs -- RFC-0028 §8 open question
#: 1 settled: the file/table is host initialization data, its content becomes
#: governance (RFC-0063 §9 unresolved point 1).
AXIOM_LOAD_CORRELATION_ID = "reasoning_axiom_load"

#: Memory type of a learned or base rule row.
_AXIOM_MEMORY_TYPE = "axiom"

#: Default for the confidence below which a defeasible rule stops constraining
#: (``settings.reasoning_rule_active_confidence_threshold``). Passed in by the
#: host rather than imported, so the asset carries no configuration dependency.
DEFAULT_RULE_ACTIVE_THRESHOLD = 0.5


@dataclass(frozen=True, slots=True)
class DerivedLedger:
    """The operation series recovered from a run's audit log, and what it cost.

    Attributes:
        ops: The operations in the order they happened.
        horizon: Epoch seconds of the earliest row read, or ``None`` when no row
            carried a readable timestamp. Operations before it are unrecoverable
            (see the module docstring on retention).
        rows_read: How many rows the derivation was handed.
        rows_unreadable: Rows whose payload could not be parsed as an object.
            Counted rather than dropped silently, for the same reason the diary
            renders an unreadable broadcast instead of skipping it (ADR-0118
            decision 3).
    """

    ops: tuple[LedgerOp, ...]
    horizon: float | None
    rows_read: int
    rows_unreadable: int


def derive_ledger(
    rows: Sequence[Mapping[str, Any]],
    *,
    rule_active_threshold: float = DEFAULT_RULE_ACTIVE_THRESHOLD,
) -> DerivedLedger:
    """Derive the ledger's operation series from persisted event rows.

    Args:
        rows: Raw ``event_store`` rows (``id``/``timestamp``/``event_type``/
            ``payload``) in any order; they are sorted here.
        rule_active_threshold: Confidence at or above which a defeasible rule
            still constrains. An axiom update below it is a ``retract``.

    Returns:
        The derived series together with what it could and could not see.
    """
    parsed = [record for record in (_parse(row) for row in rows) if record is not None]
    unreadable = len(rows) - len(parsed)
    parsed.sort(key=lambda record: (record.at if record.at is not None else 0.0, record.event_id))

    ops: list[LedgerOp] = []
    state = _FoldState()
    for record in parsed:
        ops.extend(_operations(record, state, rule_active_threshold=rule_active_threshold))

    stamps = [record.at for record in parsed if record.at is not None]
    return DerivedLedger(
        ops=tuple(ops),
        horizon=min(stamps) if stamps else None,
        rows_read=len(rows),
        rows_unreadable=unreadable,
    )


@dataclass(frozen=True, slots=True)
class _Record:
    """One audit-log row normalized into what the derivation reads."""

    event_id: str
    event_type: str
    at: float | None
    payload: dict[str, Any]


def _parse(row: Mapping[str, Any]) -> _Record | None:
    """Normalize a raw store row, or return ``None`` when its payload is unreadable.

    Both row shapes are accepted, as in the diary: the LanceDB adapter's JSON
    string payload and ``datetime`` timestamp, and a plain dict payload with an
    epoch float.
    """
    payload = row.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except TypeError, ValueError:
            return None
    if not isinstance(payload, dict):
        return None
    return _Record(
        event_id=str(row.get("id") or payload.get("event_id") or ""),
        event_type=str(row.get("event_type", "")),
        at=_as_epoch(row.get("timestamp", payload.get("timestamp"))),
        payload=payload,
    )


def _as_epoch(value: object) -> float | None:
    """Coerce a row timestamp to epoch seconds, or ``None`` when unreadable."""
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


@dataclass(slots=True)
class _FoldState:
    """What the fold has to remember between rows.

    ``truth`` is the running truth value per belief: the host's ``AtomAddedEvent``
    carries the properties that were *written*, not the resulting node, so whether
    a write flipped a belief is only visible against what the series says it held
    (``domains/blackboard/graph_ops.py`` ``add_atom``).

    ``supports`` is the same idea for the support seat (ADR-0133): a belief's
    footing accumulates across rows (a materialisation writes one, a later
    derivation reaching the same belief adds another), and each operation is
    stamped with the set as it stood *at that moment*. Mutable and threaded rather
    than recomputed, because the series is the only thing that has the order.
    """

    truth: dict[str, bool] = field(default_factory=dict)
    supports: dict[str, tuple[SupportRef, ...]] = field(default_factory=dict)


def _operations(
    record: _Record,
    state: _FoldState,
    *,
    rule_active_threshold: float,
) -> list[LedgerOp]:
    """Map one event row onto the ledger operations it stands for.

    A row may legitimately stand for none: ``BeliefSupportRecordedEvent`` updates
    the running support state and returns nothing, because gaining a second
    footing is not a governance operation on the belief (ADR-0130 -- the claim and
    the credence are both untouched).
    """
    if record.event_type == ATOM_ADDED:
        return _atom_operations(record, state)
    if record.event_type == BELIEF_SUPPORT_RECORDED:
        _absorb_support(record, state)
        return []
    if record.event_type in (BELIEF_EVIDENCE_RECORDED, BELIEF_EVIDENCE_BOOKED):
        return _evidence_operations(record, state)
    if record.event_type == CONTRADICTION_TIE_DETECTED:
        return _hold_operations(record)
    if record.event_type == MEMORY_BATCH_GET_RESPONSE:
        return _rule_load_operations(record)
    if record.event_type == MEMORY_BATCH_UPDATE_REQUEST:
        return _rule_update_operations(record, rule_active_threshold=rule_active_threshold)
    return []


def _support_refs(records: object) -> tuple[SupportRef, ...]:
    """Read a board support record into typed references, skipping malformed entries.

    Tolerant in the same measure as the board's own reader
    (``domains.blackboard.support``): support is read on paths that also run for
    beliefs that never had any, and an audit log is not a place where raising is
    useful. An unknown ``kind`` is dropped rather than guessed -- the whole point
    of carrying the kind is that it is not inferred.
    """
    if not isinstance(records, list):
        return ()
    refs: list[SupportRef] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        kind = record.get(_SUPPORT_KIND_KEY)
        ref = record.get(_SUPPORT_REF_KEY)
        if kind in ("derivation", "rule") and ref:
            refs.append(SupportRef(kind=kind, ref=str(ref)))
    return tuple(refs)


def _absorb_support(record: _Record, state: _FoldState) -> None:
    """Fold a ``BeliefSupportRecordedEvent`` into the running support state.

    Appended, not replaced, and never duplicated -- mirroring the board's
    ``add_support`` (ADR-0130): a derivation that runs again over the same pair is
    the same footing, not a second one.
    """
    node_id = str(record.payload.get("node_id", ""))
    added = _support_refs([record.payload.get("support")])
    if not node_id or not added:
        return
    current = state.supports.get(node_id, ())
    state.supports[node_id] = current + tuple(ref for ref in added if ref not in current)


def _atom_operations(record: _Record, state: _FoldState) -> list[LedgerOp]:
    """Map an ``AtomAddedEvent`` onto ``assert`` / ``retract`` / ``supersede`` / ``ground``.

    Four cases, in the order they are tested:

    - ``ask_grounding`` -> ``ground``. The ask-user closed loop is the only writer
      of confidence 1.0 (ADR-0018), so it is its own operation whatever else the
      write does.
    - an unseen belief -> ``assert``. Birth defaults to true, matching ``add_atom``.
    - a flip -> ``retract`` or ``supersede``. **The discriminator is the one the
      board itself uses**: ``runtime/blackboard.py`` re-attributes the belief's
      evidence to its new claim (``swap_evidence``, ADR-0078) exactly when the
      write carries no explicit ``confidence``. A revision flip writes the truth
      value alone; recency supersession restates the confidence to say "the world
      moved, the belief was not miscalibrated" (ADR-0068, RFC-0039 §6). So the
      presence of that key is not a guessed proxy for the distinction -- it *is*
      the host's own test for it.
    - anything else -> ``assert``, a restatement (the host publishes nothing at
      all for an idempotent re-assertion, so a row here always changed something).

    A written support record **replaces** what the belief is known to rest on,
    because that is what the board does: ``add_atom`` overwrites the property, so
    a re-derivation names the antecedent it actually rode on this time (ADR-0129).
    Accumulation is the other writer's job (``_absorb_support``).
    """
    payload = record.payload
    node_id = str(payload.get("node_id", ""))
    if not node_id:
        return []
    properties = payload.get("properties") or {}
    if not isinstance(properties, dict):
        properties = {}
    role = str(payload.get("role", ""))
    stated_truth = properties.get("truth_value")
    stated_truth = None if stated_truth is None else bool(stated_truth)
    confidence = _as_confidence(properties.get("confidence"))
    known = state.truth.get(node_id)
    if SUPPORTED_BY_KEY in properties:
        state.supports[node_id] = _support_refs(properties.get(SUPPORTED_BY_KEY))

    if payload.get("ask_grounding"):
        op = "ground"
    elif known is None:
        op = "assert"
        stated_truth = True if stated_truth is None else stated_truth
    elif stated_truth is not None and stated_truth != known:
        op = "supersede" if "confidence" in properties else "retract"
    else:
        op = "assert"

    if stated_truth is not None:
        state.truth[node_id] = stated_truth
    return [
        LedgerOp(
            op=op,  # type: ignore[arg-type]  -- one of the seven, by construction above
            target=node_id,
            actor=role,
            truth_value=stated_truth,
            confidence=confidence,
            origin_event_id=record.event_id,
            at=record.at,
            supported_by=state.supports.get(node_id, ()),
        ),
    ]


def _evidence_operations(record: _Record, state: _FoldState) -> list[LedgerOp]:
    """Map an evidence row onto ``confirm`` or ``refute``.

    Both evidence event types land here (see :data:`LEDGER_EVENT_TYPES`): which
    class the host used says only whether the board had already folded the
    evidence before publishing, which is not a governance distinction.

    No confidence is carried: the event says only which way the evidence points,
    and the resulting credence is the Laplace fold the view replays (RFC-0036 §3).

    This is the operation the support seat was worth filling for. Counter-evidence
    is booked against a derived belief exactly when its footing goes (ADR-0132),
    and stamping the entry with what it was resting on at that moment is what lets
    a reader tell "refuted while still supported" from "refuted because the
    support died" -- from the series alone, with no board in hand. The reason
    (RFC-0065 §3-2) says the same thing from the other side: the support set is
    the *state* the booking found, the reason is the *event* that caused it, and
    a reader who has to infer one from the other is guessing again.
    """
    node_id = str(record.payload.get("node_id", ""))
    if not node_id:
        return []
    supports = bool(record.payload.get("supports", True))
    return [
        LedgerOp(
            op="confirm" if supports else "refute",
            target=node_id,
            origin_event_id=record.event_id,
            at=record.at,
            supported_by=state.supports.get(node_id, ()),
            reason=_reason(record.payload.get("reason")),
        ),
    ]


def _reason(value: object) -> EvidenceReason | None:
    """Read a booking's reason, or ``None`` when it is absent or unrecognised.

    Dropped rather than guessed, exactly as :func:`_support_refs` drops an
    unknown support ``kind``: the whole value of carrying the word is that it was
    not inferred, so an audit log written by an older host (or by a writer this
    vocabulary has not caught up with) reads as "no reason stated" instead of as
    a reason invented here.
    """
    if isinstance(value, str) and value in EVIDENCE_REASONS:
        return value  # type: ignore[return-value]  -- membership above is the Literal
    return None


def _hold_operations(record: _Record) -> list[LedgerOp]:
    """Map a ``ContradictionTieDetectedEvent`` onto one ``hold`` over the pair.

    One operation, not two: a tie *is* a pair (ADR-0081's ``_TIE_ARITY``), and
    counting it twice would make the ledger's own statistics say the system held
    twice as often as it did. The view marks both members from ``partner``.

    The detection event is what the ledger records, not the self-model's
    ``RevisionTieAskEvent``: being unable to settle is the governance layer's
    judgement, while deciding to *ask* about it is the host's dialogue policy
    (ADR-0081 decision 1 keeps those two apart, and an exported ledger should not
    require its host to have a user to talk to).
    """
    node_a = str(record.payload.get("node_a", ""))
    node_b = str(record.payload.get("node_b", ""))
    if not node_a or not node_b:
        return []
    return [
        LedgerOp(
            op="hold",
            target=node_a,
            partner=node_b,
            origin_event_id=record.event_id,
            at=record.at,
        ),
    ]


def _rule_load_operations(record: _Record) -> list[LedgerOp]:
    """Map the axiom batch-get response onto one ``assert`` per rule.

    This is where RFC-0028 §8 open question 1 lands: the rule store is host
    initialization data, and the moment its content is loaded is the moment it
    enters the ledger as beliefs (RFC-0063 §2 decision 3 puts learned rules in
    the ledger's primary scope). A base (non-defeasible) axiom is asserted and
    never retracted; only a defeasible rule has a retraction path.

    Only the response to Reasoning's own axiom load is read: other batch-gets
    (memory recall, paging) return the same row shape but are not the rule set
    being taken into the ledger.
    """
    if record.payload.get("correlation_id") != AXIOM_LOAD_CORRELATION_ID:
        return []
    results = record.payload.get("results")
    if not isinstance(results, list):
        return []
    ops: list[LedgerOp] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        memory_id = str(result.get("id", ""))
        if not memory_id:
            continue
        ops.append(
            LedgerOp(
                op="assert",
                target=memory_id,
                target_kind="rule",
                actor=str(result.get("source_kind") or _AXIOM_MEMORY_TYPE),
                truth_value=True,
                confidence=_as_confidence(result.get("confidence")),
                origin_event_id=record.event_id,
                at=record.at,
            ),
        )
    return ops


def _rule_update_operations(record: _Record, *, rule_active_threshold: float) -> list[LedgerOp]:
    """Map an axiom confidence update onto ``retract`` (or a restating ``assert``).

    Soft retraction of a learned rule is a confidence driven below the active
    threshold (``modules/reasoning.py`` ``_retract_rule``): the row is kept so the
    rule can be re-learned, which is precisely the ledger's own stance -- the
    entry does not disappear, it stops counting. An update that leaves the rule
    active is a restatement, not a withdrawal.
    """
    if record.payload.get("memory_type") != _AXIOM_MEMORY_TYPE:
        return []
    updates = record.payload.get("updates")
    if not isinstance(updates, list):
        return []
    ops: list[LedgerOp] = []
    for update in updates:
        if not isinstance(update, dict):
            continue
        memory_id = str(update.get("id", ""))
        confidence = _as_confidence(update.get("confidence"))
        if not memory_id or confidence is None:
            continue
        ops.append(
            LedgerOp(
                op="retract" if confidence < rule_active_threshold else "assert",
                target=memory_id,
                target_kind="rule",
                actor=_AXIOM_MEMORY_TYPE,
                truth_value=True,
                confidence=confidence,
                origin_event_id=record.event_id,
                at=record.at,
            ),
        )
    return ops


def _as_confidence(value: object) -> float | None:
    """Read a confidence field, or ``None`` when it is absent or not a number."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


__all__ = [
    "AXIOM_LOAD_CORRELATION_ID",
    "DEFAULT_RULE_ACTIVE_THRESHOLD",
    "LEDGER_EVENT_TYPES",
    "SUPPORTED_BY_KEY",
    "DerivedLedger",
    "derive_ledger",
]
