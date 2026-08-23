"""Two claims that cannot both hold, believed exactly as firmly as each other.

Something has to give and nothing in the belief set says which. A system that
picks one is not deciding, it is guessing and then reporting the guess as a
belief. Here the inability is a state with a name: both sides stay, both are
marked `UNRESOLVED`, and the pair is on the record as a pair.

That is also what makes the state actionable. A held tie is the one situation
where asking is provably worth more than thinking harder, and the hold names
exactly which question to ask.

Run: python examples/02_a_tie_is_not_a_coin_flip.py
"""

from endoxa.governance import Belief, Constraints, LedgerOp, govern, reconstruct_view

# The cat is indoors or outdoors and not both. Handed to the agent rather than
# learned by it, so the rule itself is never a candidate for blame.
EXCLUSIVE = "fof(x, axiom, ~(indoors(cat) & outdoors(cat)))."

pair = [
    Belief(target="indoors(cat)", truth_value=True, confidence=0.6, context="agent"),
    Belief(target="outdoors(cat)", truth_value=True, confidence=0.6, context="agent"),
]

outcome = govern(pair, Constraints(hard_axioms=(EXCLUSIVE,)))

print("consistent:", outcome.consistent)
print("undecided: ", outcome.undecided, " <- a conflict with no operation at all is a different answer")
print()
print("The tie, named:")
print(f"  {outcome.hold.node_a}  vs  {outcome.hold.node_b}")
print(f"  answering yes to the first would affirm: {outcome.hold.affirm_true}")
print(f"  answering no  to the first would affirm: {outcome.hold.affirm_false}")
print()

ledger = [
    LedgerOp(op="assert", target=b.target, actor=b.context, truth_value=b.truth_value, confidence=b.confidence)
    for b in pair
]
ledger += list(outcome.ops)

print("The view holds both, and says so:")
for target, state in sorted(reconstruct_view(ledger).items()):
    print(f"  {target:<15} status={state.status:<11} held_with={state.held_with}")
print()

# Someone answers. Only a grounded answer confers full confidence, which is what
# makes it the operation that always separates a band -- and so the one that can
# always end a hold.
answer = LedgerOp(
    op="ground",
    target="indoors(cat)",
    actor="user",
    truth_value=True,
    confidence=1.0,
    origin_event_id="ask-17",
)
answered = [*ledger, answer]

print("After the answer:")
for target, state in sorted(reconstruct_view(answered).items()):
    print(f"  {target:<15} status={state.status:<11} confidence={state.confidence} released_by={state.released_by}")
print()
print("The hold ended because the preference can separate the pair again, not")
print("because anything released it. Releasing is derived, and both sides read")
print("back which operation did it -- a hold has an end with an author and a time,")
print("without ever having been an operation of its own.")
