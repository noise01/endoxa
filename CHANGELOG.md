# Changelog

Versions follow [semantic versioning](https://semver.org). Before 1.0.0 a release
may move the public API: what it looks like now is where the extraction landed,
not a promise.

## 0.0.1

First release.

The package was lifted whole out of the research system it grew in, where it has
run for months. That is the reason it arrives with a solver, a ledger, revision
and instruments already fitted to each other, and also the reason the version is
0.0.1: it has been used by exactly one host, and an API that only ever answered
to one caller has not been tested as an API.

What is in it:

- `syntax` — the shape of an atom: predicate, arity, arguments.
- `solver` — a bundled SMT engine over uninterpreted functions and equality, with
  a deliberation budget that returns *unknown* rather than running forever. Its
  answers are asserted differentially against Z3 in dev-only tests.
- `governance` — the append-only ledger and the view folded from it, defeasible
  revision (what to blame, what may be given up, and when a conflict is genuinely
  unsettleable), and where a belief came from.
- `trace` — the ordered series of an agent's propositions. Optional; needs
  `endoxa[trace]`.
- `instruments` — calibration over knowledge, competence and the choice to ask,
  and how densely rules connect predicates. Optional for the latter, which needs
  `endoxa[coverage]`.

Known gaps, stated because the tests do not state them: the calibration
accumulators are covered indirectly at best, having been verified through the
host's own suite rather than their own, and `governance.support` records the
footing a belief stands on but was never exercised by the host that shipped it.
