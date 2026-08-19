"""Vocabulary-link constraint synthesis for the SMT consistency check (RFC-0029/0030/0031).

Unit propagation (ADR-0056) detects a functional-exclusion clash in-beat and
escalates it, but the deeper anytime tier -- the full SMT consistency check
(:mod:`.revision`) -- has no way to *represent* the clash: functional exclusion
is not part of the axiom network, so the solver returns SAT and the TMS revision
loop never fires (ADR-0056 known limitation (a); baseline resolution rate 0.0 in
``paper/05_evaluation.md`` §5.14).

This module closes that gap (RFC-0029 §5, decision (b) "ground clause"). For a
predicate declared single-valued (in ``settings.functional_predicates`` -- the
same config the blackboard bootstrap uses, ADR-0056 decision 3), two atoms that
share their leading arguments but differ in the final value cannot both hold. We
synthesize the ground clause ``Not(And(atomA, atomB))`` for each such pair
currently held true. Because both atoms are asserted, the clause is directly
UNSAT without any unique-names / distinctness assumption: term distinctness is
already baked in at detection time by ADR-0038 canonicalization (the values are
compared as strings and differ). This deliberately sidesteps the fallible
equality-atom question (``backlog.md`` §5 "項レベルの同一性") -- a future
increment moving to the general axiom ``forall x,y,z. P(x,y) & P(x,z) -> y=z``
plus a fallible ``Not(Eq(...))`` would reopen it (RFC-0029 §5 移行余地).
That increment has no evidence pulling for it yet: the in-vivo residual it would
serve measures zero across every run to date, and the ``adversarial`` load
cannot produce one by construction (RFC-0024 §3 mechanism C dropped coined
proper nouns for common-noun entities repeated verbatim). The counter that would
show otherwise is ``missed_irreducible_term_drift`` on the corpus arm
(ADR-0117); read it before reopening this.

The same "detected but unrepresentable" gap holds for the other innate logical
forms the vocabulary asset records, so their clause synthesis lives here too:
:func:`inter_predicate_exclusion_clauses` (pairwise antonym / exclusion class,
RFC-0030) and :func:`implication_clauses` (defeasible implication,
RFC-0031) build their constraints from the acquired links instead of config, but
are otherwise the same ground-clause construction.

Those three are *violation* clauses: each is emitted only for a constraint the
belief set currently breaks, which is what a contradiction check and its revision
need to see. :func:`backward_implication_clauses` is the module's one *derivation*
clause source (RFC-0049 §4): a belief-verification query asks whether a target
follows, not whether something is broken, so the violation gate would emit nothing
and leave the acquired vocabulary invisible to ``verify_belief``. It walks the
implication links backwards from the target instead. The distinction matters --
ADR-0072's agreement discipline requires every tier to read the same *link set*,
not to synthesize the same *clauses* from it.

Pure and basis-independent (governance tier, RFC-0028 §7): stdlib, sibling
:mod:`.facts`, :mod:`doxa.solver`, and the vocabulary asset's atom
grammar (:func:`~doxa.syntax.parse_atom` -- governance stands on
vocabulary, which is the asset DAG's permitted direction). Clauses are built from
the belief *node-id strings* via :func:`parse_fact_to_expr`, the same parser
:func:`.revision.build_assumptions` uses, so a synthesized clause's atom Exprs are
identical to the assumption Exprs and the solver correlates them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from itertools import combinations
from typing import TYPE_CHECKING, Any, Literal

from doxa.governance.revision.facts import parse_fact_to_expr
from doxa.solver import And, Implies, Not
from doxa.syntax import parse_atom
from doxa.syntax.atoms import FUNCTIONAL_MIN_ARITY

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from doxa.solver import Expr


def _is_true(data: dict[str, Any]) -> bool:
    """Whether a belief node is currently held true (functional exclusion is stated over holding)."""
    return bool(data.get("truth_value", True))


@dataclass(frozen=True, slots=True)
class PredicateLink:
    """One acquired link, named so it can be retracted (ADR-0074).

    The identity a culprit search returns and a retraction event carries:
    ``kind`` picks which constraint source it lives in, ``predicate`` owns it and
    ``target`` is what it excludes or implies. Plain strings rather than the
    asset's link types -- ``kernel/governance/tms`` reasons over the constraints, not over
    the vocabulary asset's models.
    """

    kind: Literal["exclusion", "implication"]
    predicate: str
    target: str


@dataclass(frozen=True, slots=True)
class PredicateConstraints:
    """The three link sources the vocabulary asset records, bundled for clause synthesis.

    Groups the inputs of :func:`functional_exclusion_clauses`,
    :func:`inter_predicate_exclusion_clauses` and :func:`implication_clauses`
    so a caller can carry "the constraints the vocabulary imposes" as one value and hand
    it to both the detection path (the consistency check) and the *revision* path
    (whiff re-verification and rule-culprit search). Detection and resolution must see
    the same constraints (RFC-0029 §5, extended to revision selection by ADR-0072);
    passing them separately is what let the two drift apart.

    The empty default is the production baseline: every field empty yields no clauses,
    leaving every check byte-for-byte unchanged.
    """

    functional_predicates: Collection[str] = ()
    exclusion_targets: Mapping[str, Collection[str]] = field(default_factory=dict)
    implication_targets: Mapping[str, Collection[str]] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Whether no link source is populated (so clause synthesis is a no-op)."""
        return not self.functional_predicates and not self.exclusion_targets and not self.implication_targets

    def acquired_links(self) -> list[PredicateLink]:
        """Enumerate the links the acquisition ritual populated, as retraction candidates.

        ``functional_predicates`` is deliberately excluded (ADR-0074): it is a
        config bootstrap standing in for a per-symbol link the ritual has not yet
        elicited (ADR-0056), not acquired data, and functional-exclusion clashes
        are resolved by recency supersession before culprit search is reached.

        Returns:
            The exclusion and implication links, ordered deterministically.
        """
        links = [
            PredicateLink(kind="exclusion", predicate=predicate, target=target)
            for predicate, targets in self.exclusion_targets.items()
            for target in targets
        ]
        links.extend(
            PredicateLink(kind="implication", predicate=predicate, target=target)
            for predicate, targets in self.implication_targets.items()
            for target in targets
        )
        return sorted(links, key=lambda link: (link.kind, link.predicate, link.target))

    def without(self, link: PredicateLink) -> PredicateConstraints:
        """Return a copy with ``link`` dropped, for the single-fault culprit re-check.

        Args:
            link: The link to remove from the constraint set.

        Returns:
            The reduced constraints (the same clause sources minus one edge).
        """
        source = self.exclusion_targets if link.kind == "exclusion" else self.implication_targets
        reduced = {
            predicate: [t for t in targets if not (predicate == link.predicate and t == link.target)]
            for predicate, targets in source.items()
        }
        field_name = "exclusion_targets" if link.kind == "exclusion" else "implication_targets"
        return replace(self, **{field_name: reduced})


