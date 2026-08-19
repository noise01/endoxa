"""The knowledge boundary as a schema (RFC-0026 Decision 4 (c), ADR-0125).

What an agent knows, is uncertain about, and does not know is a fact *about its
belief set*, so the vocabulary for saying it belongs with the belief set rather
than with whoever happens to classify beliefs. RFC-0026 Decision 4 (c) said as
much -- "the persistent representation of the knowledge boundary has the
character of the governance layer" -- and this module is the smallest thing that
can be true of.

**Only the schema lives here.** The thresholds, the classifier and the asking
policy stay in the host (``domains/self_model/boundary.py``): deciding *when* a
mid-confidence belief is worth a question is a policy of this agent's
self-model, not a property of any belief set (ADR-0004's innate/acquired
boundary puts policy in the host's domains). What crosses into the kernel is the
three names an outside reader needs in order to read a knowledge boundary at
all.

**Why now.** ADR-0124 moved the calibration instruments into ``kernel/`` and
left one type annotation reaching back out to ``domains/self_model`` for this
alias -- checked by nothing, because no contract forbade it. It was the last
edge standing between the boundary and the one sentence RFC-0028 §2 states for
the end state, and a sentence that has to carve out an exception is not the
sentence. Deciding the attribution was the price of writing it (ADR-0124
decision 3 sent the decision here on purpose).

RFC-0028 §8 point 2 -- how much of ``self_model`` becomes governance -- stays
open. This settles the one name the boundary forced, not the split.
"""

from __future__ import annotations

from typing import Literal

#: Where a belief sits relative to the agent's knowledge boundary: held with
#: confidence (``known``), attended to but not confidently held (``uncertain``),
#: or absent/too weak to count as knowledge (``unknown``). The latter two are the
#: known-unknowns -- calibration's subject matter (ADR-0013, ADR-0019).
EpistemicStatus = Literal["known", "uncertain", "unknown"]
