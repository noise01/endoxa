"""Public input validators agree with Assertion without fixing error wording or order."""

import math
from typing import get_type_hints

import pytest

from endoxa import governance
from endoxa.errors import InvalidArgumentError, RuleSyntaxError
from endoxa.governance import Assertion, canonical_atom, validate_confidence, validate_id


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ready", "ready"),
        (" ready \n", "ready"),
        ("p(a)", "p(a)"),
        (" p( a , b ) ", "p(a,b)"),
        ("p(\ta,\nb\t)", "p(a,b)"),
        ("p1_A(aB_2,c3)", "p1_A(aB_2,c3)"),
    ],
)
def test_canonical_atom_returns_normalized_atom_used_by_assertion(text, expected):
    assert canonical_atom(text) == expected
    assert canonical_atom(expected) == expected
    assert Assertion(id="claim", atom=text, truth_value=True, confidence=0.5).atom == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        " \t\n",
        "P(a)",
        "p(X)",
        "p()",
        "p(f(a))",
        "p(a,b,)",
        "p(a) tail",
        "p (a)",
        "p(a b)",
        "p(a).",
        "~p(a)",
        "p(a) & q(b)",
        "p(1)",
        "p('a')",
        "p(é)",
        "_p",
        None,
        1,
        True,
        [],
    ],
)
def test_invalid_atom_raises_rule_syntax_error_for_validator_and_assertion(text):
    with pytest.raises(RuleSyntaxError):
        canonical_atom(text)
    with pytest.raises(RuleSyntaxError):
        Assertion(id="claim", atom=text, truth_value=True, confidence=0.5)


@pytest.mark.parametrize("value", ["id", " id ", "\tid\n", "a b", "識別子", "0"])
def test_validate_id_returns_none_and_assertion_preserves_value(value):
    assert validate_id(value) is None
    assert Assertion(id=value, atom="ready", truth_value=True, confidence=0.5).id == value


@pytest.mark.parametrize("value", ["", " ", "\t\n", "\u2003", None, 0, True, [], {}])
def test_invalid_id_raises_invalid_argument_for_validator_and_assertion(value):
    with pytest.raises(InvalidArgumentError):
        validate_id(value)
    with pytest.raises(InvalidArgumentError):
        Assertion(id=value, atom="ready", truth_value=True, confidence=0.5)


@pytest.mark.parametrize("value", [0, 1, 0.0, -0.0, 0.5, 1.0, math.nextafter(0.0, 1.0), math.nextafter(1.0, 0.0)])
def test_validate_confidence_returns_none_and_assertion_preserves_value(value):
    assert validate_confidence(value) is None
    assert Assertion(id="claim", atom="ready", truth_value=True, confidence=value).confidence is value


@pytest.mark.parametrize(
    "value",
    [
        math.nextafter(0.0, -math.inf),
        math.nextafter(1.0, math.inf),
        -1,
        2,
        math.nan,
        math.inf,
        -math.inf,
        True,
        False,
        "0.5",
        None,
        [],
        complex(0.5),
    ],
)
def test_invalid_confidence_raises_invalid_argument_for_validator_and_assertion(value):
    with pytest.raises(InvalidArgumentError):
        validate_confidence(value)
    with pytest.raises(InvalidArgumentError):
        Assertion(id="claim", atom="ready", truth_value=True, confidence=value)


@pytest.mark.parametrize(
    ("validator", "hints"),
    [
        (canonical_atom, {"text": str, "return": str}),
        (validate_id, {"value": str, "return": type(None)}),
        (validate_confidence, {"value": float, "return": type(None)}),
    ],
)
def test_public_validators_are_exported_with_resolvable_annotations(validator, hints):
    assert validator.__name__ in governance.__all__
    assert getattr(governance, validator.__name__) is validator
    assert get_type_hints(validator) == hints
