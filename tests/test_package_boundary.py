"""Checks on what this package is allowed to say, contain, and forget to declare.

Four rules that were held by hand while the code was being brought over, and are
held by CI from here on. A rule nothing checks is a rule that lasts until the next
person who has not read it.

Each check is paired with a positive control that plants a violation and shows the
detector firing. A check that cannot fail is not a check, and these look for the
*absence* of things, which is exactly the shape that passes by accident.
"""

import ast
import io
import re
import tokenize
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Words that name something in the project this package came from rather than
#: anything here, each with what to say instead. A reader who meets one of these is
#: being asked to picture a structure that does not exist.
#:
#: Deliberately absent: "salience". It was on the original list because a learner
#: over there was named after it, but the word itself is ordinary attention-research
#: vocabulary and :class:`doxa.trace.Proposition` carries it as a field. Forbidding a
#: word because something elsewhere was named after it is the wrong test.
FORBIDDEN_WORDS = {
    "doppelganger": "the project this was extracted from",
    "blackboard": "a working memory this package does not have -- say the belief set",
    "coalition": "a host's attention mechanism -- say what the entry is about",
    "broadcast": "a host's attention mechanism -- say entry, or proposition",
    "ritual": "the research side's acquisition process",
    "acquisition": "the research side's acquisition process",
    "faculty": "a host's organ vocabulary -- say component",
    "organ": "a host's organ vocabulary -- say component",
    "kernel": "the export core this used to sit in -- say package",
    "asset": "the export core's vocabulary -- say package",
    "bandit": "a learner that is not part of this package",
    "plastic": "the research side's plastic layer",
}

#: Directories of the host it came from. A path like ``domains/memory.py`` points at
#: a file no reader of this package can open.
HOST_PATH = re.compile(r"\b(?:domains|modules|runtime|faculties|interface|evals|policies|environments)/")

#: Citations of decision records that live in a private repository.
CITATION = re.compile(r"\b(?:ADR|RFC)-\d{4}")

CJK = re.compile(r"[　-ヿ一-鿿]")

type Corpus = list[tuple[str, str]]


def _real_files() -> Corpus:
    """Every source file except this one, as ``(name, text)``."""
    paths = sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "tests").rglob("*.py"))
    return [
        (path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8"))
        for path in paths
        if path.name != Path(__file__).name
    ]


def _word_offences(corpus: Corpus) -> list[str]:
    return [
        f"{name}: {word!r} -- {why}"
        for name, text in corpus
        for word, why in FORBIDDEN_WORDS.items()
        if re.search(rf"\b{word}\b", text.lower())
    ]


def _line_offences(corpus: Corpus, pattern: re.Pattern[str]) -> list[str]:
    return [
        f"{name}:{number}"
        for name, text in corpus
        for number, line in enumerate(text.splitlines(), 1)
        if pattern.search(line)
    ]


def _prose(source: str) -> list[tuple[int, str]]:
    """Return a file's comments and docstrings as ``(line, text)``.

    String literals that are not docstrings are excluded on purpose: test data is
    allowed to contain anything, including the non-ASCII terms whose handling is
    the point of some of the tests.
    """
    found = [
        (token.start[0], token.string)
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    ]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                found.append((getattr(node, "lineno", 1), doc))
    return found


def _cjk_offences(corpus: Corpus) -> list[str]:
    return [f"{name}:{line}" for name, text in corpus for line, prose in _prose(text) if CJK.search(prose)]


def _contract_layers() -> set[str]:
    contracts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    layers = next(
        contract["layers"]
        for contract in contracts["tool"]["importlinter"]["contracts"]
        if contract["type"] == "layers"
    )
    return {layer.removeprefix("doxa.") for layer in layers}


class TestVocabulary:
    """The package does not name structures that only exist somewhere else."""

    def test_no_forbidden_word_appears(self):
        offences = _word_offences(_real_files())
        assert not offences, "host vocabulary reached the package:\n" + "\n".join(offences)

    def test_a_planted_word_is_caught(self):
        assert _word_offences([("planted.py", "# the blackboard holds it")])
        assert not _word_offences([("planted.py", "# the belief set holds it")])

    def test_a_word_inside_a_longer_one_is_not_caught(self):
        """``organ`` must not fire on ``organise``, or the rule becomes unusable."""
        assert not _word_offences([("planted.py", "# organise the arguments")])

    def test_no_host_path_is_referenced(self):
        offences = _line_offences(_real_files(), HOST_PATH)
        assert not offences, "a path into the host this came from:\n" + "\n".join(offences)

    def test_a_planted_host_path_is_caught(self):
        assert _line_offences([("planted.py", "# see domains/memory.py")], HOST_PATH)
        assert not _line_offences([("planted.py", "# see doxa/governance.py")], HOST_PATH)

    def test_no_decision_record_is_cited(self):
        offences = _line_offences(_real_files(), CITATION)
        assert not offences, "a citation of a record this package's readers cannot open:\n" + "\n".join(offences)

    def test_a_planted_citation_is_caught(self):
        assert _line_offences([("planted.py", "# see ADR-0123 for why")], CITATION)
        assert _line_offences([("planted.py", "# see RFC-0091 for why")], CITATION)
        assert not _line_offences([("planted.py", "# see the docstring for why")], CITATION)


class TestLanguage:
    """Comments and docstrings are English; test data may be anything."""

    def test_no_cjk_in_prose(self):
        offences = _cjk_offences(_real_files())
        assert not offences, "non-English prose:\n" + "\n".join(offences)

    def test_planted_cjk_prose_is_caught(self):
        assert _cjk_offences([("planted.py", '"""説明。"""\n')])
        assert _cjk_offences([("planted.py", "x = 1  # 説明\n")])

    def test_cjk_test_data_is_left_alone(self):
        """A string that is not a docstring is data, and data may be in any script."""
        assert not _cjk_offences([("planted.py", 'name = "エロウェン"\n')])


class TestContractCompleteness:
    """Every package is named by the layers contract, or it escapes it in silence."""

    def test_the_contract_and_the_packages_agree(self):
        declared = _contract_layers()
        actual = {path.parent.name for path in (ROOT / "src" / "doxa").glob("*/__init__.py")}
        assert actual - declared == set(), f"packages outside the DAG contract: {sorted(actual - declared)}"
        assert declared - actual == set(), f"the contract names a package that is gone: {sorted(declared - actual)}"

    def test_the_comparison_is_two_way(self):
        """A new package and a deleted one are different failures, and both must show."""
        declared, actual = {"solver", "syntax"}, {"solver", "syntax", "sneaky"}
        assert actual - declared == {"sneaky"}
        assert {"solver", "syntax", "gone"} - actual == {"gone"}
