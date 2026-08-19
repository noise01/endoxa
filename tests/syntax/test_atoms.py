"""Unit tests for the ground-atom grammar."""

from doxa.syntax import parse_atom


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
        # Terms are kept verbatim. Normalising them is a caller's decision, and a
        # parser that quietly transliterated would make two callers disagree
        # about which belief they are talking about.
        parsed = parse_atom("cartographer(エロウェン・ヴァスク)")
        assert parsed is not None
        assert parsed.args == ("エロウェン・ヴァスク",)
