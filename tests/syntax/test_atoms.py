"""Unit tests for the ground-atom grammar the vocabulary asset owns (ADR-0123)."""

from __future__ import annotations

from doxa.syntax import parse_atom
from doxa.syntax.atoms import meaningful_tokens, shares_name_token


class TestParseAtom:
    def test_round_trips_common_forms(self) -> None:
        assert parse_atom("p(a)") == parse_atom("p(a)")
        one = parse_atom("mortal(socrates)")
        assert one is not None
        assert one.predicate == "mortal"
        assert one.args == ("socrates",)
        assert one.arity == 1
        assert one.key() == "mortal/1"

    def test_splits_and_trims_multiple_args(self) -> None:
        two = parse_atom("lives_in(  x ,  tokyo )")
        assert two is not None
        assert two.predicate == "lives_in"
        assert two.args == ("x", "tokyo")
        assert two.arity == 2

    def test_arity_zero(self) -> None:
        nullary = parse_atom("raining()")
        assert nullary is not None
        assert nullary.args == ()
        assert nullary.arity == 0

    def test_malformed_returns_none(self) -> None:
        assert parse_atom("not an atom") is None
        assert parse_atom("") is None
        assert parse_atom("p(a") is None

    def test_retains_non_ascii_argument_term(self) -> None:
        # The parse keeps katakana verbatim (romanization is Decision B's job,
        # not the parser's -- ADR-0038).
        parsed = parse_atom("cartographer(エロウェン・ヴァスク)")
        assert parsed is not None
        assert parsed.args == ("エロウェン・ヴァスク",)


class TestMeaningfulTokens:
    """The name-token rule RFC-0078 moved here from ``evals/bridge_extraction``."""

    def test_splits_a_snake_case_name_and_drops_the_short_words(self) -> None:
        assert meaningful_tokens("is_contract_defining_attribution") == frozenset(
            {"contract", "defining", "attribution"},
        )

    def test_a_name_of_only_short_tokens_has_none(self) -> None:
        """``is_a`` cannot be compared. Every caller has to be able to see that, so it is empty, not absent."""
        assert meaningful_tokens("is_a") == frozenset()

    def test_the_minimum_length_is_three(self) -> None:
        """Pinned absolutely, not as ``_MIN_NAME_TOKEN``: a relative check slides with the constant (ADR-0145)."""
        assert meaningful_tokens("of_the_cat") == frozenset({"the", "cat"})
        assert meaningful_tokens("at_a_b") == frozenset()

    def test_digits_count_and_case_is_folded(self) -> None:
        assert meaningful_tokens("Rule42Applies") == frozenset({"rule42applies"})
        assert meaningful_tokens("rule_42x") == frozenset({"rule", "42x"})


class TestSharesNameToken:
    def test_a_prefixed_respelling_shares_its_stem(self) -> None:
        assert shares_name_token("is_mortal", "mortal")

    def test_synonyms_that_look_nothing_alike_do_not(self) -> None:
        """The signal is weak by construction, and the docstring forbids reading it as synonymy."""
        assert not shares_name_token("dead", "deceased")

    def test_unrelated_names_that_share_a_stem_do(self) -> None:
        """The other half of the same weakness: sharing a token is not sufficient either."""
        assert shares_name_token("contains_text", "contains_bug")

    def test_a_name_with_nothing_to_share_shares_nothing_with_itself(self) -> None:
        """Empty tokens must not intersect vacuously --- ``is_a`` would otherwise match every name."""
        assert not shares_name_token("is_a", "is_a")
        assert not shares_name_token("is_a", "mortal")
