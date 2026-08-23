"""Checks on what this package is allowed to say, contain, and forget to declare.

Rules that were held by hand while the code was being brought over, and are held
by CI from here on. A rule nothing checks is a rule that lasts until the next
person who has not read it.

Two shapes of rule live here. The first asks whether a forbidden word survived
the move. The second asks a harder question the first cannot: whether the *edit
that removed one* left a readable sentence behind. Deleting a name and not
repairing the grammar around it passes every vocabulary check ever written, and
leaves prose like "the tie surfaced only as a warning log in a warning log" for a
stranger to read. Those leftovers have shapes -- an empty parenthetical, a line
holding nothing but a full stop, a plural handed a singular's possessive -- and
:data:`SCARS` is the list of the ones actually found in this package.

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
#: vocabulary and :class:`endoxa.trace.Proposition` carries it as a field. Forbidding a
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

#: Packages of the host it came from, reached either as a path (``domains/memory.py``)
#: or as a dotted module (``modules.reasoning._retract_rule``). Both point at a file no
#: reader of this package can open, and the second form is the one that slips past a
#: rule written only for slashes.
HOST_PATH = re.compile(
    r"\b(?:domains|modules|runtime|faculties|interface|evals|policies|environments)(?:/|\.(?=[a-z_]))",
)

#: Citations of decision records that live in a private repository. Both the numbered
#: form and the bare one: "Three RFCs settled on holding both" sends a reader after
#: documents that are not only unopenable but unnamed.
CITATION = re.compile(r"\b(?:ADR|RFC)s?\b")

#: Documents that exist only in the repository this was extracted from.
PRIVATE_DOC = re.compile(r"\bbacklog\.md\b|\bdocs/")

#: What a redaction leaves behind when the name goes and the sentence does not get
#: rewritten. Each of these was found in this package, not imagined for the test.
SCARS = {
    "an empty parenthetical -- whatever was inside it was deleted": re.compile(r"(?<=\s)\(\s*\.{0,2}\s*\)"),
    "a line holding nothing but a full stop": re.compile(r"^\s*\.\s*$"),
    "a section mark with no document to look it up in": re.compile(r"§"),
    "a plural handed a singular's possessive": re.compile(r"\b\w+s's\b"),
}

#: Words that genuinely end in ``s`` while being singular, so ``'s`` is correct English
#: on them -- including the name the test fixtures are built around. Without this the
#: possessive rule fires on ``the class's`` and becomes a rule people delete rather
#: than obey.
SINGULARS_ENDING_IN_S = frozenset(
    {"access", "basis", "class", "process", "socrates", "status", "success"},
)

CJK = re.compile(r"[　-ヿ一-鿿]")

#: Sphinx cross-reference roles, whose target has to name something this package
#: actually defines. An unresolvable one is a pointer into the host, or a rename that
#: only got applied on one side.
ROLE = re.compile(r":(?:func|mod|class|meth|data|attr|obj|exc):`~?([^`]+)`")

#: Inline code spans, replaced before the scar patterns run: ``p()`` is a call with no
#: arguments, not a parenthetical someone emptied.
CODE_SPAN = re.compile(r"``[^`]*``")

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


def _prose_lines(corpus: Corpus) -> list[tuple[str, int, str]]:
    """Every individual line of prose, as ``(file, line-of-the-block, text)``.

    The line number is where the comment or docstring starts rather than where the
    offending line sits inside it -- enough to find, and it keeps this independent
    of how a docstring is indented.
    """
    return [
        (name, line, text) for name, source in corpus for line, prose in _prose(source) for text in prose.splitlines()
    ]


def _scar_offences(corpus: Corpus) -> list[str]:
    offences = []
    for name, line, text in _prose_lines(corpus):
        stripped = CODE_SPAN.sub("CODE", text)
        for why, pattern in SCARS.items():
            found = pattern.search(stripped)
            if not found:
                continue
            if pattern is SCARS["a plural handed a singular's possessive"]:
                word = found.group().removesuffix("'s")
                if word.lower() in SINGULARS_ENDING_IN_S:
                    continue
            offences.append(f"{name}:{line}: {why} -- {text.strip()[:70]!r}")
    return offences


def _prose_offences(corpus: Corpus, pattern: re.Pattern[str]) -> list[str]:
    return [
        f"{name}:{line}: {text.strip()[:70]!r}" for name, line, text in _prose_lines(corpus) if pattern.search(text)
    ]


def _class_members(node: ast.ClassDef) -> set[str]:
    """Collect a class's own name and its members, under both bare and dotted forms.

    Attributes a method assigns to ``self`` count: a class that sets its state in
    ``__init__`` declares none of them at class level, and a reference to one is
    no less resolvable for that.
    """
    names = {node.name}
    for child in node.body:
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            names |= {child.name, f"{node.name}.{child.name}"}
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            names |= {child.target.id, f"{node.name}.{child.target.id}"}
    for inner in ast.walk(node):
        assigned_on_self = (
            isinstance(inner, ast.Attribute)
            and isinstance(inner.ctx, ast.Store)
            and isinstance(inner.value, ast.Name)
            and inner.value.id == "self"
        )
        if assigned_on_self:
            names |= {inner.attr, f"{node.name}.{inner.attr}"}
    return names


def _top_level_names(node: ast.stmt) -> set[str]:
    """Return the names one top-level statement makes available under its module."""
    if isinstance(node, ast.ClassDef):
        return _class_members(node)
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return {node.name}
    if isinstance(node, ast.Assign):
        return {target.id for target in node.targets if isinstance(target, ast.Name)}
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    if isinstance(node, ast.ImportFrom):
        return {alias.asname or alias.name for alias in node.names}
    return set()


def _module_symbols() -> dict[str, set[str]]:
    """Map each module's dotted name to the top-level names it defines or re-exports."""
    symbols: dict[str, set[str]] = {}
    for path in sorted((ROOT / "src").rglob("*.py")):
        dotted = path.relative_to(ROOT / "src").with_suffix("").as_posix().replace("/", ".")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        symbols[dotted.removesuffix(".__init__")] = set().union(*(_top_level_names(node) for node in tree.body), set())
    return symbols


