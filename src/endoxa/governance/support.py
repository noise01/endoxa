"""Reading a belief's footing off its supports.

A belief that a derivation put there rests on something. Whether it still does is
a question about that belief's *supports*, and this module is the fold that
answers it: given what became of each support, what may be said about the belief.

Four answers, not three. The obvious three are no support at all, at least one
still alive, and all of them gone. The fourth falls out of how supports are
stored: a support names its antecedent by id, and an antecedent can leave a
host's state without ever being refuted -- paged out under memory pressure, or
evicted by decay. "It is no longer held" is not "it turned out to be false", and
collapsing the two would turn eviction into a source of counter-evidence. So
``absent`` is a state of its own, and it yields ``indeterminate``.

The module takes *resolved states*, never the supports themselves. Deciding
whether an antecedent is alive means looking at a host's state, and this package
does not know what that state is. The host resolves; this folds. That split is
also why the shape of a support record stays with the host: nothing here needs to
read it.

Pure: stdlib typing only, no state, no I/O.
"""

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

#: What became of one support.
#:
#: ``alive``: the thing it names still holds. ``dead``: it was refuted or
#: retracted -- the antecedent flipped false, the rule was retracted, the link
#: was defeated. ``absent``: it can no longer be found. The last is deliberately
#: not ``dead``: an antecedent that was paged out says nothing against what it
#: once supported, and keeping the state separate is the only thing that makes
#: "lost track of" distinguishable from "never had one".
SupportState = Literal["alive", "dead", "absent"]

#: What may be said about a belief, given its supports.
#:
#: ``unsupported``: no derivation put it there at all -- a user assertion, an
#: observation, an axiom -- so the absence of support says nothing against it and
#: it is outside this question. In practice this is the large majority of
#: beliefs. ``in``: at least one support holds. ``out``: it had supports and every
#: one of them is gone. ``indeterminate``: nothing alive is left, but what is
#: missing went away rather than failed, so no conclusion is available.
SupportVerdict = Literal["unsupported", "in", "out", "indeterminate"]

ALIVE: SupportState = "alive"
DEAD: SupportState = "dead"
ABSENT: SupportState = "absent"

UNSUPPORTED: SupportVerdict = "unsupported"
IN: SupportVerdict = "in"
OUT: SupportVerdict = "out"
INDETERMINATE: SupportVerdict = "indeterminate"


def support_verdict(states: Sequence[SupportState]) -> SupportVerdict:
    """Fold what became of each support into what may be said about the belief.

    Ordering of the rules is the whole content:

    1. No supports at all -> ``unsupported``. Not "everything is gone": there was
       never anything to go. Reading an empty record as OUT would put every user
       assertion on the beliefs in line for counter-evidence.
    2. Any support alive -> ``in``. One live footing is enough; a belief does not
       weaken because a *second* derivation of it collapsed.
    3. Every support dead -> ``out``.
    4. Otherwise (nothing alive, and at least one support merely ``absent``) ->
       ``indeterminate``. This is the answer that costs coverage on purpose: a
       belief whose antecedent was paged out is not judged, rather than judged
       wrongly.

    Args:
        states: What became of each of the belief's supports, in any order.
            Empty when the belief carries no support record.

    Returns:
        One of :data:`SupportVerdict`.
    """
    if not states:
        return UNSUPPORTED
    if any(state == ALIVE for state in states):
        return IN
    if all(state == DEAD for state in states):
        return OUT
    return INDETERMINATE


__all__ = [
    "ABSENT",
    "ALIVE",
    "DEAD",
    "IN",
    "INDETERMINATE",
    "OUT",
    "UNSUPPORTED",
    "SupportState",
    "SupportVerdict",
    "support_verdict",
]
