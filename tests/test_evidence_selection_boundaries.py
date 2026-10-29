import json

from powercontext.artifacts import ArtifactRef
from powercontext.builtin.artifacts.memory import MemoryHit
from powercontext.builtin.runtime import PrepareContextRequest
from powercontext.builtin.runtime.prepared_context import PreparedContextBuilder, PreparedMemoryCandidates


def build(text, budget=1400):
    hit = MemoryHit(
        memory_ref=ArtifactRef(family="memory", artifact_id="memory", revision=1),
        entry_id="entry",
        entry_version_id="version",
        text=text,
        score=1,
        matched_by=("fts",),
    )
    groups = tuple(PreparedMemoryCandidates(scope_id=scope, hits=(hit,)) for scope in ("alpha", "beta"))
    return PreparedContextBuilder().build_scopes_result(
        request=PrepareContextRequest(query="cobalt 海洋", max_bytes=budget, evidence_selection=True),
        current_scope_id="alpha",
        memory_candidates=groups,
    )


def test_identical_text_across_scopes_keeps_each_identity():
    text = 'Unrelated preface. Cobalt 海洋 says "quoted" evidence. Unrelated appendix.'
    result = build(text, 1800)
    assert {fragment.address.memory.scope_id for fragment in result.fragments} == {"alpha", "beta"}
    assert result.origins == tuple(fragment.address for fragment in result.fragments)
    for fragment in result.fragments:
        assert fragment.text == text[fragment.start : fragment.end]
        assert fragment.start > 0
    assert result.context.content_bytes == len(result.context.content.encode("utf-8"))
    assert len(json.loads(result.context.content.splitlines()[-2])["items"]) == len(result.fragments)


def test_insufficient_total_budget_returns_legal_empty_context():
    result = build("Cobalt 海洋 evidence. " * 8, 512)
    assert result.context.content is None and result.context.content_bytes == 0
    assert result.fragments == result.origins == ()


def test_every_budget_includes_unicode_json_and_citation_bytes():
    text = "Cobalt 海洋 evidence. " * 8
    for budget in (600, 800, 1000, 1200, 1400):
        result = build(text, budget)
        assert result.context.content_bytes == len((result.context.content or "").encode("utf-8")) <= budget
