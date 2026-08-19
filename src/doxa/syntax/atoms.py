"""The grammar of a ground atom, owned by the vocabulary asset (RFC-0028 §8, ADR-0123).

A predicate's identity is ``predicate`` + ``arity`` -- the same pair
:class:`~doxa.syntax.atoms.VocabularySymbol` persists under
the natural key ``"{predicate}/{arity}"``. Reading that identity out of an atom
expression string is therefore an operation *of the owned language*, not a
utility of whatever caller happens to need it, and this module is its single
home.

It used to have several. The same ``name(args)`` regex was written out in
:mod:`.propagation` (which said in its own docstring that carrying it there was a
first landing awaiting this consolidation), in ``domains/memory/vocabulary``
(likewise), and in ``domains/perception/vocabulary``, which additionally modelled
the identity a second time as a ``PredicateSignature`` dataclass. ADR-0123
retired all three in favour of :class:`ParsedAtom` and :func:`parse_atom`, which
were already the form the blackboard, the actuator and unit propagation used.

Pure and basis-independent: stdlib only, and it imports nothing from the rest of
the asset, so it sits below every other vocabulary module.

Two variants remain outside. ``kernel/governance/tms`` carried three; the one whose
pattern was character-for-character this one (``exclusion``) folded in when tms
moved into the kernel (ADR-0125). ``facts`` and ``revision`` did not: their regex
tolerates no whitespace around the parenthesis and their argument split drops
empty terms, so ``p (a)`` and ``p(a,,b)`` mean different things to them than to
:func:`parse_atom`. Folding those two would *widen* the grammar the belief-revision
path accepts -- a judgement about behaviour rather than a move (ADR-0123 known
limitation (a)).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: A ground ``name(args)`` atom. Terms are not parsed further -- the blackboard
#: holds ground atoms and compares terms as strings.
_PREDICATE_PATTERN = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)\)\s*$")

#: One word inside a predicate name, once the name is lowercased.
_NAME_WORD = re.compile(r"[a-z0-9]+")

#: The shortest token of a predicate name that means anything on its own.
#: ``as``, ``of``, ``in`` and ``is`` are English function words; requiring them
#: would make "these two names have something in common" a test of grammar.
_MIN_NAME_TOKEN = 3


@dataclass(frozen=True, slots=True)
class ParsedAtom:
    """A ground atom split into predicate and argument terms."""

    predicate: str
    args: tuple[str, ...]

    @property
    def arity(self) -> int:
        """Number of argument terms."""
        return len(self.args)

    def key(self) -> str:
        """Return the ``predicate/arity`` natural key (matches :meth:`VocabularySymbol.key`)."""
        return f"{self.predicate}/{self.arity}"


def parse_atom(expr: str) -> ParsedAtom | None:
    """Parse ``"name(a, b)"`` into a :class:`ParsedAtom`, or ``None`` if malformed.

    Arity-0 atoms (``"p()"``) yield an empty argument tuple. Argument terms are
    whitespace-trimmed; nested structure is not parsed (terms are compared as
    strings), which suffices for the ground atoms the blackboard holds.
    """
    match = _PREDICATE_PATTERN.match(expr)
    if match is None:
        return None
    args_str = match.group(2).strip()
    args = tuple(part.strip() for part in args_str.split(",")) if args_str else ()
    return ParsedAtom(predicate=match.group(1), args=args)


def meaningful_tokens(predicate: str) -> frozenset[str]:
    """Return the tokens of a predicate's name long enough to mean anything on their own.

    A name's tokens are part of the owned language's identity, which is why this
    sits beside :func:`parse_atom` rather than in whichever caller needed it
    first. It was written first in ``evals/bridge_extraction/gloss_census.py``,
    as a diagnosis of how far a coined name sits from the text it came from; that
    module now imports it from here, because RFC-0078 made the same question part
    of a decision the gate takes and **two spellings of "which parts of the name
    count" would let the fix and the diagnosis disagree while both looked right**
    (ADR-0128).

    Returns an empty set for a name made entirely of short tokens (``is_a``).
    That emptiness is load-bearing in every caller and none may swallow it: it
    means the name cannot be compared, which is different from comparing it and
    finding nothing in common.
    """
    return frozenset(token for token in _NAME_WORD.findall(predicate.lower()) if len(token) >= _MIN_NAME_TOKEN)


def shares_name_token(left: str, right: str) -> bool:
    """Whether two predicate names have a meaningful token in common.

    **Not a synonymy test, and no caller may use it as one.** ``dead`` and
    ``deceased`` share nothing and mean the same; ``contains_text`` and
    ``contains_bug`` share a token and do not. What it reports is a weak,
    embedding-independent signal that two names are about the same thing --- weak
    on purpose, since its whole value is that it shares no machinery with the
    criterion it sits beside (RFC-0078 §2-1).
    """
    return bool(meaningful_tokens(left) & meaningful_tokens(right))


#: The lowest arity at which a functional-exclusion link can mean anything: a
#: predicate whose last argument is a value needs at least one argument before it.
#: One constant, because a rule about what a link *means* cannot hold on one path
#: and not another.
FUNCTIONAL_MIN_ARITY = 2
