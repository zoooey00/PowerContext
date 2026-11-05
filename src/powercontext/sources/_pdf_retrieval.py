# Copyright (c) 2026 OceanBase.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy at http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

"""Snapshot-based page and passage retrieval over public scoped Memory records.

No corpus or index survives a request. The complete active page catalog comes
from Memory.list, avoiding search admission thresholds and candidate truncation.
All results retain the exact persisted citation from that same snapshot.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from powercontext.artifacts import MemoryCitation

_FUNCTION_WORDS = frozenset([
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "our",
    "should",
    "than",
    "that",
    "the",
    "their",
    "these",
    "they",
    "this",
    "those",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
    "answer",
    "assume",
    "assuming",
    "analyst",
    "calculate",
    "define",
    "details",
    "explicit",
    "explicitly",
    "fiscal",
    "fy",
    "give",
    "investment",
    "million",
    "millions",
    "only",
    "outline",
    "outlined",
    "perspective",
    "please",
    "provide",
    "question",
    "report",
    "reported",
    "reporting",
    "respond",
    "response",
    "shown",
    "state",
    "statement",
    "statements",
    "unadjusted",
    "use",
    "using",
    "usd",
    "year",
    "years",
])


def _stem(word: str) -> str:
    if len(word) > 5 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    if len(word) > 6 and word.endswith("ing"):
        word = word[:-3]
    elif len(word) > 5 and word.endswith("ed"):
        word = word[:-2]
    if len(word) > 3 and word[-2:] in ("tt", "pp", "nn"):
        word = word[:-1]
    return word


def _words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"([a-z])-\s*\n\s*([a-z])", r"\1\2", text)
    return [_stem(word) for word in re.findall(r"[a-z]+|\d+", text) if word not in _FUNCTION_WORDS]


@dataclass
class _Page:
    citation: MemoryCitation
    source_id: str
    document: str
    revision: str
    number: int
    text: str
    words: list[str]
    counts: Counter
    sections: set[str]


def _sections(text: str) -> set[str]:
    lines = [" ".join(line.lower().split()) for line in text.splitlines() if line.strip()]
    # A locator is necessary: real pages may contain several numbered items.
    locators = sum(bool(re.match(r"item\s+\d+[a-z]?\..*\s\d+$", line)) for line in lines)
    if locators >= 4:
        return set()
    labels = set()
    for line in lines:
        if len(line) > 115:
            continue
        if re.search(r"(?:statements? of (?:income|operations|earnings)|income statements?)", line):
            labels.add("income")
        if re.search(r"(?:statements? of cash flows?|cash flows? statements?)", line):
            labels.add("cash")
        if re.search(r"(?:balance sheets?|statements? of financial (?:position|condition))", line):
            labels.add("balance")
        if re.search(r"(?:legal proceedings|litigation|contingencies)[.: ]*$", line):
            labels.add("legal")
        if re.search(r"(?:business|geographic|operating|reportable) segments?|our (?:operations|divisions)", line):
            labels.add("geography")
        if re.fullmatch(
            r"(?:[a-z -]+ )?(?:europe|(?:north|south|latin) america|asia pacific|africa|middle east)", line
        ):
            labels.add("geography")
    return labels


def _catalog(records) -> list[_Page]:
    pages, seen = [], set()
    for record in records:
        refs = record.entry.sources
        if record.state != "active" or len(refs) != 1 or refs[0].source_type != "pdf-page":
            continue
        source_id = refs[0].source_id
        if source_id in seen:
            continue
        seen.add(source_id)
        name, _, text = record.entry.text.partition("\n")
        # Location is encoded by our own Source definition, not inferred from
        # printed page numbers in the extracted body.
        match = re.fullmatch(r"pdf-page:([a-f0-9]{64}):([a-f0-9]{64}):([1-9]\d*)", source_id)
        revision = match[1] + ":" + match[2] if match else source_id
        number = int(match[3]) if match else 0
        words = _words(text)
        pages.append(
            _Page(record.citation, source_id, name, revision, number, text, words, Counter(words), _sections(text))
        )
    return pages


def _choose_documents(pages: list[_Page], question: str) -> list[_Page]:
    """Match explicit issuer IDs while leaving unknown/opaque IDs unrestricted."""
    query = re.findall(r"[a-z0-9]+", question.lower())
    names = {"".join(query[start : start + size]) for start in range(len(query)) for size in range(1, 7)}
    matched = set()
    for document in {page.document for page in pages}:
        issuer = re.split(r"[_ -](?:19|20)\d{2}", document, maxsplit=1)[0]
        words = re.findall(r"[a-z0-9]+", issuer.lower())
        words = [word for word in words if word not in {"inc", "corp", "corporation", "company", "the"}]
        if words and "".join(words) in names:
            matched.add(document)
    years = re.findall(r"(?:19|20)\d{2}", question)
    if matched and years:
        latest = max(years)
        dated = {name for name in matched if re.search(rf"[_ -]{latest}(?:[_ -]|$)", name)}
        if dated:
            matched = dated
    return [page for page in pages if page.document in matched] if matched else pages


def _accounting_facets(question: str) -> dict[str, set[str]]:
    text = question.lower()
    facets: dict[str, set[str]] = {}

    def add(section: str, phrase: str) -> None:
        facets.setdefault(section, set()).update(_words(phrase))

    # Accounting concepts name the statement operands needed as evidence. They
    # never compute answers and are independent of companies, dates and labels.
    if re.search(r"income|earnings|profit|margin|p\s*&\s*l|\beps\b|tax rate", text):
        add("income", "income earnings operating profit revenue sales cost diluted shares tax")
    if re.search(r"cash|capex|ebitda|depreciation|amortization|d\s*&\s*a", text):
        add(
            "cash",
            "operating investing financing activities cash depreciation amortization property equipment expenditures",
        )
    if re.search(r"ebitda|interest coverage", text):
        add("income", "operating profit earnings interest expense")
    if re.search(r"equity|assets|liabilities|balance|working capital|current ratio|quick ratio|leverage|debt", text):
        add("balance", "assets liabilities equity debt cash inventory receivable current total")
    if re.search(
        r"return on|\bro[aei]c?\b|turnover|cash conversion|days (?:sales|payable|inventory)|\bd[isp]o\b", text
    ):
        add("income", "income revenue earnings sales cost")
        add("balance", "assets equity inventory receivable payable")
    if re.search(r"gross|inventory|payable", text):
        add("income", "cost goods sales revenue")
    if re.search(r"legal|lawsuit|litigation|battles", text):
        add("legal", "legal litigation lawsuit proceedings claims contingencies")
    if re.search(r"geograph|regions?|countries|operates", text):
        add("geography", "segments divisions geographic operations international america europe asia africa pacific")
    return facets


def _query(question: str) -> tuple[dict[str, float], dict[str, set[str]]]:
    vocabulary = set(_words(question))
    facets = _accounting_facets(question)
    domain = set().union(*facets.values()) if facets else set()
    weights = dict.fromkeys(vocabulary, 0.35 if domain else 1.0)
    for word in domain:
        weights[word] = 1.0
    # Terms describing a particular requested item retain their specificity.
    for word in vocabulary & set(_words("restructuring impairment dividend pension acquisition tax")):
        weights[word] = 1.5
    for word in weights:
        if word.isdigit():
            weights[word] = 0.08
    return weights, facets


class _SnapshotIndex:
    def __init__(self, pages: list[_Page]):
        self.pages = pages
        frequency = Counter(word for page in pages for word in page.counts)
        self.idf = {word: math.log1p((len(pages) - count + 0.5) / (count + 0.5)) for word, count in frequency.items()}
        self.average = sum(len(page.words) for page in pages) / max(1, len(pages))

    def lexical(self, counts: Counter, weights: dict[str, float], length: int) -> float:
        normalizer = 1.1 * (0.65 + 0.35 * length / max(1, self.average))
        return sum(
            weight * self.idf.get(word, 0) * 2.1 * counts[word] / (counts[word] + normalizer)
            for word, weight in weights.items()
            if counts[word]
        )

    def rank(self, weights: dict[str, float], facets: dict[str, set[str]], native: set[str]):
        scores, passages = {}, {}
        for number, page in enumerate(self.pages):
            scores[number] = self.lexical(page.counts, weights, len(page.words)) + 12 * len(
                page.sections & facets.keys()
            )
            # Short evidence passages compete independently of exhibit length.
            passages[number] = max(
                (
                    self.lexical(Counter(page.words[start : start + 100]), weights, 100)
                    for start in range(0, len(page.words), 65)
                ),
                default=0.0,
            )
        rankings = [(1.0, scores), (0.65, passages)]
        for section, terms in facets.items():
            focused = dict.fromkeys(terms, 1.0)
            field_scores = {
                i: self.lexical(page.counts, focused, len(page.words)) + (20 if section in page.sections else 0)
                for i, page in enumerate(self.pages)
            }
            rankings.append((0.7, field_scores))
        fused = defaultdict(float)
        for weight, channel in rankings:
            ordered = sorted(channel, key=lambda i: (-channel[i], self.pages[i].source_id))
            for rank, number in enumerate(ordered, 1):
                if channel[number] > 0:
                    fused[number] += weight / (12 + rank)
        for number, page in enumerate(self.pages):
            if page.source_id in native:
                fused[number] += 0.005
        ordered = sorted(fused, key=lambda i: (-fused[i], self.pages[i].source_id))
        return ordered, scores


def _include_continuations(index: _SnapshotIndex, ranked: list[int], limit: int) -> list[int]:
    # Reserve up to one fifth of the budget for adjacent physical pages. A
    # continued table need not repeat the query vocabulary or its section title.
    quota = min(4, limit // 5)
    selected = ranked[: max(1, limit - quota)]
    if len(selected) >= limit:
        return selected
    locations = {(page.revision, page.number): i for i, page in enumerate(index.pages) if page.number}
    for seed in ranked[:4]:
        page = index.pages[seed]
        for offset in (1, -1):
            neighbor = locations.get((page.revision, page.number + offset))
            if neighbor is not None and neighbor not in selected and index.pages[neighbor].words:
                selected.append(neighbor)
                if len(selected) >= limit:
                    return selected
    for number in ranked:
        if number not in selected:
            selected.append(number)
            if len(selected) >= limit:
                break
    return selected


async def retrieve_pages(memory, question: str, limit: int) -> tuple[MemoryCitation, ...]:
    from powercontext.builtin.runtime.models import GetMemoryEntryRequest, SearchMemoryRequest

    snapshot = await memory.list()
    pages = _choose_documents(_catalog(snapshot.entries), question)
    if not pages:
        return ()
    # Native search remains one recall signal; it does not define which stored
    # pages are allowed to enter the local reranker.
    hits = await memory.search(SearchMemoryRequest(query=question, mode="fts", limit=max(64, limit)))
    refs = {(hit.entry_id, hit.entry_version_id) for hit in hits.hits}
    native = {page.source_id for page in pages if (page.citation.entry_id, page.citation.entry_version_id) in refs}
    index = _SnapshotIndex(pages)
    weights, facets = _query(question)
    ranked, _ = index.rank(weights, facets, native)
    selected = _include_continuations(index, ranked, limit)
    citations = []
    for number in selected[:limit]:
        page = pages[number]
        record = await memory.get(GetMemoryEntryRequest(citation=page.citation))
        if len(record.entry.sources) == 1 and record.entry.sources[0].source_id == page.source_id:
            citations.append(record.citation)
    return tuple(citations)
