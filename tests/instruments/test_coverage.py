from doxa.instruments.coverage import (
    build_predicate_graph,
    compute_coverage_snapshot,
    rule_antecedent_links,
)
from doxa.solver import parse_fof

# --- Unit: predicate adjacency graph (coverage/graph.py) ---------------


def test_single_rule_connects_its_predicates() -> None:
    """A rule mentioning two predicates connects them by an edge."""
    _name, _role, expr = parse_fof("fof(rule_mortal, axiom, ![X] : (human(X) => mortal(X))).")
    graph = build_predicate_graph([expr])
    assert set(graph.nodes) == {"human", "mortal"}
    assert graph.has_edge("human", "mortal")


def test_rule_with_single_predicate_is_isolated_node() -> None:
    """A rule mentioning only one predicate still contributes it as a node, with no edges."""
    _name, _role, expr = parse_fof("fof(fact, axiom, human(socrates)).")
    graph = build_predicate_graph([expr])
    assert set(graph.nodes) == {"human"}
    assert graph.number_of_edges() == 0


def test_disjoint_rules_form_separate_components() -> None:
    """Two rules sharing no predicate form two separate connected components."""
    _n1, _r1, expr1 = parse_fof("fof(r1, axiom, ![X] : (human(X) => mortal(X))).")
    _n2, _r2, expr2 = parse_fof("fof(r2, axiom, ![X] : (bird(X) => flies(X))).")
    graph = build_predicate_graph([expr1, expr2])
    assert set(graph.nodes) == {"human", "mortal", "bird", "flies"}
    assert not graph.has_edge("human", "bird")


def test_connectives_are_not_predicate_symbols() -> None:
    """And/Or/Not/Eq/Implies never show up as predicate-graph nodes themselves."""
    _name, _role, expr = parse_fof("fof(rule, axiom, ![X] : ((human(X) & wise(X)) => mortal(X))).")
    graph = build_predicate_graph([expr])
    assert set(graph.nodes) == {"human", "wise", "mortal"}


# --- Unit: directed rule links (coverage/graph.py) -----------


def test_rule_antecedent_links_recovers_implication_direction() -> None:
    """An implication maps its consequent predicate back to its antecedent."""
    _name, _role, expr = parse_fof("fof(rule_deep_dangerous, axiom, ![X] : (deep(X) => dangerous(X))).")
    assert rule_antecedent_links([expr]) == {"dangerous": {"deep"}}


def test_rule_antecedent_links_handles_conjunctive_antecedent() -> None:
    """Both conjuncts of a compound antecedent map to the consequent."""
    _name, _role, expr = parse_fof("fof(rule, axiom, ![X] : ((human(X) & wise(X)) => mortal(X))).")
    assert rule_antecedent_links([expr]) == {"mortal": {"human", "wise"}}


def test_rule_antecedent_links_bare_fact_has_no_antecedent() -> None:
    """A bare fact axiom is a lone positive predicate with an empty antecedent set."""
    _name, _role, expr = parse_fof("fof(fact, axiom, human(socrates)).")
    assert rule_antecedent_links([expr]) == {"human": set()}


def test_rule_antecedent_links_merges_across_rules() -> None:
    """Antecedents from multiple rules sharing a consequent are unioned."""
    _n1, _r1, e1 = parse_fof("fof(r1, axiom, ![X] : (wet(X) => slippery(X))).")
    _n2, _r2, e2 = parse_fof("fof(r2, axiom, ![X] : (icy(X) => slippery(X))).")
    assert rule_antecedent_links([e1, e2]) == {"slippery": {"wet", "icy"}}


# --- Unit: coverage snapshot (coverage/snapshot.py) --------------------


def test_linked_predicate_is_reported_as_linked() -> None:
    """A belief-set predicate connected by a rule is linked, not isolated."""
    _name, _role, expr = parse_fof("fof(rule_mortal, axiom, ![X] : (human(X) => mortal(X))).")
    snapshot = compute_coverage_snapshot([expr], frozenset({"human(socrates)"}))
    assert snapshot.linked_predicates == frozenset({"human"})
    assert snapshot.isolated_predicates == frozenset()
    assert snapshot.linked_ratio == 1.0
    assert snapshot.rule_count == 1


def test_isolated_predicate_is_reported_as_isolated() -> None:
    """A belief-set predicate absent from any rule is isolated -- a candidate for a new rule."""
    _name, _role, expr = parse_fof("fof(rule_mortal, axiom, ![X] : (human(X) => mortal(X))).")
    snapshot = compute_coverage_snapshot(
        [expr],
        frozenset({"human(socrates)", "likes_wine(socrates)"}),
    )
    assert snapshot.linked_predicates == frozenset({"human"})
    assert snapshot.isolated_predicates == frozenset({"likes_wine"})
    assert snapshot.linked_ratio == 0.5


def test_connected_components_counts_the_rule_graph_itself() -> None:
    """connected_components measures the rule graph's own fragmentation, not just observed predicates."""
    _n1, _r1, expr1 = parse_fof("fof(r1, axiom, ![X] : (human(X) => mortal(X))).")
    _n2, _r2, expr2 = parse_fof("fof(r2, axiom, ![X] : (bird(X) => flies(X))).")
    snapshot = compute_coverage_snapshot([expr1, expr2], frozenset({"human(socrates)"}))
    assert snapshot.connected_components == 2


def test_linked_ratio_is_none_at_zero_denominator() -> None:
    """Rate is undefined, not a divide-by-zero, when the belief set has no predicates yet."""
    snapshot = compute_coverage_snapshot([], frozenset())
    assert snapshot.linked_ratio is None
    assert snapshot.connected_components == 0
    assert snapshot.rule_count == 0


def test_unparseable_belief_expr_is_ignored() -> None:
    """A belief set node ID that isn't a simple name(args) atom contributes no predicate."""
    _name, _role, expr = parse_fof("fof(rule_mortal, axiom, ![X] : (human(X) => mortal(X))).")
    snapshot = compute_coverage_snapshot([expr], frozenset({"not a valid atom"}))
    assert snapshot.linked_ratio is None
    assert snapshot.isolated_predicates == frozenset()
