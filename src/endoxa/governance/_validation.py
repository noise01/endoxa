"""Shared validation of explicit ground inputs, without historical records."""

import math
import re

from endoxa.errors import InvalidArgumentError, RuleSyntaxError

_NAME = r"[a-z][a-zA-Z0-9_]*"
_FACT = re.compile(rf"\s*{_NAME}(?:\(\s*{_NAME}(?:\s*,\s*{_NAME})*\s*\))?\s*")


def canonical_atom(text: str) -> str:
    """Return a flat ground atom with whitespace removed.

    Accept a bare proposition or a predicate with one or more simple ground
    arguments. Names start with an ASCII lowercase letter, followed by ASCII
    letters, digits or underscores. Whitespace may surround the atom and
    arguments, but cannot separate a predicate name from its opening parenthesis.
    Raise RuleSyntaxError for invalid syntax or a non-string input.
    """
    if not isinstance(text, str) or _FACT.fullmatch(text) is None:
        msg = f"Expected a flat ground atom, got {text!r}"
        raise RuleSyntaxError(msg)
    return re.sub(r"\s+", "", text)


def validate_confidence(value: float) -> None:
    """Return None for a finite int or float in [0, 1], excluding bool.

    Raise InvalidArgumentError for an invalid value; do not convert the input.
    """
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or not 0.0 <= value <= 1.0
    ):
        msg = "Explicit confidence must be a finite number between 0 and 1"
        raise InvalidArgumentError(msg)


def validate_id(value: str) -> None:
    """Return None for a string containing at least one non-whitespace character.

    Raise InvalidArgumentError otherwise. Whitespace is checked, not stripped
    from the caller's ID; Assertion preserves the original value.
    """
    if not isinstance(value, str) or not value.strip():
        msg = "An ID must be a nonempty string"
        raise InvalidArgumentError(msg)
