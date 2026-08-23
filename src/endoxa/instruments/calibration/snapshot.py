"""A coherent, point-in-time view of the calibration module's 3 metrics.

Pure data aggregation only: ``CalibrationSnapshot`` bundles the knowledge,
competence, and ask-policy facets into a single introspectable
value, without introducing new accounting logic. The actor wiring that
populates it lives in a host.
"""

from dataclasses import dataclass

from endoxa.instruments.calibration.ask_policy import AskOutcomeCounts
from endoxa.instruments.calibration.competence import BrierAccumulator
from endoxa.instruments.calibration.knowledge import KnowledgeCalibrationStats


@dataclass(slots=True, frozen=True)
class CalibrationSnapshot:
    """A single, coherent read of the agent's calibration metrics.

    Attributes:
        knowledge: Knowledge-calibration transition counts (overconfidence /
            unknown-confirmation).
        competence_brier: Brier-score accumulator over resolved predictions.
        ask_policy: Ask-outcome counters over resolved ask-user questions.
    """

    knowledge: KnowledgeCalibrationStats
    competence_brier: BrierAccumulator
    ask_policy: AskOutcomeCounts
