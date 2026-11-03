from powercontext.artifacts import ArtifactAddress, ArtifactRef
from powercontext.builtin.artifacts.memory import MemoryHit
from powercontext.builtin.runtime import PrepareContextRequest
from powercontext.builtin.runtime.evidence_selection import _render, _terms
from powercontext.builtin.runtime.prepared_context import (
    EvidenceFragment,
    MemoryEntryAddress,
    PreparedContextBuilder,
    PreparedMemoryCandidates,
)


def test_verb_inflections_match_base_form():
    assert set(_terms("increase")) == set(_terms("increased")) == set(_terms("increases"))


def test_long_repetitive_sentence_does_not_crowd_out_two_short_evidence_spans():
    ref = ArtifactRef(family="memory", artifact_id="memory", revision=1)
    texts = ("Alpha beta gamma delta " + "noise " * 80 + ".", "Alpha beta evidence.", "Gamma delta evidence.")
    hits = tuple(
        MemoryHit(memory_ref=ref, entry_id=str(i), entry_version_id=str(i), text=text, score=1, matched_by=("fts",))
        for i, text in enumerate(texts)
    )
    fragments = tuple(
        EvidenceFragment(
            MemoryEntryAddress(ArtifactAddress(scope_id="scope", artifact=ref), str(i), str(i)), 0, len(text), text
        )
        for i, text in enumerate(texts)
    )
    budget = max(len(_render(fragments[1:]).encode()), len(_render(fragments[:1]).encode()))
    assert len(_render(fragments[:2]).encode()) > budget
    built = PreparedContextBuilder().build_scopes_result(
        request=PrepareContextRequest(query="alpha beta gamma delta", max_bytes=budget, evidence_selection=True),
        current_scope_id="scope",
        memory_candidates=(PreparedMemoryCandidates(scope_id="scope", hits=hits),),
    )
    assert {fragment.address.entry_id for fragment in built.fragments} == {"1", "2"}
