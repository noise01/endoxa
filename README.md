# endoxa

**Governed beliefs for agents.** An append-only ledger, SMT-checked consistency,
defeasible revision, and calibration instruments — a layer you give an agent,
not a framework you build one inside.

> **Status: pre-alpha.** The library was extracted whole from the research system
> it grew in, where it has run for months. Versions before 1.0 may move the public
> API: what is shown below is where the extraction landed, not a promise.

## The problem

An LLM agent will tell you Socrates is mortal, and twenty turns later that he is
immortal, and never notice. It has no place to put a claim other than its own
context, no way to check a new claim against the ones it already made, and no
record of why it believes any of them. Asking it to be consistent is asking the
thing that lost track to keep track.

endoxa is the place to put them.

## What it does

- **Checks.** Beliefs and the rules they live under go to a bundled SMT solver,
  which answers satisfiable, unsatisfiable, or *unknown* when its deliberation
  budget runs out — a real answer, not a failure.
- **Decides.** On a conflict it finds what is actually to blame and orders the
  candidates by how readily each may be given up. A rule the agent *learned* may
  be retracted; a rule it was given may not.
- **Holds.** When two beliefs are equally credible, the conflict cannot be
  settled from the inside. That is a state with a name, not a coin flip.
- **Records.** Every operation is an entry in an append-only ledger. A retracted
  belief keeps its row and stops counting, so the history of what the agent
  believed survives the change.
- **Measures.** Whether the agent's confidence matched its accuracy, over what it
  claims to know, what it claims to be able to do, and when it chooses to ask.

## Example

```python
from endoxa.governance import Belief, Constraints, Rule, govern

constraints = Constraints(
    rules=(
        Rule(
            name="mortality",
            axiom="fof(m, axiom, ![X]: (human(X) => mortal(X))).",
            confidence=0.9,
        ),
    ),
)
beliefs = [
    Belief(target="human(socrates)", truth_value=True, confidence=1.0, context="user"),
    Belief(target="mortal(socrates)", truth_value=False, confidence=0.6, context="agent"),
]

outcome = govern(beliefs, constraints)

outcome.consistent  # False

# The operations to perform, in order: here, retracting the 0.6-confidence
# claim -- not the rule, and not the one the user asserted.
outcome.ops
```

`govern` decides; it does not mutate. The operations it returns are what you
append to the ledger and apply to your own store.

Three runnable scripts go further — what happens over a run of turns, what a
conflict that cannot be settled looks like, and what the instruments report. See
[examples/](examples/).

## Install

**Requires Python 3.14 or newer.** That floor is real rather than cautious: the
package is written in 3.14 syntax and will not parse on an older interpreter. If
`pip` declines to install this, that is why.

```bash
pip install endoxa
```

The core takes one dependency. Two packages need more and are opt-in:

```bash
pip install "endoxa[trace]"     # the ordered series of an agent's propositions
pip install "endoxa[coverage]"  # how densely rules connect predicates
```

## Design notes

- **The solver is bundled and frozen.** endoxa answers about consistency without
  reaching for an external prover. Its verdicts are checked against Z3's over
  generated formulas in two fragments — propositional, and equality with
  uninterpreted functions — chosen because both solvers are *complete* on them, so
  a disagreement is a bug rather than an artefact of one giving up first.
  Quantifier instantiation sits outside that on purpose: it is anytime, and
  answers `UNKNOWN` when its budget runs out, which is a correct answer and not
  one a verdict comparison can score. That part has ordinary tests instead. The
  differential needs Z3, which is a dev dependency and is not shipped.
- **The ledger is the record, not a cache.** Operations are appended; the current
  view is folded from them. An unsettleable conflict appears in that view as
  `UNRESOLVED` rather than as a silent choice.
- **Instruments are imported by nothing else.** A measure its subject can reach
  is a measure its subject can move, so the dependency is forbidden by contract
  and checked in CI.
- **One name catches everything this raises.** `endoxa.errors.EndoxaError` is the
  base of every error the library raises on its own behalf, and no dependency's
  exceptions reach past the boundary — a malformed rule is a `RuleSyntaxError`,
  not the grammar library's business. Each class is also the built-in you would
  have reached for anyway, so `except ValueError` keeps working.
- **Requires Python 3.14+.**

## Issues

Issues are open and they are read. What is not offered is a response time: this
is one person's pre-alpha library, so a report may sit for a while and a pull
request may sit longer. Filing one is still the best way to move something up
the list — what is reported is what gets looked at first.

Security reports go through [private advisories](https://github.com/noise01/endoxa/security/advisories/new)
rather than public issues. See [SECURITY.md](SECURITY.md).

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
