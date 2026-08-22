# Changelog

Versions follow [semantic versioning](https://semver.org). Before 1.0.0 a release
may move the public API: what it looks like now is where the extraction landed,
not a promise.

## Unreleased

- **Corrected what 0.0.1 said about `governance.support`.** The note claimed the
  module records a belief's footing and that nothing had exercised it. Neither
  half was right. It records nothing: it folds *resolved* support states into a
  verdict, because deciding whether an antecedent is still alive means reading a
  host's state and this package does not know what that state is. And it has had
  a direct test since the port, including the distinction the fold exists for —
  that `out` and `indeterminate` must not collapse, or a paged-out antecedent
  becomes counter-evidence against everything that once rested on it. What is
  true, and what the note should have said, is about traffic rather than
  coverage: see the amended 0.0.1 entry below.
- **The calibration accumulators are tested directly.** They were reachable only
  through the windowed recomputation that folds them, which cannot construct an
  accumulator that has seen nothing and cannot state any of their contracts on
  its own terms. Added: each type asserted directly, the empty states (no
  observations is not a score of zero), the two ask-policy rates that differ
  only in their denominator, the transitions that count as neither direction,
  and the property that folding one observation at a time agrees with computing
  over the whole stream at once. The export list of
  `endoxa.instruments.calibration` is checked against the package both ways.

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
host's own suite rather than their own, and the support fold has coverage but no
traffic — its host calls it on every pass, yet across that host's whole archive
no belief has ever been observed losing its footing, so the branch the fold
exists to get right has never once been taken outside a test.

*(Amended after release: the original wording said this module "records" a
belief's footing and "was never exercised". It records nothing, and it is
tested. The gap is the one stated above. See Unreleased.)*
