"""Check adopted premises and propose verified changes; callers own their state."""

from endoxa.governance._validation import canonical_atom, validate_confidence, validate_id
from endoxa.governance.checks import (
    check_consistency,
    check_entailment,
    check_support,
)
from endoxa.governance.formulas import parse_premise_fof, parse_query_fof
from endoxa.governance.premises import Assertion, PremiseSet, RevisionPolicy, Rule, Target, target_of
from endoxa.governance.proposal import (
    Adopt,
    RevisionBinding,
    RevisionDecision,
    RevisionReason,
    RevisionResult,
    RevisionTrial,
    Withdraw,
    propose_revision,
)
from endoxa.governance.results import Assumption, ConsistencyResult, EntailmentResult, EntailmentVerdict, SolverStatus

__all__ = [
    "Adopt",
    "Assertion",
    "Assumption",
    "ConsistencyResult",
    "EntailmentResult",
    "EntailmentVerdict",
    "PremiseSet",
    "RevisionBinding",
    "RevisionDecision",
    "RevisionPolicy",
    "RevisionReason",
    "RevisionResult",
    "RevisionTrial",
    "Rule",
    "SolverStatus",
    "Target",
    "Withdraw",
    "canonical_atom",
    "check_consistency",
    "check_entailment",
    "check_support",
    "parse_premise_fof",
    "parse_query_fof",
    "propose_revision",
    "target_of",
    "validate_confidence",
    "validate_id",
]
