"""The knowledge boundary as a schema.

What an agent knows, is uncertain about, and does not know is a fact *about its
belief set*, so the names for saying it belong with the belief set rather than
with whoever happens to do the classifying.

**Only the schema lives here.** The thresholds, the classifier and the policy for
when to ask belong to the host: deciding whether a mid-confidence belief is worth
a question is a policy of a particular agent, not a property of any belief set.
What this module provides is the three names an outside reader needs in order to
read a knowledge boundary at all.
"""

from typing import Literal

#: Where a belief sits relative to the agent's knowledge boundary: held with
#: confidence (``known``), attended to but not confidently held (``uncertain``),
#: or absent/too weak to count as knowledge (``unknown``). The latter two are the
#: known-unknowns -- calibration's subject matter.
EpistemicStatus = Literal["known", "uncertain", "unknown"]
