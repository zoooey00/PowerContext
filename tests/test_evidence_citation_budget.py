from powercontext.artifacts import ArtifactAddress, ArtifactRef
from powercontext.builtin.artifacts.memory import MemoryHit
from powercontext.builtin.runtime import PrepareContextRequest
from powercontext.builtin.runtime.evidence_selection import _render
from powercontext.builtin.runtime.prepared_context import (
    EvidenceFragment,
    MemoryEntryAddress,
    PreparedContextBuilder,
    PreparedMemoryCandidates,
)
from powercontext.builtin.runtime.prepared_text import TRUST_POLICY


def test_short_literal_gap_costs_less_than_duplicate_citation():
    ref = ArtifactRef(family="memory", artifact_id="memory-" + "a" * 64, revision=1)
    address = MemoryEntryAddress(
        ArtifactAddress(scope_id="scope-" + "b" * 32, artifact=ref), "entry-" + "c" * 64, "version-" + "d" * 64
    )
    first = "Cobalt exposure increased inflammation by 30%."
    gap = " Samples were stored overnight. "
    last = "Cobalt withdrawal reduced inflammation by 25%."
    text = first + gap + last
    full = EvidenceFragment(address, 0, len(text), text)
    separate = [
        EvidenceFragment(address, 0, len(first), first),
        EvidenceFragment(address, len(first + gap), len(text), last),
    ]
    budget = len(_render([full]).encode())
    assert len(_render(separate).encode()) > budget
    hit = MemoryHit(
        memory_ref=ref,
        entry_id=address.entry_id,
        entry_version_id=address.entry_version_id,
        text=text,
        score=1,
        matched_by=("fts",),
    )
    built = PreparedContextBuilder().build_scopes_result(
        request=PrepareContextRequest(
            query="cobalt inflammation exposure withdrawal", max_bytes=budget, evidence_selection=True
        ),
        current_scope_id=address.memory.scope_id,
        memory_candidates=(PreparedMemoryCandidates(scope_id=address.memory.scope_id, hits=(hit,)),),
    )
    assert built.fragments == (full,)
    assert built.origins == (address,)
    assert built.context.content_bytes == budget
    assert built.context.content.startswith(TRUST_POLICY + "\n\nBEGIN_POWERCONTEXT_PREPARED_CONTEXT_V1\n")