def predicate_clauses(
    beliefs: dict[str, dict[str, Any]],
    constraints: PredicateConstraints | None,
) -> list[Expr]:
    """Synthesize every vocabulary-derived ground clause the belief set currently violates.

    Runs the three synthesizers in this module over one belief set. Every clause they
    emit is by construction a *currently violated* constraint -- exclusion clauses are
    emitted only for pairs held true together, an implication only for an antecedent
    held true with its consequent held false -- so the length of the returned list is
    also the clash count of ``beliefs``. The revision path uses that count as its
    progress measure when no single flip fully resolves a pile-up (ADR-0072).

    Args:
        beliefs: Mapping of belief node ID to its data (``truth_value`` etc.).
        constraints: The vocabulary link sources, or ``None`` for "no constraints".

    Returns:
        The ground clause expressions to add as hard constraints (empty when
        ``constraints`` is ``None`` or carries no populated link source).
    """
    if constraints is None or constraints.is_empty():
        return []
    clauses = functional_exclusion_clauses(beliefs, constraints.functional_predicates)
    clauses.extend(inter_predicate_exclusion_clauses(beliefs, constraints.exclusion_targets))
    clauses.extend(implication_clauses(beliefs, constraints.implication_targets))
    return clauses


def functional_exclusion_clauses(
    beliefs: dict[str, dict[str, Any]],
    functional_predicates: Collection[str],
) -> list[Expr]:
    """Synthesize ``Not(And(a, b))`` clauses for every functional-exclusion clash held true.

    For each predicate in ``functional_predicates``, group the true atoms by their
    leading arguments (``args[:-1]``) and, for each pair sharing those but differing
    in the final value (``args[-1]``), emit a ground exclusion clause. Mirrors the
    functional-exclusion arm of :func:`.propagation.propagate` (same predicate, same
    arity ``>= FUNCTIONAL_MIN_ARITY``, equal leading args, distinct final value) so
    detection and this resolution constraint agree.

    The arity floor is that mirror's, not this function's own judgement: below it
    the leading arguments are the empty tuple, so every atom of the predicate
    would group together and any two individuals would be emitted as a clash. It
    applies to a config-declared predicate too --- the rule is about what
    functional exclusion *means*, so it cannot hold for an acquired link and not
    for a declared one.

    Returns an empty list when ``functional_predicates`` is empty (the production
    default, ADR-0056 decision 3), leaving the consistency check byte-for-byte
    unchanged for every caller that does not opt in.

    Args:
        beliefs: Mapping of belief node ID to its data (``truth_value`` etc.).
        functional_predicates: Predicate names declared single-valued.

    Returns:
        The ground exclusion clause expressions to add as hard constraints.
    """
    functional = frozenset(functional_predicates)
    if not functional:
        return []

    # (predicate, leading-args) -> list of (node_id, final_value) held true.
    groups: dict[tuple[str, tuple[str, ...]], list[tuple[str, str]]] = {}
    for node_id, data in beliefs.items():
        if not _is_true(data):
            continue
        atom = parse_atom(node_id)
        if atom is None:
            continue
        predicate, args = atom.predicate, atom.args
        if predicate not in functional or len(args) < FUNCTIONAL_MIN_ARITY:
            continue
        groups.setdefault((predicate, args[:-1]), []).append((node_id, args[-1]))

    clauses: list[Expr] = []
    for members in groups.values():
        for (id_a, value_a), (id_b, value_b) in combinations(members, 2):
            if value_a != value_b:
                clauses.append(Not(And(parse_fact_to_expr(id_a), parse_fact_to_expr(id_b))))
    return clauses


