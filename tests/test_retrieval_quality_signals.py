from powercontext.artifacts import ArtifactRef
from powercontext.builtin.artifacts.memory import MemoryHit
from powercontext.builtin.runtime import PrepareContextRequest
from powercontext.builtin.runtime.prepared_context import PreparedContextBuilder, PreparedMemoryCandidates


def test_observed_result_precedes_matching_study_objective():
    ref = ArtifactRef(family="memory", artifact_id="memory", revision=1)
    objective = "We aimed to determine whether exercise reduces blood pressure in adults."
    result = "Results showed that exercise significantly reduced blood pressure in adults by 12 mmHg."
    text = objective + " " + result
    hit = MemoryHit(
        memory_ref=ref, entry_id="entry", entry_version_id="version", text=text, score=1, matched_by=("fts",)
    )
    from powercontext.artifacts import ArtifactAddress
    from powercontext.builtin.runtime.evidence_selection import _render
    from powercontext.builtin.runtime.prepared_context import EvidenceFragment, MemoryEntryAddress

    fragment = EvidenceFragment(
        MemoryEntryAddress(ArtifactAddress(scope_id="scope", artifact=ref), "entry", "version"),
        len(objective) + 1,
        len(text),
        result,
    )
    budget = len(_render([fragment]).encode())
    built = PreparedContextBuilder().build_scopes_result(
        request=PrepareContextRequest(
            query="Exercise reduces blood pressure in adults", max_bytes=budget, evidence_selection=True
        ),
        current_scope_id="scope",
        memory_candidates=(PreparedMemoryCandidates(scope_id="scope", hits=(hit,)),),
    )
    assert len(built.fragments) == 1
    assert built.fragments[0].text == result
