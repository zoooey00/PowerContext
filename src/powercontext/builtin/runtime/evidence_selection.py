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
        # Inflected forms such as "increased" already lose their final e;
        # normalize the uninflected form to the same comparison key.
        result.append(word[:-1] if word.endswith("e") and len(word) > 4 else word)
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
                *_sentence_boundaries(hit.text),
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
    sentences = _attach_references(_sentences(candidates), query, request.max_bytes, candidates)
    frequencies = Counter(term for _, terms in sentences for term in terms)
    weights = {term: 1 + math.log(1 + len(sentences) / (1 + frequencies[term])) for term in query}
    ranked = []
    for index, (fragment, terms) in enumerate(sentences):
        overlap = sum(weight for term, weight in weights.items() if term in terms)
        if overlap:
            coverage = overlap / max(sum(weights.values()), 1)
            score = overlap * (1 + coverage) / (1 + sum(terms.values()) / 80)
            score *= _evidence_weight(fragment.text)
            ranked.append((-score, index, fragment))
    ranked.sort(key=lambda item: (item[0], item[1]))
    selected, content = _budgeted_selection(ranked, candidates, request.max_bytes)
    if content is None:
        return PreparedContextBuild(PreparedContext(status="empty", content=None, content_bytes=0), ())
    return PreparedContextBuild(
        context=PreparedContext(status="ready", content=content, content_bytes=len(content.encode("utf-8"))),
        origins=tuple(fragment.address for fragment in selected),
        fragments=tuple(selected),
    )


def _budgeted_selection(ranked, candidates, budget):
    """Keep bounded alternatives instead of irrevocably taking the first span.

    Costs include merged citations, JSON escaping and the complete envelope.
    The beam bounds CPU/memory independently of the number of source sentences.
    """
    states = [(0.0, 0, [], None)]
    for negative_score, _, fragment in ranked[:48]:
        alternatives = list(states)
        for utility, _, selected, _ in states:
            trial = _extend_selection(selected, fragment, candidates)
            rendered = _render(trial)
            size = len(rendered.encode("utf-8"))
            if size <= budget:
                alternatives.append((utility - negative_score, size, trial, rendered))
        alternatives.sort(key=lambda state: (-state[0], state[1]))
        unique = {}
        for state in alternatives:
            unique.setdefault(state[3], state)
        # Preserve the empty option: an expensive earlier sentence must not
        # prevent a later pair of cheap, stronger sentences from competing.
        states = list(unique.values())[:31]
        states.append((0.0, 0, [], None))
    best = min(states, key=lambda state: (-state[0], state[1]))
    return best[2], best[3]


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


def _evidence_weight(text):
    """Distinguish reported observations from a study's proposed hypothesis.

    These cues affect ranking only; every returned character is still literal.
    Background and objective sentences remain eligible when no result is present.
    """
    lower = text.lower()
    if re.search(
        r"\b(?:aim(?:ed|s)? to|sought to|we hypothesi[sz]|we investigated whether|to determine whether|objective[s]?[: ])",
        lower,
    ):
        return 0.55
    if re.search(
        r"\b(?:we (?:found|show|demonstrat)|results? (?:show|demonstrat|indicat)|conclu(?:sion|de)|these (?:findings|results)|associated with|correlat|significantly|revealed|reduced|increased|decreased)\w*",
        lower,
    ):
        return 1.5
    return 1.0


def _sentence_boundaries(text):
    for match in re.finditer(r"(?<=[.!?。！？])\s+|\n+", text):  # noqa: RUF001
        prefix = text[: match.start()]
        # A soft line wrap is not the end of a scientific observation.
        if match.group().count("\n") == 1 and not prefix.endswith(tuple(".!?。！？")):  # noqa: RUF001
            continue
        if re.search(r"\b(?:et al|e\.g|i\.e|fig|eq|dr|prof|vs|approx)\.$", prefix, re.IGNORECASE):
            continue
        if re.search(r"\b[A-Z]\.$", prefix):
            continue
        yield match.end()


def _attach_references(sentences, query, budget, candidates):
    """Keep an otherwise unmatchable anaphoric result with its antecedent.

    Never join across entry identities or paragraphs. Keep the independently
    useful antecedent when the combined literal passage cannot fit the budget.
    """
    result = []
    for fragment, terms in sentences:
        if (
            result
            and not (query.keys() & terms.keys())
            and re.match(r"(?:It|They|This|These|Those|Such)\b", fragment.text)
        ):
            previous, previous_terms = result[-1]
            if previous.address == fragment.address and query.keys() & previous_terms.keys():
                source = next(
                    hit.text
                    for group in candidates
                    for hit in group.hits
                    if group.scope_id == fragment.address.memory.scope_id
                    and hit.memory_ref == fragment.address.memory.artifact
                    and hit.entry_id == fragment.address.entry_id
                    and hit.entry_version_id == fragment.address.entry_version_id
                )
                gap = source[previous.end : fragment.start]
                if not gap.strip() and gap.count("\n") < 2:
                    joined = EvidenceFragment(
                        fragment.address, previous.start, fragment.end, source[previous.start : fragment.end]
                    )
                    if len(_render([joined]).encode("utf-8")) <= budget:
                        result[-1] = (joined, previous_terms + terms)
                        continue
        result.append((fragment, terms))
    return result
