"""Predicate adjacency extraction for the rule-network coverage instrument.

Pure and side-effect-free: builds a graph connecting the predicate symbols that
co-occur in the same active inference rule, so the network's density can be
measured against the predicates actually asserted on the belief set. Supplying
the rules and the belief set is the host's; reading the shape they make is this.
"""

from collections.abc import Sequence
from itertools import combinations
from typing import TYPE_CHECKING

import networkx as nx

from endoxa.solver import BOOL_SORT, App, Expr

# ``nx.Graph`` is generic to a type checker and a plain class at runtime, so
# ``nx.Graph[str]`` in a signature raises when anything reads the annotations
# back -- and this package ships ``py.typed``, which is a promise that they can
# be read. The alias is the usual way out: subscripted where it is checked,
# bare where it is evaluated.
if TYPE_CHECKING:
    PredicateGraph = nx.Graph[str]
else:
    PredicateGraph = nx.Graph

# Connective/equality declaration names that are never predicate symbols, even
# though they're Bool-sorted applications like any predicate.
# ``Implies`` desugars to ``Or(Not(p), q)`` at construction time
# (:mod:`endoxa.solver`), so it never appears as its own node.
_NON_PREDICATE_DECLS = frozenset({"And", "Or", "Not", "Eq"})


def _predicate_symbols(expr: Expr) -> set[str]:
    """Collect the predicate symbols appearing anywhere in ``expr``.

    Walks the AST via ``Expr.children`` (quantifiers descend into their body,
    applications descend into their arguments) and treats any Bool-sorted
    ``App`` node whose declaration isn't a logical connective or equality as a
    predicate symbol, identified by its declaration name -- granularity is the
    symbol, and arity is ignored. Function/constant
    applications (e.g. ``socrates``) are term-sorted, not Bool-sorted, so
    they're excluded without needing a name-based allowlist.
    """
    symbols: set[str] = set()
    stack = [expr]
    while stack:
        node = stack.pop()
        if isinstance(node, App) and node.sort is BOOL_SORT and node.decl.name not in _NON_PREDICATE_DECLS:
            symbols.add(node.decl.name)
        stack.extend(node.children)
    return symbols


def _split_by_polarity(expr: Expr) -> tuple[set[str], set[str]]:
    """Split a rule's predicate symbols into (antecedents, consequents) by polarity.

    ``Implies`` desugars to ``Or(Not(p), q)`` at construction (:mod:`endoxa.solver`),
    so an implication rule ``p(X) => q(X)`` becomes ``Or(Not(p(X)), q(X))``: the
    antecedent predicate sits under a ``Not`` (negative polarity) and the consequent
    is bare (positive polarity). Walking the AST while tracking how many ``Not`` nodes
    enclose each predicate recovers the direction that :func:`build_predicate_graph`
    (undirected) discards. A predicate at negative polarity is an
    antecedent, at positive polarity a consequent; a bare fact axiom contributes a
    single positive (consequent) predicate with no antecedents.
    """
    antecedents: set[str] = set()
    consequents: set[str] = set()
    stack: list[tuple[Expr, bool]] = [(expr, True)]
    while stack:
        node, positive = stack.pop()
        if isinstance(node, App) and node.sort is BOOL_SORT and node.decl.name not in _NON_PREDICATE_DECLS:
            (consequents if positive else antecedents).add(node.decl.name)
            continue  # arguments are term-sorted; no nested predicates to visit
        flip = isinstance(node, App) and node.decl.name == "Not"
        child_polarity = not positive if flip else positive
        stack.extend((child, child_polarity) for child in node.children)
    return antecedents, consequents


def rule_antecedent_links(rule_exprs: Sequence[Expr]) -> dict[str, set[str]]:
    """Map each rule consequent predicate to the antecedent predicates that imply it.

    Reverses the implication direction so a caller holding a consequent atom
    (e.g. a lie negating ``dangerous(x)``) can find the antecedent predicate
    (``deep``) whose atom must be co-present for the cross-atom SMT contradiction
    to form, which is what restoring an evicted antecedent into the consistency
    check needs. Directionality is recovered via :func:`_split_by_polarity`.

    Args:
        rule_exprs: The parsed logic of every active rule.

    Returns:
        A mapping of consequent predicate name to the set of antecedent predicate
        names across all rules. A predicate appearing only as a bare fact axiom
        maps to an empty set.
    """
    links: dict[str, set[str]] = {}
    for expr in rule_exprs:
        antecedents, consequents = _split_by_polarity(expr)
        for consequent in consequents:
            links.setdefault(consequent, set()).update(antecedents)
    return links


def build_predicate_graph(rule_exprs: Sequence[Expr]) -> PredicateGraph:
    """Build an undirected adjacency graph of predicate symbols.

    Two predicate symbols are connected if they co-occur in the same rule
    : every rule contributes a clique over the predicate
    symbols it mentions. A rule mentioning a single predicate (or none)
    contributes that predicate as an isolated node rather than no edge, so it
    still shows up in the graph's node set.

    Args:
        rule_exprs: The parsed logic of every active rule (base axioms and
            active learned rules).

    Returns:
        A graph whose nodes are predicate symbol names.
    """
    graph: PredicateGraph = nx.Graph()
    for expr in rule_exprs:
        symbols = _predicate_symbols(expr)
        graph.add_nodes_from(symbols)
        graph.add_edges_from(combinations(sorted(symbols), 2))
    return graph
