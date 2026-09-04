"""Tests for the provenance vocabularies.

This module was deleted once, in 0.2.0, under a rule worth keeping: a module
exported by nothing, imported by nothing and tested by nothing is 118 lines on no
execution path, and removing it is the only thing to do with it.

Two of those three were true from inside this repository and false outside it.
The consumer these names were written for is a private host that this package
cannot see, so "imported by nothing" meant "imported by nothing visible", and the
unit tests for the vocabularies existed all along -- in that host, where they
could not count. The half that was true without qualification is that ``__all__``
did not export it, and that is fixed alongside these tests: a name in the API and
a test on it are the two things the deletion rule reads.

What is *not* back is the mapping from a host's write roles onto these names.
That half named roles belonging to one host, and a package that cannot see its
consumers cannot hold a vocabulary belonging to one of them. The names are the
ledger's; deciding which one applies is the host's.
"""

from endoxa.governance import PROVENANCE_KEYS, RETRIEVAL_KINDS, SOURCE_KINDS
from endoxa.governance import provenance as provenance_module


class TestTheTwoVocabulariesStaySeparate:
    def test_an_origin_is_never_also_a_retrieval(self):
        # The whole reason there are two frozensets rather than one: a belief
        # paged back in by spreading activation still originated with whoever
        # asserted it, and a single vocabulary lets the second overwrite the first.
        assert SOURCE_KINDS.isdisjoint(RETRIEVAL_KINDS)

    def test_the_origins_are_the_contract(self):
        assert sorted(SOURCE_KINDS) == [
            "consolidation",
            "corpus",
            "derivation",
            "seed",
            "tool",
            "unknown",
            "user",
        ]

    def test_unknown_is_available_as_the_fallback(self):
        # A row predating the distinction, or a caller that does not specify, has
        # to land somewhere inside the vocabulary rather than outside it.
        assert "unknown" in SOURCE_KINDS

    def test_the_retrieval_mechanisms_are_the_contract(self):
        assert sorted(RETRIEVAL_KINDS) == ["conflict_check", "read_through", "spreading_activation"]


class TestWhatABirthFixes:
    def test_the_keys_a_later_update_must_not_overwrite(self):
        assert sorted(PROVENANCE_KEYS) == ["origin_event_id", "session_id", "source"]


class TestTheModuleHoldsNamesAndNothingElse:
    """The positive control under the split.

    The deletion took a mapping out along with the vocabularies, and restoring the
    vocabularies without it is the decision here rather than an oversight. A test
    that only reads the three frozensets would pass just as well with the mapping
    put back, so it would not be checking the decision at all.
    """

    def test_the_module_is_data(self):
        public = {name for name in vars(provenance_module) if not name.startswith("_")}
        assert public == {"SOURCE_KINDS", "RETRIEVAL_KINDS", "PROVENANCE_KEYS"}

    def test_the_vocabularies_cannot_be_edited_in_place(self):
        # frozenset rather than set: a caller that could add a name to the
        # vocabulary would be deciding the contract at runtime.
        for vocabulary in (SOURCE_KINDS, RETRIEVAL_KINDS, PROVENANCE_KEYS):
            assert isinstance(vocabulary, frozenset)
