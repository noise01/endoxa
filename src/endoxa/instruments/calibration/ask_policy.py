"""Pure ask-outcome accounting for an agent's decision to ask rather than assert.

An agent that can put a question to the user instead of asserting an answer has
a policy, and this counts what became of the questions that policy actually
raised: affirmed, denied, or timed out.

Scope: resolution-outcome counters only. Correlating an unasked "uncertain"
classification with a failure that followed -- a stronger measure of the
policy's precision -- would need the host to report that failure back, and is
deliberately out of scope. Deciding when to ask is the host's; counting how the
asking went is this.
"""

from dataclasses import dataclass
from typing import Literal

AskOutcome = Literal["affirmed", "denied", "timed_out"]


@dataclass(slots=True, frozen=True)
class AskOutcomeCounts:
    """Running counts of how ask-user questions were resolved.

    Attributes:
        affirmed: Number of questions the user answered affirmatively.
        denied: Number of questions the user answered negatively.
        timed_out: Number of questions that were never answered in time.
    """

    affirmed: int = 0
    denied: int = 0
    timed_out: int = 0

    def observe(self, outcome: AskOutcome) -> AskOutcomeCounts:
        """Return new counts with one more resolved question folded in."""
        return AskOutcomeCounts(
            affirmed=self.affirmed + (1 if outcome == "affirmed" else 0),
            denied=self.denied + (1 if outcome == "denied" else 0),
            timed_out=self.timed_out + (1 if outcome == "timed_out" else 0),
        )

    def resolution_rate(self) -> float | None:
        """Return the fraction of questions resolved (not timed out)."""
        total = self.affirmed + self.denied + self.timed_out
        if total == 0:
            return None
        return (self.affirmed + self.denied) / total

    def affirm_rate(self) -> float | None:
        """Return the fraction of resolved questions that were affirmed."""
        resolved = self.affirmed + self.denied
        if resolved == 0:
            return None
        return self.affirmed / resolved