def inter_predicate_exclusion_clauses(
    beliefs: dict[str, dict[str, Any]],
    exclusion_targets: Mapping[str, Collection[str]],
) -> list[Expr]:
    """Synthesize ``Not(And(a, b))`` clauses for every inter-predicate exclusion clash held true.

    Generalizes :func:`functional_exclusion_clauses` from the intra-predicate
    value swap to the inter-predicate forms (RFC-0030, closing ADR-0068 limitation
    (a) for pairwise antonym / exclusion class). For each pair of true atoms that
    share their *whole* argument tuple but whose predicates are declared mutually
    exclusive, emit a ground exclusion clause. Mirrors the inter-predicate arm of
    :func:`.propagation.propagate` (excluded predicate on the identical argument
    tuple) so detection and this resolution constraint agree.

    ``exclusion_targets`` maps a predicate to the predicate names it excludes. The
    relation is treated as *undirected* here: atoms ``p(args)`` and ``q(args)``
    clash when ``q`` is in ``exclusion_targets[p]`` **or** ``p`` is in
    ``exclusion_targets[q]``. The acquisition ritual records an exclusion link on
    the proposing symbol only (:func:`.memory._build_exclusion_links` adds no
    reciprocal edge), and unit-propagation detection reads only the *newer* atom's
    links, so it misses a clash asserted in the other order (RFC-0030 §5). Treating
    the relation undirected here (a) guarantees every unit-propagation-detected
    clash is representable and (b) additionally closes that assertion-order blind
    spot at the deeper SMT tier -- two co-present, contradictory atoms are UNSAT
    regardless of which was asserted last.

    Returns an empty list when ``exclusion_targets`` is empty (the production
    default with no populated inter-predicate links), leaving the consistency
    check byte-for-byte unchanged for every caller that does not opt in.

    Args:
        beliefs: Mapping of belief node ID to its data (``truth_value`` etc.).
        exclusion_targets: Predicate name -> the predicate names it excludes.

    Returns:
        The ground exclusion clause expressions to add as hard constraints.
    """
    if not exclusion_targets:
        return []

    # Whole-argument-tuple -> list of (node_id, predicate) held true. Inter-predicate
    # exclusion is stated over the identical argument tuple (unlike functional
    # exclusion, which groups by the *leading* args), so the full args are the key.
    groups: dict[tuple[str, ...], list[tuple[str, str]]] = {}
    for node_id, data in beliefs.items():
        if not _is_true(data):
            continue
        atom = parse_atom(node_id)
        if atom is None:
            continue
        predicate, args = atom.predicate, atom.args
        groups.setdefault(args, []).append((node_id, predicate))

    clauses: list[Expr] = []
    for members in groups.values():
        for (id_a, pred_a), (id_b, pred_b) in combinations(members, 2):
            if pred_a == pred_b:
                continue
            if pred_b in exclusion_targets.get(pred_a, ()) or pred_a in exclusion_targets.get(pred_b, ()):
                clauses.append(Not(And(parse_fact_to_expr(id_a), parse_fact_to_expr(id_b))))
    return clauses


