# Copyright (c) 2026 OceanBase.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy at http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

"""Atomic physical-page extraction and immutable PDF evidence sources."""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import TYPE_CHECKING
from zlib import decompressobj

from pydantic import BaseModel, Field, StrictInt, field_validator

from powercontext.sources.definitions import AdapterSourceDefinition, SourceDefinition
from powercontext.sources.models import Source, SourceMaterialization
from powercontext.sources.projections import TextEvidence

if TYPE_CHECKING:
    from powercontext.artifacts import MemoryCitation


class _PDFIdentity(BaseModel):
    document_id: str

    @field_validator("document_id")
    @classmethod
    def require_document_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("document-id-is-blank")
        return value


class PDFDocumentInput(_PDFIdentity):
    """The complete, unmodified PDF file and its caller-assigned identity."""

    content: bytes


class PDFPageInput(_PDFIdentity):
    """Extracted text belonging to exactly one physical page of a revision."""

    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_number: StrictInt = Field(ge=1)
    text: str


class _ContentInspector:
    """Validate page/Form streams before pypdf's forgiving text extraction."""

    def __init__(self, reader):
        self.reader = reader
        self.visited = set()

    def resources(self, resources) -> None:
        if resources is None:
            return
        from pypdf.generic import DictionaryObject, NullObject

        resolved = resources.get_object()
        if isinstance(resolved, NullObject):
            return
        if not isinstance(resolved, DictionaryObject):
            raise TypeError("invalid-page-resources")
        objects = resolved.get("/XObject")
        if objects is None or isinstance(objects.get_object(), NullObject):
            return
        for resource in objects.get_object().values():
            obj = resource.get_object()
            if obj is None:
                raise ValueError("unresolved-page-resource")
            if obj.get("/Subtype") == "/Form":
                self.content(obj)

    def content(self, reference) -> None:
        from pypdf.generic import ArrayObject, ContentStream, NullObject, StreamObject

        obj = reference.get_object()
        if isinstance(obj, NullObject):
            return
        if isinstance(obj, ArrayObject):
            for member in obj:
                self.content(member)
            return
        if not isinstance(obj, StreamObject):
            raise TypeError("invalid-page-content")
        if id(obj) in self.visited:
            return
        self.visited.add(id(obj))
        self.encoding(obj)
        # Eagerly parse operations: malformed Form contents must not be caught
        # and quietly skipped later by the text extractor.
        _ = ContentStream(obj, self.reader).operations
        self.resources(obj.get("/Resources"))

    @staticmethod
    def encoding(stream) -> None:
        from pypdf.filters import decode_stream_data
        from pypdf.generic import ArrayObject, EncodedStreamObject, NameObject, NullObject

        filters = stream.get("/Filter", ArrayObject()).get_object()
        filters = filters if isinstance(filters, ArrayObject) else [filters]
        options = stream.get("/DecodeParms", NullObject()).get_object()
        options = options if isinstance(options, ArrayObject) else [options] * len(filters)
        encoded = stream._data
        for position, algorithm in enumerate(filters):
            if algorithm in ("/FlateDecode", "/Fl"):
                inflater = decompressobj()
                inflater.decompress(encoded)
                inflater.flush()
                if not inflater.eof:
                    raise ValueError("incomplete-compressed-pdf-stream")
            step = EncodedStreamObject()
            step._data = encoded
            step[NameObject("/Filter")] = algorithm
            if position < len(options):
                step[NameObject("/DecodeParms")] = options[position]
            encoded = decode_stream_data(step)


def parse_pdf_document(value: PDFDocumentInput) -> tuple[PDFPageInput, ...]:
    """Return every physical page, including blanks, or fail the entire file."""
    from pypdf import PdfReader

    content = value.content
    if not content or not content.lstrip().startswith(b"%PDF-") or b"%%EOF" not in content:
        raise ValueError("invalid-pdf-file")
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("pdf-needs-a-password")  # noqa: TRY301
        if not len(reader.pages):
            raise ValueError("pdf-has-no-physical-pages")  # noqa: TRY301
        digest = hashlib.sha256(content).hexdigest()
        inspector = _ContentInspector(reader)
        pages = []
        for physical_number, page in enumerate(reader.pages, start=1):
            if "/Contents" in page:
                inspector.content(page.raw_get("/Contents"))
            inspector.resources(page.get("/Resources"))
            text = page.extract_text()
            pages.append(
                PDFPageInput(
                    document_id=value.document_id,
                    document_sha256=digest,
                    page_number=physical_number,
                    text="" if text is None else text,
                )
            )
        return tuple(pages)
    except Exception as error:
        raise ValueError("cannot-parse-entire-pdf") from error


class PDFPageSource(Source):
    document_id: str
    document_sha256: str
    page_number: int
    text: str


class _PhysicalPageAdapter:
    name = "pdf-page"
    input_class = PDFPageInput
    source_class = PDFPageSource

    async def resolve(self, value: PDFPageInput, /) -> PDFPageSource:
        document_key = hashlib.sha256(value.document_id.encode("utf-8")).hexdigest()
        name = f"pdf-page:{document_key}:{value.document_sha256}:{value.page_number}"
        if len(name) > 256:
            name = "pdf-page-digest:" + hashlib.sha256(name.encode("ascii")).hexdigest()
        return PDFPageSource(
            name=name,
            materialization=SourceMaterialization.CAPTURED,
            **value.model_dump(),
        )

    async def read(self, source: PDFPageSource, /) -> PDFPageInput:
        return PDFPageInput.model_validate(source.model_dump())


class _PhysicalPageText:
    name = "powercontext.text-evidence"
    version = "1"
    source_class = PDFPageSource
    output_class = TextEvidence

    def project(self, source: PDFPageSource, /) -> TextEvidence:
        return TextEvidence(
            source_type="pdf-page",
            source_id=source.name,
            content=source.document_id + "\n" + source.text,
            metadata={
                "document_id": source.document_id,
                "document_sha256": source.document_sha256,
                "page_number": source.page_number,
            },
        )


PDF_PAGE_SOURCE_DEFINITION: SourceDefinition[PDFPageInput, PDFPageSource, PDFPageInput] = AdapterSourceDefinition(
    adapter=_PhysicalPageAdapter(),
    version="1",
    projections=(_PhysicalPageText(),),
)


async def search_pdf_pages(memory, question: str, limit: int = 10) -> tuple[MemoryCitation, ...]:
    """Search the current scoped Memory snapshot with a complete page catalog."""
    from powercontext.sources._pdf_retrieval import retrieve_pages

    if type(limit) is not int or limit < 0:
        raise ValueError("invalid-limit")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question-is-blank")
    return () if limit == 0 else await retrieve_pages(memory, question, limit)
