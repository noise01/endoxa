---
type: API reference
title: Atom syntax
description: The dependency-free ground-atom parser used for predicate identity in governance links and coverage measurements.
tags: [syntax, atoms, parsing]
---

# Atom syntax

`endoxa.syntax` is the lowest package layer. Its public API is intentionally small:

- `ParsedAtom(predicate: str, args: tuple[str, ...])`, with `arity` and `key()`;
- `parse_atom(expr: str) -> ParsedAtom | None`;
- `FUNCTIONAL_MIN_ARITY = 2`.

Import from `endoxa.syntax`, not its `atoms` implementation module.

## Contract

`parse_atom` accepts a simple outer shape: an identifier-like predicate followed by parentheses. It trims surrounding whitespace and whitespace around comma-separated arguments. It returns `None` for malformed outer structure rather than raising.

```python
parse_atom("mortal(socrates)").key()  # "mortal/1"
parse_atom("raining()").args          # ()
parse_atom("lives_in( x , tokyo )").args  # ("x", "tokyo")
```

A parsed atom's stable identity is its predicate and **arity**, not its arguments: `ParsedAtom.key()` is `"predicate/arity"`. The parser deliberately treats each argument as an opaque string. It does not build an AST for nested terms, validate the meaning of an argument, or normalize Unicode; non-ASCII content is retained exactly.

## Consumers and change boundary

[Governance revision](../governance/decision-and-revision.md) uses this shallow parser to identify predicate/arity groups when synthesizing functional and predicate-link conflicts. [Coverage](../instruments/coverage.md) uses it to obtain current belief predicates from raw atom strings. The solver has a separate TPTP parser and AST; do not expand `parse_atom` into a solver parser merely to share syntax.

`FUNCTIONAL_MIN_ARITY` is `2` because functional exclusion compares claims with a shared leading subject portion and different final values. A relation with fewer positions cannot represent that comparison.

## Validation

`tests/syntax/test_atoms.py` pins whitespace trimming, zero-arity atoms, malformed input returning `None`, `predicate/arity` keys, and lossless non-ASCII argument handling.

```bash
uv run pytest tests/syntax/test_atoms.py -q
```