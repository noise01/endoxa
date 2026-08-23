"""Importing this package does not build a parser.

Compiling the TPTP grammar and loading the library that compiles it cost about
seventy milliseconds, and they were paid at import by everyone: a caller that
only reads a ledger, a caller that only counts Brier scores. Neither parses
anything.

The cost moved to the first parse, where it is once and then held by
``sys.modules``. What keeps it there is this file. A single top-level ``from lark
import ...`` put back anywhere in the package undoes the whole thing, silently
and with every test still passing -- the shape of regression that only a test
about *absence* can catch.

Each check runs in a fresh interpreter. Once a module is in ``sys.modules`` the
question cannot be asked any more, and the suite has almost certainly imported
everything by the time this runs.
"""

import subprocess
import sys

import pytest

#: What a caller can import without a parser being built. ``endoxa.solver`` is on
#: the list on purpose: constructing and checking formulas is most of what it is
#: for, and none of that goes through the grammar.
PARSERLESS = [
    "endoxa.errors",
    "endoxa.governance",
    "endoxa.instruments.calibration",
    "endoxa.instruments.coverage",
    "endoxa.solver",
    "endoxa.syntax",
    "endoxa.trace",
]


def _in_fresh_interpreter(script: str) -> str:
    result = subprocess.run(  # noqa: S603 - our own interpreter, our own script
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.parametrize("module", PARSERLESS)
def test_importing_it_does_not_load_the_grammar_library(module):
    loaded = _in_fresh_interpreter(f"import sys, {module}; print('lark' in sys.modules)")
    assert loaded == "False", f"importing {module} loaded the parser library"


def test_the_check_can_fail():
    """The control: the same question, asked where the answer has to be yes."""
    loaded = _in_fresh_interpreter(
        "import sys\nfrom endoxa.solver import parse_fof\n"
        "parse_fof('fof(r, axiom, human(a)).')\nprint('lark' in sys.modules)",
    )
    assert loaded == "True", "parsing did not load the parser library, so the check above proves nothing"


def test_the_parser_is_built_once():
    """Held by ``sys.modules`` after the first parse, not rebuilt per call."""
    same = _in_fresh_interpreter(
        "from endoxa.solver import parse_fof\n"
        "from endoxa.solver.parsers import _grammar\n"
        "a = _grammar.parser\n"
        "parse_fof('fof(r, axiom, human(a)).')\n"
        "parse_fof('fof(s, axiom, cat(b)).')\n"
        "print(a is _grammar.parser)",
    )
    assert same == "True"
