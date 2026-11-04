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

"""Complete PDF physical pages as immutable, independently citable evidence."""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from collections import Counter

from pydantic import BaseModel, Field, StrictInt, field_validator

from powercontext.sources.definitions import AdapterSourceDefinition, SourceDefinition
from powercontext.sources.models import Source, SourceMaterialization
from powercontext.sources.projections import TextEvidence


class PDFDocumentInput(BaseModel):
    document_id: str
    content: bytes

    @field_validator("document_id")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("blank-document-id")
        return value


class PDFPageInput(BaseModel):
    document_id: str
    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_number: StrictInt = Field(gt=0)
    text: str

    @field_validator("document_id")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("blank-document-id")
        return value


def parse_pdf_document(value: PDFDocumentInput) -> tuple[PDFPageInput, ...]:
    """Extract every page before returning; any unreadable page fails the document."""
    from pypdf import PdfReader

    if not value.content.lstrip().startswith(b"%PDF-") or b"%%EOF" not in value.content:
        raise ValueError("invalid-pdf-envelope")
    digest = hashlib.sha256(value.content).hexdigest()
    try:
        reader = PdfReader(io.BytesIO(value.content))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("password-required")  # noqa: TRY301
        pages = tuple(
            PDFPageInput(
                document_id=value.document_id,
                document_sha256=digest,
                page_number=number,
                text=page.extract_text() or "",
            )
            for number, page in enumerate(reader.pages, start=1)
        )
        if not pages:
            raise ValueError("pdf-has-no-pages")  # noqa: TRY301
    except Exception as error:
        raise ValueError("cannot-completely-parse-pdf") from error
    return pages


class PDFPageSource(Source):
    document_id: str
    document_sha256: str
    page_number: int
    text: str


class _PDFPageAdapter:
    name = "pdf-page"
    input_class = PDFPageInput
    source_class = PDFPageSource

    async def resolve(self, value: PDFPageInput, /) -> PDFPageSource:
        key = json.dumps(
            (value.document_id, value.document_sha256, value.page_number), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        return PDFPageSource(
            name="pdf:" + hashlib.sha256(key).hexdigest(),
            materialization=SourceMaterialization.CAPTURED,
            **value.model_dump(),
        )

    async def read(self, source: PDFPageSource, /) -> PDFPageInput:
        return PDFPageInput.model_validate(source.model_dump())


class _PDFPageProjection:
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
    _PDFPageAdapter(), projections=(_PDFPageProjection(),)
)

_STOP = {
    "what",
    "is",
    "are",
    "was",
    "were",
    "the",
    "a",
    "an",
    "of",
    "in",
    "on",
    "for",
    "from",
    "and",
    "or",
    "as",
    "that",
    "this",
    "to",
    "has",
    "have",
    "had",
    "any",
    "its",
    "it",
    "how",
    "much",
    "many",
    "does",
    "do",
    "did",
    "by",
    "with",
    "at",
    "can",
    "only",
    "shown",
    "details",
    "answer",
    "question",
    "assuming",
    "perspective",
    "investment",
    "analyst",
    "reported",
    "report",
    "fiscal",
    "fy",
    "state",
    "explicitly",
    "outlined",
    "directly",
    "quantity",
    "then",
    "if",
    "not",
}
_EXPANSIONS = {
    "geographies": "geographic geography segments countries international",
    "operates": "operations segments",
    "legal": "litigation proceedings contingencies",
    "battles": "litigation proceedings lawsuits",
    "capex": "capital expenditures spending",
    "ebitda": "operating income depreciation amortization",
    "income": "earnings operations",
    "revenue": "sales revenues",
    "restructuring": "restructuring charges",
    "cash": "cash flows",
    "dividend": "dividends shareholders",
    "debt": "borrowings maturities indebtedness",
    "acquisition": "acquisitions purchase",
    "pension": "retirement benefits",
    "profit": "income earnings",
}


def _tokens(text):
    return Counter(word for word in re.findall(r"[a-z]+|\d+", text.lower()) if word not in _STOP)


async def search_pdf_pages(memory, question: str, limit: int = 10) -> tuple:
    """Search the scoped public Memory API and rank distinct literal page evidence."""
    from powercontext.builtin.runtime.models import SearchMemoryRequest

    if type(limit) is not int or limit < 0:
        raise ValueError("invalid-page-limit")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("blank-question")
    if limit == 0:
        return ()
    query = _tokens(question)
    expanded = Counter(query)
    for word in query:
        expanded.update(_tokens(_EXPANSIONS.get(word, "")))
    # Long questions face a multi-term admission floor in native Memory search.
    # Add independent term queries so a page containing one decisive financial
    # term reaches the reranker even when it misses the conversational wording.
    terms = tuple(expanded)
    queries = [" ".join(terms[offset : offset + 24]) for offset in range(0, len(terms), 24)]
    queries.extend(term for term in terms if len(term) >= 3 and not term.isdigit())
    hits = {}
    for query_text in dict.fromkeys(queries):
        page = await memory.search(SearchMemoryRequest(query=query_text, mode="fts", limit=max(256, limit * 32)))
        for hit in page.hits:
            key = (hit.memory_ref.artifact_id, hit.entry_id, hit.entry_version_id)
            hits[key] = hit
    if not hits:
        return ()
    return await _distinct_pages(memory, _rank_pages(_requested_documents(hits, question), query, expanded), limit)