def _resolves(target: str, *, package: str, symbols: dict[str, set[str]]) -> bool:
    """Whether a cross-reference target names something in this package.

    ``package`` is what a leading dot means in the file the reference was written
    in: for ``__init__.py`` that is the package itself, for any other module it is
    the package the module sits in.
    """
    target = target.removeprefix("~").strip()
    if target.startswith("."):
        target = package + target
    if target in symbols:
        return True
    head, _, tail = target.rpartition(".")
    if head in symbols and tail in symbols[head]:
        return True
    return any(target in names for names in symbols.values())


def _dangling_references() -> list[str]:
    symbols = _module_symbols()
    dangling: list[str] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        dotted = path.relative_to(ROOT / "src").with_suffix("").as_posix().replace("/", ".")
        module = dotted.removesuffix(".__init__")
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        name = path.relative_to(ROOT).as_posix()
        dangling.extend(
            f"{name}:{line}: {target}"
            for line, prose in _prose(path.read_text(encoding="utf-8"))
            for target in ROLE.findall(prose)
            if not _resolves(target, package=package, symbols=symbols)
        )
    return dangling


def _contract_layers() -> set[str]:
    contracts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    layers = next(
        contract["layers"]
        for contract in contracts["tool"]["importlinter"]["contracts"]
        if contract["type"] == "layers"
    )
    return {layer.removeprefix("endoxa.") for layer in layers}


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
        assert not _line_offences([("planted.py", "# see endoxa/governance.py")], HOST_PATH)

    def test_no_decision_record_is_cited(self):
        offences = _line_offences(_real_files(), CITATION)
        assert not offences, "a citation of a record this package's readers cannot open:\n" + "\n".join(offences)

    def test_a_planted_citation_is_caught(self):
        assert _line_offences([("planted.py", "# see ADR-0123 for why")], CITATION)
        assert _line_offences([("planted.py", "# see RFC-0091 for why")], CITATION)
        assert not _line_offences([("planted.py", "# see the docstring for why")], CITATION)

    def test_an_unnumbered_record_is_caught_too(self):
        """Dropping the number does not make the reference followable, only vaguer."""
        assert _line_offences([("planted.py", "# Three RFCs settled on holding both")], CITATION)

    def test_no_private_document_is_named(self):
        offences = _prose_offences(_real_files(), PRIVATE_DOC)
        assert not offences, "a document only the host repository holds:\n" + "\n".join(offences)

    def test_a_planted_private_document_is_caught(self):
        assert _prose_offences([("planted.py", "# out of scope; see docs/backlog.md")], PRIVATE_DOC)
        assert _prose_offences([("planted.py", '"""The remaining work (``backlog.md`` §6)."""')], PRIVATE_DOC)
        assert not _prose_offences([("planted.py", "# out of scope; see the CHANGELOG")], PRIVATE_DOC)


