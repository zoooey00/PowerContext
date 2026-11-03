import pytest

from powercontext.artifacts import ArtifactRef
from powercontext.builtin.artifacts.memory import MemoryHit
from powercontext.builtin.runtime import PrepareContextRequest
from powercontext.builtin.runtime.prepared_context import PreparedContextBuilder, PreparedMemoryCandidates


@pytest.mark.parametrize(
    "text",
    [
        "Cytokine levels measured by Smith et al. fell by 42% relative to controls.",
        "Cytokine levels measured in the laboratory\nfell by 42% relative to controls.",
        "Neratinib was added to cytokine-producing cultures. These concentrations fell by 42% relative to controls.",
    ],
)
def test_complete_scientific_observation_survives_sentence_selection(text):
    hit = MemoryHit(
        memory_ref=ArtifactRef(family="memory", artifact_id="memory", revision=1),
        entry_id="entry",
        entry_version_id="version",
        text=text,
        score=1,
        matched_by=("fts",),
    )
    built = PreparedContextBuilder().build_scopes_result(
        request=PrepareContextRequest(
            query="Neratinib inhibits cytokine production", max_bytes=1400, evidence_selection=True
        ),
        current_scope_id="scope",
        memory_candidates=(PreparedMemoryCandidates(scope_id="scope", hits=(hit,)),),
    )
    assert any(f.start == 0 and f.end == len(text) and f.text == text for f in built.fragments)
    assert built.context.content_bytes == len(built.context.content.encode()) <= 1400


def test_anaphoric_followup_does_not_cross_a_paragraph():
    text = "Neratinib was added to cytokine-producing cultures.\n\nThese unrelated controls were discarded."
    hit = MemoryHit(
        memory_ref=ArtifactRef(family="memory", artifact_id="memory", revision=1),
        entry_id="entry",
        entry_version_id="version",
        text=text,
        score=1,
        matched_by=("fts",),
    )
    built = PreparedContextBuilder().build_scopes_result(
        request=PrepareContextRequest(query="Neratinib cytokine", max_bytes=1400, evidence_selection=True),
        current_scope_id="scope",
        memory_candidates=(PreparedMemoryCandidates(scope_id="scope", hits=(hit,)),),
    )
    assert all("unrelated controls" not in f.text for f in built.fragments)


def test_anaphoric_followup_keeps_fitting_antecedent_under_tight_budget():
    from powercontext.artifacts import ArtifactAddress
    from powercontext.builtin.runtime.evidence_selection import _render
    from powercontext.builtin.runtime.prepared_context import EvidenceFragment, MemoryEntryAddress

    first = "Neratinib was added to cytokine-producing cultures."
    text = first + " These concentrations fell after " + ("a lengthy followup period " * 80) + "."
    ref = ArtifactRef(family="memory", artifact_id="memory", revision=1)
    address = MemoryEntryAddress(ArtifactAddress(scope_id="scope", artifact=ref), "entry", "version")
    budget = len(_render([EvidenceFragment(address, 0, len(first), first)]).encode())
    hit = MemoryHit(
        memory_ref=ref, entry_id="entry", entry_version_id="version", text=text, score=1, matched_by=("fts",)
    )
    built = PreparedContextBuilder().build_scopes_result(
        request=PrepareContextRequest(query="Neratinib cytokine", max_bytes=budget, evidence_selection=True),
        current_scope_id="scope",
        memory_candidates=(PreparedMemoryCandidates(scope_id="scope", hits=(hit,)),),
    )
    assert [f.text for f in built.fragments] == [first]
    assert built.context.content_bytes <= budget
