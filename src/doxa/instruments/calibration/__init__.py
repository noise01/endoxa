"""Whether the agent's confidence matches its accuracy.

Three questions, kept apart because an agent can be well calibrated about one
and badly calibrated about another: what it claims to *know*, what it claims to
be *able to do*, and whether it asks when it should. Each is scored over a
moving window as well as cumulatively, since a calibration that was true a
thousand claims ago is not a claim about the agent now.
"""

__all__: list[str] = []