class TestRedactionScars:
    """Removing a name is half the edit. These are the shapes of the other half undone."""

    def test_no_scar_survives(self):
        offences = _scar_offences(_real_files())
        assert not offences, "the redaction left the sentence broken:\n" + "\n".join(offences)

    def test_each_planted_scar_is_caught(self):
        assert _scar_offences([("planted.py", "# the solver can decide (..). What it leaves")])
        assert _scar_offences([("planted.py", '"""What the belief rested on\n\n    .\n    """')])
        assert _scar_offences([("planted.py", "# the revision target (§2.10) is picked")])
        assert _scar_offences([("planted.py", "# mirroring the beliefs's own reader")])

    def test_a_call_with_no_arguments_is_not_a_scar(self):
        """``p()`` and ``match()`` are code, and the parentheses are meant to be empty."""
        assert not _scar_offences([("planted.py", "# arity-0 atoms (``p()``) yield an empty tuple")])
        assert not _scar_offences([("planted.py", "# tested between ``match()`` calls")])

    def test_a_singular_ending_in_s_keeps_its_possessive(self):
        """``the class's`` is correct English; a rule that forbids it gets deleted."""
        assert not _scar_offences([("planted.py", "# the class's own reader")])
        assert not _scar_offences([("planted.py", "# the process's exit code")])


class TestCrossReferences:
    """Every ``:func:``/``:mod:`` target names something a reader of this package can find."""

    def test_no_reference_dangles(self):
        dangling = _dangling_references()
        assert not dangling, "a cross-reference naming nothing in this package:\n" + "\n".join(dangling)

    def test_a_planted_dangling_reference_is_caught(self):
        """Both real ones the extraction left behind: a host class, and a host module."""
        symbols = _module_symbols()
        package = "endoxa.governance.revision"
        assert not _resolves("EventStore.get_by_types", package=package, symbols=symbols)
        assert not _resolves(".memory._build_exclusion_links", package=package, symbols=symbols)

    def test_a_relative_reference_resolves_against_its_own_package(self):
        symbols = _module_symbols()
        package = "endoxa.governance.revision"
        assert _resolves(".preference", package=package, symbols=symbols)
        assert _resolves(".engine.select_verified_revision_target", package=package, symbols=symbols)
        assert not _resolves(".propagation.propagate", package=package, symbols=symbols)


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


class TestTypingPromise:
    """The ``Typing :: Typed`` classifier is a claim, and PEP 561 is how it is kept."""

    def test_the_marker_is_present(self):
        """Without ``py.typed`` a type checker ignores every annotation in here.

        The classifier would then be advertising something no downstream project
        can actually use -- annotations written, declared, and unreadable.
        """
        classifiers = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["classifiers"]
        if "Typing :: Typed" not in classifiers:
            return
        marker = ROOT / "src" / "endoxa" / "py.typed"
        assert marker.is_file(), "the classifier claims a typing the marker does not grant"


def _units_under_the_package() -> set[str]:
    """Everything directly under ``endoxa``: subpackages, and modules beside them.

    Both, because the layers contract constrains whatever it lists and leaves
    everything else unconstrained. A rule that only counted packages would let a
    new top-level *module* out of the DAG without anything saying so -- which is
    what ``errors`` would have done.
    """
    root = ROOT / "src" / "endoxa"
    packages = {path.parent.name for path in root.glob("*/__init__.py")}
    modules = {path.stem for path in root.glob("*.py") if path.name != "__init__.py"}
    return packages | modules


class TestContractCompleteness:
    """Everything under ``endoxa`` is named by the layers contract, or it escapes it."""

    def test_the_contract_and_the_source_agree(self):
        declared, actual = _contract_layers(), _units_under_the_package()
        assert actual - declared == set(), f"outside the DAG contract: {sorted(actual - declared)}"
        assert declared - actual == set(), f"the contract names something gone: {sorted(declared - actual)}"

    def test_a_top_level_module_counts_too(self):
        """``errors.py`` is a module, not a package, and is still inside the DAG."""
        assert "errors" in _units_under_the_package()
        assert "errors" in _contract_layers()

    def test_the_comparison_is_two_way(self):
        """A new package and a deleted one are different failures, and both must show."""
        declared, actual = {"solver", "syntax"}, {"solver", "syntax", "sneaky"}
        assert actual - declared == {"sneaky"}
        assert {"solver", "syntax", "gone"} - actual == {"gone"}
