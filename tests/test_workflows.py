r"""The shell in a workflow step is shell, and a stray ``\n`` in it is an argument.

A line continuation written as the two characters backslash-``n`` rather than as a
real newline does not fail to parse. YAML takes it, the shell takes it, and the
pair arrives as a word: ``gh`` was handed an argument ``n`` and answered "no
matches found for `n`" -- after the version had already gone to the index, where
a second upload of the same version is refused.

Nothing here runs a workflow. What it checks is the shape of that mistake, which
is cheap to look for and was not cheap to make.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

#: A backslash immediately followed by the letter ``n``. Distinct from a real
#: continuation, which is a backslash at the end of a line with a newline after
#: it, and which this does not match.
LITERAL_NEWLINE = re.compile(r"\\n")

#: The workflows that are ours to keep working. ``openwiki-update.yml`` is
#: rewritten by the tool that generates it, so holding it to this would be a fight
#: with the generator rather than a check on us.
WORKFLOWS = ["ci.yml", "release.yml"]


def _run_blocks(name: str) -> list[tuple[str, str]]:
    """Return every ``run:`` script in a workflow, as ``(where, script)``."""
    document = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    return [
        (f"{name}:{job}:{step.get('name', '?')}", step["run"])
        for job, definition in document["jobs"].items()
        for step in definition["steps"]
        if "run" in step
    ]


@pytest.mark.parametrize("name", WORKFLOWS)
def test_no_step_carries_a_literal_backslash_n(name):
    offences = [
        f"{where}: {script.strip()[:80]!r}" for where, script in _run_blocks(name) if LITERAL_NEWLINE.search(script)
    ]
    assert not offences, "a continuation that is two characters, not a newline:\n" + "\n".join(offences)


@pytest.mark.parametrize("name", WORKFLOWS)
def test_the_walk_found_steps_to_check(name):
    """The control: a workflow whose steps were never read passes for free."""
    assert _run_blocks(name), f"{name} yielded no run blocks"


def test_the_shape_that_broke_is_caught():
    """The line as it shipped, so the detector is seen firing on the real thing."""
    shipped = 'gh release create "${TAG}" ' + chr(92) + 'n            --title "${TAG}"'
    assert LITERAL_NEWLINE.search(shipped)


def test_a_real_continuation_is_not_caught():
    """A backslash at the end of a line is how a continuation is actually written."""
    fine = 'gh release create "${TAG}" ' + chr(92) + '\n  --title "${TAG}"'
    assert not LITERAL_NEWLINE.search(fine)


def test_the_release_step_reads_the_file_the_step_before_it_writes():
    """Two steps joined only by a filename, which nothing else would notice."""
    scripts = dict(_run_blocks("release.yml"))
    writers = [script for script in scripts.values() if "> release-notes.md" in script]
    cutters = [script for script in scripts.values() if "gh release create" in script]
    assert len(writers) == 1, writers
    assert len(cutters) == 1, cutters
    assert "--notes-file release-notes.md" in cutters[0]