def implication_clauses(
    beliefs: dict[str, dict[str, Any]],
    implication_targets: Mapping[str, Collection[str]],
) -> list[Expr]:
    """Synthesize ``Implies(antecedent, consequent)`` clauses for every implication clash held.

    Closes the last of the innate logical forms (RFC-0027 §10-1: three exclusion
    kinds plus implication) that unit propagation detects but the SMT tier cannot
    represent (RFC-0031, closing ``backlog.md`` §0 item 1 (a)). For each true atom
    ``p(args)`` whose predicate implies ``q`` and whose ``q(args)`` is on the board
    held **false**, emit the ground implication. Both polarities are already
    assumptions, so the clause is directly UNSAT and the TMS revision loop fires.

    ``implication_targets`` maps a predicate to the predicate names it implies. Unlike
    :func:`inter_predicate_exclusion_clauses`, the relation is **directed**: exclusion
    is symmetric, but ``cat(x) -> animal(x)`` does not license ``animal(x) -> cat(x)``,
    and symmetrizing would inject the false constraint that every animal is a cat.

    A consequent *absent* from the board yields no clause. This keeps the clause set
    identical to unit propagation's escalation condition (a consequent held false,
    :func:`.propagation.propagate`) per the detection/resolution agreement discipline
    (RFC-0029 §5). Emitting the implication for an absent consequent would let the
    solver *derive* ``q(args)`` -- forward materialization of a new atom, which is a
    separate question about derived-atom provenance on the blackboard (RFC-0031 §4),
    not contradiction resolution.

    Scanning board pairs additionally closes the assertion-order blind spot of
    in-beat detection (propagation reads only the newly asserted atom's links, so a
    consequent asserted false *after* its antecedent is missed) -- the same deeper-tier
    strengthening :func:`inter_predicate_exclusion_clauses` gets from undirectedness.

    Returns an empty list when ``implication_targets`` is empty (the production
    default with no populated implication links), leaving the consistency check
    byte-for-byte unchanged for every caller that does not opt in.

    Args:
        beliefs: Mapping of belief node ID to its data (``truth_value`` etc.).
        implication_targets: Predicate name -> the predicate names it implies.

    Returns:
        The ground implication clause expressions to add as hard constraints.
    """
    if not implication_targets:
        return []

    # Implication is stated over the identical argument tuple, so group by the full
    # args and split by polarity: antecedents are looked up among the true atoms,
    # consequents among the false ones.
    true_by_args: dict[tuple[str, ...], list[tuple[str, str]]] = {}
    false_by_args: dict[tuple[str, ...], dict[str, str]] = {}
    for node_id, data in beliefs.items():
        atom = parse_atom(node_id)
        if atom is None:
            continue
        predicate, args = atom.predicate, atom.args
        if _is_true(data):
            true_by_args.setdefault(args, []).append((node_id, predicate))
        else:
            false_by_args.setdefault(args, {})[predicate] = node_id

    clauses: list[Expr] = []
    for args, members in true_by_args.items():
        negated = false_by_args.get(args)
        if not negated:
            continue
        for node_id, predicate in members:
            for target in implication_targets.get(predicate, ()):
                consequent_id = negated.get(target)
                if consequent_id is not None:
                    clauses.append(Implies(parse_fact_to_expr(node_id), parse_fact_to_expr(consequent_id)))
    return clauses


