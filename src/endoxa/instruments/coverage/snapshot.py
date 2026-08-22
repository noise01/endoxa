"""A coherent, point-in-time view of how far the rules cover the belief set.

Pure data aggregation only: ``CoverageSnapshot`` bundles the
predicate adjacency graph (``graph.py``) with the predicate set currently
asserted in the belief set, without introducing new inference logic. The
wiring that populates it lives in a host.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import networkx as nx

from endoxa.instruments.coverage.graph import build_predicate_graph
from endoxa.syntax.atoms import parse_atom

if TYPE_CHECKING:
    from collections.abc import Sequence

    from endoxa.solver import Expr


@dataclass(slots=True, frozen=True)
class CoverageSnapshot:
    """A single, coherent read of the axiom network's static coverage.

    Attributes:
        linked_ratio: Fraction of belief set predicates connected to at least
            one rule, or ``None`` when the belief set has no predicates yet
            (zero-denominator convention, matching :mod:`endoxa.instruments.calibration`).
        connected_components: Number of connected components in the rule
            adjacency graph itself -- a static measure of how fragmented the
            axiom network is, independent of what's currently in the
            belief set.
        isolated_predicates: Belief-set predicates with no rule connecting
            them to any other predicate -- the first candidates for a new rule.
        linked_predicates: Belief-set predicates connected to at least one
            other predicate by a rule.
        rule_count: Number of active rules (base axioms plus active learned
            rules) the graph was built from.
    """

    linked_ratio: float | None
    connected_components: int
    isolated_predicates: frozenset[str]
    linked_predicates: frozenset[str]
    rule_count: int


def compute_coverage_snapshot(rule_exprs: Sequence[Expr], belief_exprs: frozenset[str]) -> CoverageSnapshot:
    """Compute the coverage snapshot from active rules and the beliefs held.

    Args:
        rule_exprs: The parsed logic of every active rule.
        belief_exprs: Raw atom expression strings currently in the
            belief set (node IDs, e.g. ``"human(socrates)"``), from which
            predicate symbols are extracted via
            :func:`~endoxa.syntax.atoms.parse_atom`.

    Returns:
        The aggregate :class:`CoverageSnapshot`.
    """
    graph = build_predicate_graph(rule_exprs)

    belief_predicates: set[str] = set()
    for expr_str in belief_exprs:
        parsed = parse_atom(expr_str)
        if parsed is not None:
            belief_predicates.add(parsed.predicate)

    linked_predicates = frozenset(
        predicate for predicate in belief_predicates if predicate in graph and graph.degree[predicate] > 0
    )
    isolated_predicates = frozenset(belief_predicates - linked_predicates)

    total = len(belief_predicates)
    linked_ratio = len(linked_predicates) / total if total else None

    return CoverageSnapshot(
        linked_ratio=linked_ratio,
        connected_components=nx.number_connected_components(graph),
        isolated_predicates=isolated_predicates,
        linked_predicates=linked_predicates,
        rule_count=len(rule_exprs),
    )
