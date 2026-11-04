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

"""Whole-document PDF extraction and offline, scoped evidence-page retrieval.

Extraction preserves physical page boundaries. Retrieval only uses public Memory
search/get operations; it has no filesystem, network or benchmark-data access.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import zlib
from collections import Counter
from itertools import pairwise
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, StrictInt, field_validator

from powercontext.sources.definitions import AdapterSourceDefinition, SourceDefinition
from powercontext.sources.models import Source, SourceMaterialization
from powercontext.sources.projections import TextEvidence

if TYPE_CHECKING:
    from powercontext.artifacts import MemoryCitation


class _DocumentIdentity(BaseModel):
    document_id: str

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("document-id-required")
        return value


class PDFDocumentInput(_DocumentIdentity):
    content: bytes


class PDFPageInput(_DocumentIdentity):
    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_number: StrictInt = Field(gt=0)
    text: str


def parse_pdf_document(value: PDFDocumentInput) -> tuple[PDFPageInput, ...]:
    """Materialize all physical pages or raise ValueError without partial output."""
    from pypdf import PdfReader

    raw = value.content
    if not raw.lstrip().startswith(b"%PDF-") or b"%%EOF" not in raw:
        raise ValueError("invalid-pdf-envelope")
    digest = hashlib.sha256(raw).hexdigest()
    try:
        reader = PdfReader(io.BytesIO(raw), strict=True)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("pdf-requires-password")  # noqa: TRY301
        result = []
        for number, page in enumerate(reader.pages, 1):
            # pypdf deliberately repairs some broken compressed streams and can
            # swallow Form extraction errors. Validate before accepting a page
            # so a damaged page cannot silently become an empty observation.
            visited: set[int] = set()
            if "/Contents" in page:
                _check_content(page.raw_get("/Contents"), visited)
            _check_resources(page.get("/Resources"), visited)
            result.append(
                PDFPageInput(
                    document_id=value.document_id,
                    document_sha256=digest,
                    page_number=number,
                    text=page.extract_text() or "",
                )
            )
        if not result:
            raise ValueError("pdf-has-no-pages")  # noqa: TRY301
        return tuple(result)
    except Exception as error:
        raise ValueError("pdf-cannot-be-completely-parsed") from error


def _check_content(reference, visited: set[int]) -> None:
    from pypdf.generic import ArrayObject, NullObject, StreamObject

    stream = reference.get_object()
    if isinstance(stream, NullObject):
        return
    if isinstance(stream, ArrayObject):
        for item in stream:
            _check_content(item, visited)
        return
    if not isinstance(stream, StreamObject):
        raise TypeError("invalid-pdf-content-stream")
    if id(stream) in visited:
        return
    visited.add(id(stream))
    _check_encoding(stream)
    _check_resources(stream.get("/Resources"), visited)


def _check_encoding(stream) -> None:
    from pypdf.generic import ArrayObject, EncodedStreamObject, NameObject, NullObject

    filters = stream.get("/Filter", ArrayObject()).get_object()
    if not isinstance(filters, ArrayObject):
        filters = [filters]
    parameters = stream.get("/DecodeParms", NullObject()).get_object()
    if not isinstance(parameters, ArrayObject):
        parameters = [parameters] * len(filters)
    data = stream._data
    for index, filter_name in enumerate(filters):
        if filter_name in ("/FlateDecode", "/Fl"):
            decoder = zlib.decompressobj()
            decoder.decompress(data)
            decoder.flush()
            if not decoder.eof:
                raise ValueError("incomplete-pdf-compression")
        stage = EncodedStreamObject()
        stage[NameObject("/Filter")] = filter_name
        if index < len(parameters):
            stage[NameObject("/DecodeParms")] = parameters[index]
        stage._data = data
        data = stage.get_data()


def _check_resources(reference, visited: set[int]) -> None:
    from pypdf.generic import NullObject

    if reference is None:
        return
    resources = reference.get_object()
    if isinstance(resources, NullObject) or "/XObject" not in resources:
        return
    objects = resources["/XObject"].get_object()
    if isinstance(objects, NullObject):
        return
    for reference in objects.values():
        obj = reference.get_object()
        if obj is None:
            raise ValueError("missing-pdf-resource")
        if obj.get("/Subtype") == "/Form":
            _check_content(reference, visited)


class PDFPageSource(Source):
    document_id: str
    document_sha256: str
    page_number: int
    text: str


class _PageAdapter:
    name = "pdf-page"
    input_class = PDFPageInput
    source_class = PDFPageSource

    async def resolve(self, value: PDFPageInput, /) -> PDFPageSource:
        # A canonical tuple avoids delimiter collisions and bounds even very
        # long document IDs. Text is deliberately not part of page identity.
        identity = json.dumps(
            [value.document_id, value.document_sha256, value.page_number],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return PDFPageSource(
            name="pdf-page:" + hashlib.sha256(identity).hexdigest(),
            materialization=SourceMaterialization.CAPTURED,
            **value.model_dump(),
        )

    async def read(self, source: PDFPageSource, /) -> PDFPageInput:
        return PDFPageInput(
            document_id=source.document_id,
            document_sha256=source.document_sha256,
            page_number=source.page_number,
            text=source.text,
        )


class _PageProjection:
    name = "powercontext.text-evidence"
    version = "1"
    source_class = PDFPageSource
    output_class = TextEvidence

    def project(self, source: PDFPageSource, /) -> TextEvidence:
        return TextEvidence(
            source_type="pdf-page",
            source_id=source.name,
            content=f"{source.document_id}\n{source.text}",
            metadata={
                "document_id": source.document_id,
                "document_sha256": source.document_sha256,
                "page_number": source.page_number,
            },
        )


PDF_PAGE_SOURCE_DEFINITION: SourceDefinition[PDFPageInput, PDFPageSource, PDFPageInput] = AdapterSourceDefinition(
    _PageAdapter(),
    version="1",
    projections=(_PageProjection(),),
)

_STOPWORDS = frozenset([
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "of",
    "to",
    "in",
    "on",
    "at",
    "for",
    "from",
    "by",
    "with",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "do",
    "does",
    "did",
    "have",
    "has",
    "had",
    "it",
    "its",
    "their",
    "they",
    "this",
    "that",
    "these",
    "those",
    "what",
    "which",
    "who",
    "how",
    "much",
    "many",
    "any",
    "can",
    "could",
    "would",
    "should",
    "will",
    "if",
    "then",
    "than",
    "not",
    "no",
    "only",
    "use",
    "using",
    "used",
    "shown",
    "details",
    "answer",
    "question",
    "respond",
    "response",
    "give",
    "assuming",
    "perspective",
    "investment",
    "analyst",
    "calculate",
    "define",
    "state",
    "explicitly",
    "outlined",
    "directly",
    "reported",
    "report",
    "fiscal",
    "fy",
    "year",
    "years",
    "usd",
    "million",
    "millions",
])

# General accounting vocabulary and metric inputs, independent of issuers,
# questions, evidence labels and the contents of any benchmark.
_CONCEPTS = (
    (
        r"geograph|countr|regions?|operates",
        "geographic countries international segments divisions operations north south america europe asia africa pacific",
    ),
    (r"legal|litigation|lawsuit|battles", "legal proceedings litigation contingencies lawsuits"),
    (r"capex|capital expend|free cash|fcf", "capital expenditures purchases property plant equipment cash flows"),
    (r"ebitda", "operating income depreciation amortization cash flows"),
    (r"restructur", "restructuring charges costs income"),
    (r"revenue|sales", "revenue revenues sales"),
    (r"profit|income|earnings|margin|p[ &]+l", "income earnings operations sales revenue"),
    (r"debt|leverage|borrow", "debt borrowings maturities indebtedness"),
    (r"dividend", "dividends shareholders"),
    (r"pension|retirement", "pension retirement benefits"),
    (r"acqui", "acquisition acquisitions purchase"),
    (r"return on (?:average )?equity|\broe\b", "net income shareholders equity"),
    (r"return on (?:average )?assets|\broa\b", "net income total assets"),
    (r"return on (?:invested )?capital|\broic\b", "operating income tax debt equity cash"),
    (r"current ratio|working capital|quick ratio|acid test", "current assets liabilities cash receivables"),
    (r"gross (?:profit|margin)", "net sales revenue cost goods sold"),
    (r"earnings per share|\beps\b", "earnings diluted basic shares income"),
    (r"inventory turnover|days.*inventory|\bdio\b", "cost sales inventories inventory"),
    (r"receivables turnover|days sales outstanding|\bdso\b", "net sales accounts receivable"),
    (r"days payable outstanding|\bdpo\b", "cost sales accounts payable"),
    (r"cash conversion cycle", "inventories receivables accounts payable cost sales"),
    (r"interest coverage", "operating income interest expense"),
    (r"asset turnover", "net sales revenue total assets"),
)


def _terms(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z]+|\d+", text.lower()) if word not in _STOPWORDS]


def _document_matches(names: set[str], question: str) -> set[str]:
    """Disambiguate explicit issuer names, leaving opaque IDs unrestricted."""
    words = re.findall(r"[a-z0-9]+", question.lower())
    phrases = {"".join(words[i : i + size]) for i in range(len(words)) for size in range(1, 6)}
    matches = set()
    for name in names:
        issuer = re.split(r"[_ -](?:19|20)\d{2}(?:[_ -]|$)", name, maxsplit=1)[0]
        if issuer == name:
            continue
        tokens = set(re.findall(r"[a-z0-9]+", issuer.lower())) - {"the", "inc", "corp", "corporation", "company"}
        if tokens and (tokens <= set(words) or "".join(re.findall(r"[a-z0-9]+", issuer.lower())) in phrases):
            matches.add(name)
    return matches


def _heading_bonus(text: str, query: set[str]) -> float:
    lines = [" ".join(line.lower().split()) for line in text.splitlines() if line.strip()]
    # Multiple numbered items can share a real disclosure page. A contents
    # entry additionally ends in a page locator; counting item headings alone
    # would suppress genuine legal/properties/mine-safety disclosures.
    if sum(bool(re.fullmatch(r"item\s+\d+[a-z]?[. :].{1,120}\s\d{1,4}", line)) for line in lines) >= 3:
        return 0.0
    headings = lines + [a + " " + b for a, b in pairwise(lines) if len(a) + len(b) < 120]
    sections = (
        (
            {"income", "earnings", "profit", "ebitda", "margin", "restructuring"},
            r"(?:consolidated |combined )?(?:statements? of (?:income|earnings|operations)|income statements?)",
        ),
        (
            {"cash", "capex", "ebitda", "depreciation", "amortization"},
            r"(?:consolidated |combined )?(?:statements? of cash flows?|cash flows? statements?)",
        ),
        (
            {"assets", "liabilities", "equity", "debt", "capital", "balance"},
            r"(?:consolidated |combined )?(?:balance sheets?|statements? of financial (?:position|condition))",
        ),
        ({"legal", "litigation", "lawsuits", "battles"}, r"(?:item\s*3[. : ]*)?legal proceedings"),
        (
            {"geographic", "segments", "geographies", "operates"},
            r"(?:our|reportable|operating|business) (?:segments|divisions)|item\s*1[. :]*business"
            r"|(?:[a-z -]+ )?(?:(?:north|south|latin|central) america|europe|asia(?: pacific)?|africa|middle east)",
        ),
    )
    return 16.0 * sum(
        bool(query & triggers) and any(re.fullmatch(pattern + r"[ .:]*(?:\(continued\))?", line) for line in headings)
        for triggers, pattern in sections
    )


async def search_pdf_pages(memory, question: str, limit: int = 10) -> tuple[MemoryCitation, ...]:
    """Retrieve real, distinct page citations without models or external state.

    Single-term recall queries avoid native multi-term admission dropping short
    statement pages. Candidate work is bounded per query; BM25 and statement
    headings rank the union. Every returned citation is read back before use.
    """
    from powercontext.builtin.runtime.models import SearchMemoryRequest

    if type(limit) is not int or limit < 0:
        raise ValueError("invalid-page-limit")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question-required")
    if limit == 0:
        return ()
    original = set(_terms(question))
    expanded = set(original)
    focused = set()
    for pattern, vocabulary in _CONCEPTS:
        if re.search(pattern, question.lower()):
            focused.update(_terms(vocabulary))
    expanded.update(focused)
    # Do not let conversational repetition determine term weights or call count.
    terms = sorted(expanded)
    queries = [" ".join(terms[i : i + 16]) for i in range(0, len(terms), 16)]
    queries += [term for term in terms if len(term) >= 3 and not term.isdigit()]
    hits = {}
    for query in dict.fromkeys(queries):
        page = await memory.search(SearchMemoryRequest(query=query, mode="fts", limit=max(512, limit * 16)))
        for hit in page.hits:
            key = (hit.memory_ref.artifact_id, hit.memory_ref.revision, hit.entry_id, hit.entry_version_id)
            hits[key] = hit
    if not hits:
        return ()
    return await _select_citations(memory, _rank_candidates(hits, question, expanded, focused), limit)


def _rank_candidates(hits, question: str, expanded: set[str], focused: set[str]):
    names = {hit.text.split("\n", 1)[0] for hit in hits.values()}
    requested = _document_matches(names, question)
    candidates = [
        (key, hit, Counter(_terms(hit.text.split("\n", 1)[-1])))
        for key, hit in hits.items()
        if not requested or hit.text.split("\n", 1)[0] in requested
    ]
    frequency = Counter(term for _, _, tokens in candidates for term in tokens)
    average = sum(tokens.total() for _, _, tokens in candidates) / max(1, len(candidates))
    ranked = []
    for key, hit, tokens in candidates:
        score = _heading_bonus(hit.text, expanded)
        norm = 1.2 * (0.4 + 0.6 * tokens.total() / max(average, 1))
        for term in expanded:
            count = tokens[term]
            if count:
                idf = math.log1p((len(candidates) - frequency[term] + 0.5) / (frequency[term] + 0.5))
                # Conversational adjectives such as "important" and "ongoing"
                # can have high IDF in an annual report without identifying the
                # requested accounting disclosure. Explicit domain vocabulary
                # must carry at least as much weight as the user's wording.
                weight = 1.0 if not focused or term in focused else 0.25
                if term.isdigit():
                    weight *= 0.2
                score += weight * idf * count * 2.2 / (count + norm)
        ranked.append((-score, key, hit))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return tuple(hit for _, _, hit in ranked)


async def _select_citations(memory, ranked, limit: int) -> tuple[MemoryCitation, ...]:
    from powercontext.artifacts import MemoryCitation
    from powercontext.builtin.runtime.models import GetMemoryEntryRequest

    selected, seen = [], set()
    for hit in ranked:
        citation = MemoryCitation(
            memory_ref=hit.memory_ref,
            entry_id=hit.entry_id,
            entry_version_id=hit.entry_version_id,
        )
        record = await memory.get(GetMemoryEntryRequest(citation=citation))
        sources = record.entry.sources
        pages = {(source.source_type, source.source_id) for source in sources if source.source_type == "pdf-page"}
        if len(pages) != 1 or len(sources) != 1 or pages & seen:
            continue
        seen.update(pages)
        selected.append(citation)
        if len(selected) == limit:
            break
    return tuple(selected)