def backward_implication_clauses(
    target: str,
    implication_targets: Mapping[str, Collection[str]],
) -> list[Expr]:
    """Synthesize the implication clauses that could let ``target`` be derived (RFC-0049 §4).

    Belief verification (``verify_belief``, ADR-0017) asks whether an atom follows
    from the rest of the beliefs under the active constraints. Until now it saw only
    the axiom network, so a consequence the *acquired* vocabulary licenses came back
    ``NOT_ENTAILED``: the system could derive ``p(c)`` from a ritual link ``q => p``
    on the propagation tier (ADR-0073) but could not confirm it on the SMT tier. That
    asymmetry made ``verification`` usage credit structurally unreachable for coined
    symbols, which is what pinned the vocabulary economy's second usage kind at zero
    (ADR-0089 known limitation (d)).

    :func:`implication_clauses` cannot fill the gap. It gates on a
    *violated* implication -- antecedent true, consequent on the board held false --
    because emitting an implication for an absent consequent would let the solver
    derive it, which is forward materialization rather than contradiction resolution
    (RFC-0031 §4). In a verification query the target is dropped from the assumptions
    in both polarities (ADR-0034) and is not held false, so that gate emits nothing.
    Derivation is exactly what this query wants, so this synthesizer inverts the walk:
    start at the target and collect the links that could conclude it.

    Walks ``implication_targets`` *backwards* from the target's predicate to the
    transitive closure of its antecedents (breadth-first, each predicate expanded
    once so a cyclic link set terminates), emitting the ground implication for every
    edge reached on the target's own argument tuple -- implication is stated over the
    identical arguments, as in :func:`implication_clauses`. Taking the
    closure rather than one hop keeps "can the system verify what it owns" from
    depending on the shape of the link graph: ``r => q => p`` must verify ``p`` from
    ``r`` the same way one hop does. The cost is linear in the reachable link count.

    ADR-0034 is preserved: the clauses are implications *toward* the target, never
    the target as a premise, so nothing here lets ``target`` prove itself. Exclusion
    links are deliberately not supplied -- ``Not(And(p, q))`` yields the entailment of
    a *negation*, and a ``verify_belief`` target is a plan precondition, always
    positive (RFC-0049 §4-2).

    Returns an empty list when ``implication_targets`` is empty (the production
    default with no populated implication links) or the target is unparseable,
    leaving the verification query byte-for-byte unchanged for every caller that
    does not opt in.

    Args:
        target: The atom being verified, as a fact string (e.g. ``"mortal(socrates)"``).
        implication_targets: Predicate name -> the predicate names it implies.

    Returns:
        The ground implication clause expressions to add as hard constraints.
    """
    if not implication_targets:
        return []
    atom = parse_atom(target)
    if atom is None:
        return []
    predicate, args = atom.predicate, atom.args

    # Reverse the directed link map: consequent -> the predicates implying it.
    antecedents: dict[str, list[str]] = {}
    for antecedent, targets in implication_targets.items():
        for consequent in targets:
            antecedents.setdefault(consequent, []).append(antecedent)

    clauses: list[Expr] = []
    expanded = {predicate}
    frontier = [predicate]
    while frontier:
        next_frontier: list[str] = []
        for consequent in frontier:
            for antecedent in sorted(antecedents.get(consequent, ())):
                clauses.append(
                    Implies(_ground_atom(antecedent, args), _ground_atom(consequent, args)),
                )
                if antecedent not in expanded:
                    expanded.add(antecedent)
                    next_frontier.append(antecedent)
        frontier = next_frontier
    return clauses


