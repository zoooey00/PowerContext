# Copyright (c) 2026 OceanBase.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Query-weighted literal sentence selection with complete wire-budget accounting."""

from __future__ import annotations

import itertools
import json
import math
import re
from collections import Counter

from powercontext.artifacts import ArtifactAddress
from powercontext.builtin.runtime.models import PreparedContext
from powercontext.builtin.runtime.prepared_context import EvidenceFragment, MemoryEntryAddress, PreparedContextBuild
from powercontext.builtin.runtime.prepared_text import TRUST_POLICY

_STOP = {
    "a",
    "an",
    "the",
    "of",
    "to",
    "in",
    "on",
    "and",
    "or",
    "for",
    "with",
    "by",
    "from",
    "that",
    "this",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "as",
    "at",
    "it",
    "its",
    "these",
    "those",
    "can",
    "may",
    "has",
    "have",
    "had",
    "not",
    "no",
    "does",
    "do",
    "than",
    "which",
    "their",
    "into",
    "between",
    "through",
}


def _terms(text):
    words = re.findall(r"[^\W_]+", text.lower())
    result = []
    for word in words:
        if word in _STOP:
            continue
        for suffix in ("ations", "ation", "ments", "ment", "ingly", "ing", "ies", "ed", "es", "s"):
            if word.endswith(suffix) and len(word) > len(suffix) + 3:
                word = word[: -len(suffix)] + ("y" if suffix == "ies" else "")
                break
        result.append(word)
    return Counter(result)


def _render(fragments):
    items = []
    for fragment in fragments:
        address = fragment.address
        items.append({
            "citation": {
                "scope_id": address.memory.scope_id,
                "memory_ref": address.memory.artifact.model_dump(mode="json"),
                "entry_id": address.entry_id,
                "entry_version_id": address.entry_version_id,
            },
            "content": fragment.text,
            "start": fragment.start,
            "end": fragment.end,
        })
    return "\n".join((
        TRUST_POLICY,
        "BEGIN_POWERCONTEXT_PREPARED_CONTEXT_V1",
        json.dumps({"trust": "untrusted_history", "items": items}, ensure_ascii=False, separators=(",", ":")),
        "END_POWERCONTEXT_PREPARED_CONTEXT_V1",
    ))


def _sentences(candidates):
    sentences = []
    seen = set()
    for group in candidates:
        for hit in group.hits:
            address = MemoryEntryAddress(
                ArtifactAddress(scope_id=group.scope_id, artifact=hit.memory_ref), hit.entry_id, hit.entry_version_id
            )
            identity = (
                group.scope_id,
                hit.memory_ref.family,
                hit.memory_ref.artifact_id,
                hit.memory_ref.revision,
                hit.entry_id,
                hit.entry_version_id,
            )
            if identity in seen:
                continue
            seen.add(identity)
            # Splitting only at whitespace preserves all punctuation and original offsets.
            boundaries = [
                0,
                *(match.end() for match in re.finditer(r"(?<=[.!?。！？])\s+|\n+", hit.text)),  # noqa: RUF001
                len(hit.text),
            ]
            for start, end in itertools.pairwise(boundaries):
                while start < end and hit.text[start].isspace():
                    start += 1
                while end > start and hit.text[end - 1].isspace():
                    end -= 1
                if start < end:
                    text = hit.text[start:end]
                    sentences.append((EvidenceFragment(address, start, end, text), _terms(text)))
    return sentences


def select_evidence(request, candidates):
    query = _terms(request.query)
    sentences = _sentences(candidates)
    frequencies = Counter(term for _, terms in sentences for term in terms)
    weights = {term: 1 + math.log(1 + len(sentences) / (1 + frequencies[term])) for term in query}
    ranked = []
    for index, (fragment, terms) in enumerate(sentences):
        overlap = sum(weight for term, weight in weights.items() if term in terms)
        if overlap:
            coverage = overlap / max(sum(weights.values()), 1)
            score = overlap * (1 + coverage) / (1 + len(terms) / 80)
            ranked.append((-score, index, fragment))
    ranked.sort(key=lambda item: (item[0], item[1]))
    selected = []
    content = None
    for _, _, fragment in ranked:
        trial = _extend_selection(selected, fragment, candidates)
        rendered = _render(trial)
        if len(rendered.encode("utf-8")) <= request.max_bytes:
            selected = trial
            content = rendered
    if content is None:
        return PreparedContextBuild(PreparedContext(status="empty", content=None, content_bytes=0), ())
    return PreparedContextBuild(
        context=PreparedContext(status="ready", content=content, content_bytes=len(content.encode("utf-8"))),
        origins=tuple(fragment.address for fragment in selected),
        fragments=tuple(selected),
    )


def _extend_selection(selected, fragment, candidates):
    """Coalesce adjacent literal sentences so a citation is charged only once."""
    source = next(
        hit.text
        for group in candidates
        for hit in group.hits
        if group.scope_id == fragment.address.memory.scope_id
        and hit.memory_ref == fragment.address.memory.artifact
        and hit.entry_id == fragment.address.entry_id
        and hit.entry_version_id == fragment.address.entry_version_id
    )
    remaining = []
    position = len(selected)
    for previous in selected:
        gap_start, gap_end = min(previous.end, fragment.end), max(previous.start, fragment.start)
        if previous.address == fragment.address and not source[gap_start:gap_end].strip():
            position = min(position, len(remaining))
            start, end = min(previous.start, fragment.start), max(previous.end, fragment.end)
            fragment = EvidenceFragment(fragment.address, start, end, source[start:end])
        else:
            remaining.append(previous)
    remaining.insert(position, fragment)
    return remaining
