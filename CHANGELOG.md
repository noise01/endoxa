# Changelog

Versions follow [semantic versioning](https://semver.org). Before 1.0.0 a release
may move the public API: what it looks like now is where the extraction landed,
not a promise.

## 0.2.0

Two modules that could not be reached are gone, and a type checker now runs in
CI. The checker was the interesting half: it found a loop that could not
terminate and a comparison that could never be false, neither of which any test
was ever going to reach.

### Removed

- **`governance.provenance`** and **`solver.parsers.dimacs`**. Neither was
  exported, neither was imported anywhere in the package, and neither had a test
  — 118 lines that ran on no path. `dimacs` was also the only function here that
  read a file, in a package whose security policy names untrusted input reaching
  a parser as one of its two problem shapes; a parser nothing calls is a surface
  with no purpose. The suite passes unchanged without them, which is the whole
  argument for the removal.

### Fixed

- **A congruence merge with no terms named was a non-terminating loop.** An edge
  in the equality graph carries the two terms whose equality it rests on, and the
  explanation walk reads them back. The edge type allowed them to be absent, and
  the walk defended itself with a guard that skipped such an edge *without
  advancing to the next one*. Nothing ever built such an edge, so nothing ever
  hung; the guard was reachable only in a state no caller could produce. It is
  refused at the write now, the type no longer admits it, and the guard is gone.
- **A quantifier was rebuilt on every substitution, including the ones that
  changed nothing.** The walk decided whether to rebuild by comparing a freshly
  built *list* of patterns against the stored *tuple* of them. A list is never
  equal to a tuple however their contents match, so the test was true on every
  pass. Hash-consing returned the identical object either way, which is why this
  was invisible to every test and why the test added for it asserts that the
  rebuild does not happen rather than what came back.
- **A SAT preprocessing check could never fire.** `[[]] in clauses` asked whether
  a list-of-lists was an element of a list of clauses. The `[] in clauses` beside
  it is the one that means UNSAT.
- **Three type suppressions suppressed nothing.** Two in `governance.derive` were
  malformed — trailing prose after the error code makes the comment invalid, and
  a checker reads it as a syntax error rather than as an instruction. A third
  named a checker that is not among this project's dependencies. All three are
  replaced by the narrowing they were standing in for.
- **The TPTP transformer's annotations described the wrong things.** `term_list`
  and `app_term` were typed as receiving tokens; by the time they run, the
  grammar has already transformed their children into expressions.

### Changed

- **`mypy --strict` runs in CI**, over `src/endoxa`. Strict is what turns
  `warn_unused_ignores` on, which is the setting that would have caught the
  suppressions above the day they were written. The tests are deliberately out of
  scope: they carry untyped fixtures, private access and planted violations on
  purpose.
- **`ForAll` and `Exists` take a `Sequence[Expr]`** rather than a `list[Expr]`.
  They only iterate it. A `list` parameter is invariant, so a caller holding a
  `list` of a subclass could not pass it.
- **`SATSolver` and `SMTEngine` take a `Callbacks`** — `dict[str, Callable]`,
  named in `solver.sat.types` alongside the rest of the search vocabulary —
  rather than a bare `dict`. `Trail` takes an `AssignHook` with the signature it
  actually calls.
- **`mk_bound_var` returns a `BoundVar`**, not the `Expr` the shared hash-cons
  cache is typed to return.
- **`FuncDecl` is imported from `solver.ast.expr`**, where it is defined, rather
  than from `solver.ast.context`, which only imports it. Unchanged for anyone
  importing it from `endoxa.solver`, which is where the README says to.

## 0.1.1

The extraction took the host's names out and did not always repair the sentences
around them. This release is that repair, and a set of checks so the next removal
cannot pass unnoticed.

- **Prose the redaction broke.** A tie that "surfaced only as a warning log in a
  warning log". A parenthetical emptied of its contents, leaving ``(..)``. A
  clause ending "extended to revision selection by", with nothing after the "by".
  Lines holding nothing but a full stop, where a citation used to end the
  sentence. And a singular noun replaced by the plural "beliefs" in nineteen
  places, so the docstrings read "the beliefs's own test" and "what the beliefs
  does". Repaired throughout.
- **References a reader could not follow.** Cross-references into modules that
  exist only in the host (``.propagation.propagate``,
  ``.memory._build_exclusion_links``, ``EventStore.get_by_types``); an ``:attr:``
  still pointing at ``BeliefState.state`` after that field was renamed to
  ``status``; section marks with no document named ("§2.10"); a decision record
  cited without its number ("Three RFCs settled on holding both"); and
  ``docs/backlog.md``, which is not in this repository. Each replaced by what it
  was trying to say, or removed.
- **"production" meant the host.** Nine places used the word for the system this
  was extracted from. An outside reader takes it for "production environment",
  which is a different claim entirely.
- **Checks for all of the above, each with a positive control.** The vocabulary
  rules already here ask whether a forbidden word survived the move; these ask
  the harder question they cannot -- whether *removing* one left a readable
  sentence. Added: the four scar shapes above, cross-references that resolve to
  nothing in this package, ADR/RFC named without a number, private document
  names, and the dotted form of a host module path (``modules.reasoning``), which
  the existing rule missed because it was written for slashes.
- **``py.typed``.** The ``Typing :: Typed`` classifier was a claim PEP 561 did
  not back: with no marker file, a downstream type checker ignores every
  annotation in here. Added, shipped in both the wheel and the sdist, and pinned
  by a test that reads the classifier and fails if the marker is missing.
- **The top-level ``__init__`` no longer promises a facade.** It described itself
  as "the facade [the exports] will land in". None is coming, and that is the
  decision rather than an unfinished one: import from the layer you mean, because
  the layer a name belongs to is the most useful thing its address can tell you.

## 0.1.0

No API change. What moved is the evidence for it: of the two thin places 0.0.1
named in its own entry, one is now covered directly and the other turned out not
to be a gap in this package at all.

- **A policy on issues, and a place for security reports.** The tracker is open
  and read, and no response time is offered — an open tracker with nothing
  written next to it implies a maintenance commitment this cannot keep.
  Vulnerabilities go to a private advisory rather than a public issue, and
  `SECURITY.md` names the two shapes a problem here would take: rule text is
  untrusted input reaching a parser, and a consistent belief set is not a true
  one.
- **`examples/`.** Three scripts: a contradiction that only exists under a rule
  and what gives way when it surfaces; a conflict between two equally credible
  claims, which gets a name and an end with an author rather than a coin flip;
  and what the three instruments report about an agent's confidence. Each is run
  by the test suite with the numbers its prose points at asserted, because an
  example nobody executes is a promise nobody keeps.
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