def _ground_atom(predicate: str, args: tuple[str, ...]) -> Expr:
    """Build the Expr for ``predicate`` applied to ``args``.

    Goes through :func:`parse_fact_to_expr` -- the parser the assumptions are built
    with -- so a synthesized atom is the identical Expr the solver correlates with
    the belief's assumption. The parser trims each term, so the separator's spacing
    does not affect identity.
    """
    return parse_fact_to_expr(f"{predicate}({', '.join(args)})")


def functional_exclusion_partner(
    node_id: str,
    beliefs: dict[str, dict[str, Any]],
    functional_predicates: Collection[str],
) -> tuple[str, dict[str, Any]] | None:
    """Find the atom that ``node_id`` functionally excludes and that is still held true.

    Used by the resolution path (RFC-0029 §6): when a functional-exclusion clash
    is escalated, ``node_id`` is the newly asserted atom (the coalition
    ``content_id``), so its true, same-leading-args, different-final-value partner
    is the *older* belief the recency-supersession rule retracts. Functional
    exclusion signals a state change ("moved"), not a miscalibration, so the newer
    claim wins and the older is superseded regardless of confidence (unlike the
    confidence-driven :func:`.revision.select_verified_revision_target`).

    Returns the first such partner (pairwise clashes have one; a 3+-value pileup is
    resolved one partner per beat, ADR-0064), or ``None`` when ``node_id`` is not a
    functional atom or has no conflicting partner.

    Carries the same arity floor as the two clause synthesizers: supersession is
    "the subject moved", and below :data:`FUNCTIONAL_MIN_ARITY` there is no
    subject to have moved --- the partner would be a claim about someone else.
    """
    functional = frozenset(functional_predicates)
    if not functional:
        return None
    atom = parse_atom(node_id)
    if atom is None:
        return None
    predicate, args = atom.predicate, atom.args
    if predicate not in functional or len(args) < FUNCTIONAL_MIN_ARITY:
        return None

    for other_id, data in beliefs.items():
        if other_id == node_id or not _is_true(data):
            continue
        other = parse_atom(other_id)
        if other is None:
            continue
        other_pred, other_args = other.predicate, other.args
        if (
            other_pred == predicate
            and len(other_args) == len(args)
            and other_args[:-1] == args[:-1]
            and other_args[-1] != args[-1]
        ):
            return other_id, data
    return None


__all__ = [
    "PredicateConstraints",
    "PredicateLink",
    "backward_implication_clauses",
    "functional_exclusion_clauses",
    "functional_exclusion_partner",
    "implication_clauses",
    "inter_predicate_exclusion_clauses",
    "predicate_clauses",
]
