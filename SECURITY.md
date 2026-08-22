# Security

Report a vulnerability through a
[private advisory](https://github.com/noise01/endoxa/security/advisories/new)
rather than a public issue, so that a fix can exist before the report does.

## What is supported

The latest release, and only that one. This is a pre-alpha library maintained by
one person: there is no support window, no backport, and no patch schedule. A
fix lands in the next release, whenever that is.

## What this library does and does not do

endoxa decides what to do about beliefs it is given: it checks them against the
rules it is given, and returns the operations to perform. It does not execute
anything, open a network connection, read the filesystem, or hold credentials.

Two things follow that are worth stating, because they are the shape a problem
here would take.

**Rules are code-adjacent input.** An axiom is parsed and handed to a solver. A
rule assembled from text an agent received — a document it read, a message from
a user — is untrusted input reaching a parser, and the deliberation budget is
the only bound on what the solver will spend on it. Treat rule text the way you
would treat a query.

**The answer is about consistency, not about truth.** A belief set can be
perfectly consistent and entirely wrong. Nothing here validates that a belief
corresponds to the world, and a system that reads `consistent` as `correct` is
making a claim this library never made.
