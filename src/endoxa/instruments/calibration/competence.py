"""Pure Brier-score accounting for the world model's competence calibration.

Tracks how well predicted per-action success probabilities (from whatever
produced them) match the eventually observed
success/failure outcome. The wiring lives in
a host; this module is unit-testable in isolation.
"""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class BrierAccumulator:
    """Running Brier-score accumulator over resolved predictions.

    Attributes:
        sum_squared_error: Running sum of ``(predicted_probability - actual)^2``.
        count: Number of predictions folded in.
    """

    sum_squared_error: float = 0.0
    count: int = 0

    def observe(self, *, predicted_probability: float, success: bool) -> BrierAccumulator:
        """Return new stats with one more resolved prediction folded in.

        Args:
            predicted_probability: The predicted success probability in ``[0.0, 1.0]``.
            success: Whether the action actually succeeded.

        Returns:
            A new :class:`BrierAccumulator` (this type is immutable).
        """
        actual = 1.0 if success else 0.0
        error = predicted_probability - actual
        return BrierAccumulator(
            sum_squared_error=self.sum_squared_error + error * error,
            count=self.count + 1,
        )

    def score(self) -> float | None:
        """Return the mean Brier score, or ``None`` with no observations yet."""
        if self.count == 0:
            return None
        return self.sum_squared_error / self.count
