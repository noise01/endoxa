"""Reading a belief's footing off its supports.

A belief that was put on the board by a derivation rests on something. Whether
it still does is a question about that belief's *supports*, and this module is
the fold that answers it: given what became of each support, what may be said
about the belief.

Four answers, not three. RFC-0064 §3-2 named three states -- no support at all,
at least one alive (IN), all gone (OUT) -- and the fourth falls out of how the
host stores supports: a support names its antecedent by id, and the antecedent
can leave the board without being refuted (paged out under memory pressure,
ADR-0042, or evicted by activation decay). "The board no longer holds it" is not
"it turned out to be false", and collapsing the two would make eviction a source
of counter-evidence -- exactly the false refutation RFC-0064 §7-4 requires to
stay at zero. So ``absent`` is its own state and yields ``indeterminate``.

The module takes *resolved states*, never the supports themselves. Deciding
whether an antecedent is alive means looking at a board, and the kernel does not
know what a board is (principle 1). The host resolves; this folds.
That split is also why the support record's shape stays in the host: nothing
here needs to read it.

**Nothing calls this yet.** Placing the judgement and firing on it are separate
increments on purpose: a single increment that did both would
produce measurements consistent with two different explanations, which is the
mistake ADR-0110 and ADR-0116 each recorded once. Increment 3 writes the
resolver and decides what an OUT is worth.

This module is pure: stdlib typing only, no state, no I/O.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

#: What became of one support.
#:
#: ``alive``: the thing it names still holds. ``dead``: it was refuted or
#: retracted -- the antecedent flipped false, the rule was retracted, the link
#: was defeated. ``absent``: it can no longer be found. The last is deliberately
#: not ``dead``: a paged-out antecedent says nothing against what it
#: once supported, and ADR-0080 known limitation (c) -- that a support lost to
#: paging is indistinguishable from one that never existed -- is precisely what
#: keeping this state separate makes measurable.
SupportState = Literal["alive", "dead", "absent"]

#: What may be said about a belief, given its supports.
#:
#: ``unsupported``: it was not put on the board by a derivation at all (a user
#: assertion, an observation, an innate axiom -- 97.2% of atoms in vivo,
#: ADR-0128), so the absence of support says nothing against it and it is outside
#: this question. ``in``: at least one support holds. ``out``: it had supports
#: and every one of them is gone -- the transition RFC-0064 was written to make
#: observable. ``indeterminate``: nothing alive is left, but what is missing left
#: the board rather than failed, so no conclusion is available.
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
       assertion on the board in line for counter-evidence.
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