def _rank_pages(hits, query, expanded):
    from powercontext.builtin.artifacts.memory import MemoryCitation

    documents = [(key, hit, _tokens(hit.text)) for key, hit in hits.items()]
    frequency = Counter(term for _, _, tokens in documents for term in tokens)
    average = sum(sum(tokens.values()) for _, _, tokens in documents) / len(documents)
    ranked = []
    for key, hit, tokens in documents:
        length = sum(tokens.values())
        score = 0.0
        for term in expanded:
            tf = tokens[term]
            if tf:
                idf = math.log(1 + (len(documents) - frequency[term] + 0.5) / (frequency[term] + 0.5))
                score += (
                    (1 if term in query else 0.45)
                    * idf
                    * tf
                    * 2.2
                    / (tf + 1.2 * (0.25 + 0.75 * length / max(average, 1)))
                )
        # Financial statements often contain the required numbers but few of
        # the explanatory words in a natural-language question. Match requested
        # report sections against headings, rather than rewarding incidental
        # mentions of those sections in notes or management commentary.
        score += _section_score(hit.text, query)
        ranked.append((-score, key, hit))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return tuple(
        MemoryCitation(memory_ref=hit.memory_ref, entry_id=hit.entry_id, entry_version_id=hit.entry_version_id)
        for _, _, hit in ranked
    )


async def _distinct_pages(memory, ranked, limit):
    from powercontext.builtin.runtime.models import GetMemoryEntryRequest

    selected, seen = [], set()
    for citation in ranked:
        entry = await memory.get(GetMemoryEntryRequest(citation=citation))
        pages = {(ref.source_type, ref.source_id) for ref in entry.entry.sources if ref.source_type == "pdf-page"}
        if len(pages) != 1 or pages & seen:
            continue
        seen.update(pages)
        selected.append(citation)
        if len(selected) == limit:
            break
    return tuple(selected)


def _section_score(text, query):
    head = text.lower()
    terms = set(query)
    sections = (
        (
            {"income", "earnings", "profit", "ebitda", "margin", "restructuring"},
            r"consolidated statements? of (?:income|earnings|operations)|consolidated income statements?",
        ),
        (
            {"cash", "capex", "ebitda", "depreciation", "amortization"},
            r"consolidated statements? of cash flows?|consolidated cash flow statements?",
        ),
        (
            {"assets", "liabilities", "equity", "balance", "debt", "capital"},
            r"consolidated balance sheets?|consolidated statements? of financial (?:position|condition)",
        ),
        ({"legal", "litigation", "battles", "lawsuits"}, r"item\s*3[. :]*legal proceedings"),
        (
            {"geographies", "geographic", "operates", "segments"},
            r"(?:our|reportable|operating|business) (?:divisions|segments)|item\s*1[. :]*business",
        ),
    )
    # Ignore contents pages: they mention all headings without their evidence.
    if len(re.findall(r"item\s+\d+[a-z]?[.]", head)) >= 3:
        return 0.0
    return 18.0 * sum(
        bool(terms & triggers)
        and any(re.fullmatch(pattern + r"[ .:]*(?:\(continued\))?", line.strip()) for line in head.splitlines())
        for triggers, pattern in sections
    )


def _requested_documents(hits, question):
    """Resolve explicit report identities before comparing their page scores.

    A financial question about one issuer must not be answered with a different
    issuer's identically titled statements. Only restrict when a report-name
    prefix actually occurs in the query; opaque IDs retain ordinary retrieval.
    """
    query_tokens = re.findall(r"[a-z0-9]+", question.lower())
    query_words = set(query_tokens)
    # Filenames commonly collapse spaces or punctuation in company names.
    query_names = {
        "".join(query_tokens[start : start + width]) for start in range(len(query_tokens)) for width in range(1, 5)
    }
    names = {hit.text.split("\n", 1)[0] for hit in hits.values()}
    matched = set()
    for name in names:
        prefix = re.split(r"[_ -](?:19|20)\d{2}(?:[_ -]|$)", name, maxsplit=1)[0]
        if prefix == name:
            continue
        words = set(re.findall(r"[a-z0-9]+", prefix.lower())) - {"inc", "corp", "corporation", "company", "the"}
        if words and (words <= query_words or re.sub(r"[^a-z0-9]", "", prefix.lower()) in query_names):
            matched.add(name)
    if not matched:
        return hits
    return {key: hit for key, hit in hits.items() if hit.text.split("\n", 1)[0] in matched}
