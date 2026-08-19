"""How densely the rules connect the predicates.

A set of predicates nothing relates is a glossary; a set of predicates whose
rules reach one another is a theory. This measures the difference, by reading
the rules as a graph over the predicates they mention.

Requires the ``coverage`` extra.
"""

__all__: list[str] = []
