"""The shape of an atom.

A belief's identity is its expression string -- ``mortal(socrates)`` -- and
several parts of the library need to read that string the same way: the
predicate, its arity, its arguments. One parser, so two callers can never
disagree about what an atom is.
"""

from doxa.syntax.atoms import FUNCTIONAL_MIN_ARITY, ParsedAtom, parse_atom

__all__ = [
    "FUNCTIONAL_MIN_ARITY",
    "ParsedAtom",
    "parse_atom",
]
