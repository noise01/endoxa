"""Reading an agent's confidence against what actually happened.

Three separate questions, kept separate on purpose. Whether the agent's stated
probabilities matched outcomes. Whether the things it called *known* stayed
known. Whether asking got it anywhere. One number for all three would hide which
of them moved.

The stream below is scripted, so nothing here is a measurement of anything: it
shows what the instruments report, not that an agent got better. A reading is
not an achievement.

Run: python examples/03_what_the_instruments_say.py
"""

from endoxa.instruments.calibration import (
    AskOutcomeCounts,
    BrierAccumulator,
    CompetenceObservation,
    KnowledgeCalibrationStats,
    windowed_competence,
)

# Twelve resolved predictions. Early on the agent is sure and wrong as often as
# not; later its numbers hedge toward what happens.
PREDICTIONS = [
    (0.95, False), (0.90, False), (0.95, True), (0.90, False),
    (0.80, True), (0.75, False), (0.85, True), (0.70, True),
    (0.60, True), (0.55, False), (0.65, True), (0.60, True),
]  # fmt: skip

brier = BrierAccumulator()
for probability, success in PREDICTIONS:
    brier = brier.observe(predicted_probability=probability, success=success)

print("Competence -- did the stated probabilities match the outcomes?")
print(f"  over the whole run: Brier {brier.score():.3f}  (0 is perfect, 1 is confidently wrong)")

curve = windowed_competence([CompetenceObservation(predicted_probability=p, success=s) for p, s in PREDICTIONS], 4)
readings = "  ".join(f"{w.brier:.3f}" for w in curve.windows)
print(f"  in windows of four:  {readings}")
print("  A single score cannot say whether the agent is badly calibrated or was")
print("  badly calibrated. The windowed reading can, and it is the same fold.")
print()

# The self-model calls a target known, uncertain or unknown. A target that was
# called known and later is not, is the overconfidence signal; the other
# direction is a question that got answered. Per-target membership belongs to
# the caller: this counts, it does not remember.
TRANSITIONS = [
    ("port_number", None, "known"),
    ("port_number", "known", "uncertain"),  # it was not known after all
    ("deploy_target", None, "unknown"),
    ("deploy_target", "unknown", "known"),  # asking worked
    ("owner_team", None, "known"),
]

knowledge = KnowledgeCalibrationStats()
ever_known: set[str] = set()
ever_other: set[str] = set()
for target, previous, status in TRANSITIONS:
    first_known = status == "known" and target not in ever_known
    first_other = status != "known" and target not in ever_other
    (ever_known if status == "known" else ever_other).add(target)
    knowledge = knowledge.observe_transition(
        previous=previous,
        status=status,
        first_time_known=first_known,
        first_time_nonknown=first_other,
    )

left = f"{knowledge.known_to_nonknown}/{knowledge.known_ever}"
arrived = f"{knowledge.nonknown_to_known}/{knowledge.nonknown_ever}"

print("Knowledge -- did what it called known stay known?")
print(f"  overconfidence:       {left} of targets it called known later left")
print(f"  unknown confirmation: {arrived} of targets it was unsure about became known")
print()

ask = AskOutcomeCounts()
for outcome in ("affirmed", "denied", "affirmed", "timed_out"):
    ask = ask.observe(outcome)

print("Ask policy -- did asking get anywhere?")
print(f"  resolution rate: {ask.resolution_rate():.2f}  (timeouts count against it)")
print(f"  affirm rate:     {ask.affirm_rate():.2f}  (timeouts are not in this denominator)")
print("  Two denominators rather than one: a question nobody answered is a")
print("  failure of the loop, not evidence about what the answer would have been.")
