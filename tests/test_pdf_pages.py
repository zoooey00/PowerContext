"""PDF contracts exercised through extraction, projections and real Memory."""

import hashlib
import io
import zlib

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, EncodedStreamObject, NameObject
from selftest_support.source_acceptance import persist

from powercontext.builtin.runtime import GetMemoryEntryRequest, open_builtin_runtime
from powercontext.builtin.scope import ScopeDraft
from powercontext.sources import SourceDefinitionRegistry, project_source_for_transport
from powercontext.sources.pdf_pages import (
    PDF_PAGE_SOURCE_DEFINITION,
    PDFDocumentInput,
    PDFPageInput,
    parse_pdf_document,
    search_pdf_pages,
)
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY


def _pdf(*texts, password=None, broken=False):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=300, height=300)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({
                NameObject("/F1"): DictionaryObject({
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }),
            }),
        })
        stream = EncodedStreamObject()
        stream[NameObject("/Filter")] = NameObject("/FlateDecode")
        stream._data = zlib.compress(f"BT /F1 12 Tf 10 200 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    if broken:
        stream._data = stream._data[:-5]
    if password is not None:
        writer.encrypt(password, "owner")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


async def test_complete_revision_identity_and_projection():
    raw = _pdf("Revenue 123", "", "Net income 456")
    pages = parse_pdf_document(PDFDocumentInput(document_id="报表 / A", content=raw))
    assert [page.page_number for page in pages] == [1, 2, 3]
    assert [page.text.strip() for page in pages] == ["Revenue 123", "", "Net income 456"]
    assert {page.document_sha256 for page in pages} == {hashlib.sha256(raw).hexdigest()}
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    source = await registry.resolve(pages[0])
    assert source == await registry.resolve(pages[0])
    assert await registry.read(source) == pages[0]
    assert len(source.name) <= 256
    revised = parse_pdf_document(PDFDocumentInput(document_id="报表 / A", content=_pdf("Revenue 124")))[0]
    assert source.name != (await registry.resolve(revised)).name
    assert source.name != (await registry.resolve(pages[1])).name
    assert await registry.read(source) == pages[0]


@pytest.mark.parametrize("raw", [b"", b"not pdf", b"%PDF-1.7\n%%EOF", _pdf("Good", "Bad", broken=True)])
def test_malformed_document_fails_atomically(raw):
    with pytest.raises(ValueError):
        parse_pdf_document(PDFDocumentInput(document_id="test", content=raw))


def test_permission_marker_and_password():
    assert len(parse_pdf_document(PDFDocumentInput(document_id="test", content=_pdf("ok", password="")))) == 1
    with pytest.raises(ValueError):
        parse_pdf_document(PDFDocumentInput(document_id="test", content=_pdf("ok", password="secret")))  # noqa: S106


@pytest.mark.parametrize("document_id", ["", " \t\n"])
def test_document_id_required(document_id):
    with pytest.raises(ValueError):
        PDFDocumentInput(document_id=document_id, content=b"")


async def test_restart_distinct_pages_and_issuer_retrieval(tmp_path):
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    pages = [
        PDFPageInput(
            document_id="NORTHSTARLABS_2025_10K",
            document_sha256="a" * 64,
            page_number=1,
            text="Consolidated Statements of Income\nNet sales 100 Operating income 12",
        ),
        PDFPageInput(
            document_id="NORTHSTARLABS_2025_10K",
            document_sha256="a" * 64,
            page_number=2,
            text="Consolidated Statements of Cash Flows\nDepreciation 3 Capital expenditures 4",
        ),
        PDFPageInput(
            document_id="BETA_2025_10K",
            document_sha256="b" * 64,
            page_number=1,
            text="Consolidated Statements of Income\nOperating income depreciation capital expenditures",
        ),
    ]
    observations = [project_source_for_transport(registry, await registry.resolve(page)) for page in pages]
    config, scope, stored = await persist(tmp_path, PDF_PAGE_SOURCE_DEFINITION, observations)
    async with open_builtin_runtime(config) as runtime:
        memory = runtime.memory.for_scope(scope)
        query = "What is EBITDA less capex for Northstar Labs in 2025?"
        citations = await search_pdf_pages(memory, query, limit=20)
        assert len(citations) == 2
        assert await search_pdf_pages(memory, query, limit=0) == ()
        assert len(await search_pdf_pages(memory, query, limit=1)) == 1
        locations = set()
        for citation in citations:
            entry = (await memory.get(GetMemoryEntryRequest(citation=citation))).entry
            source = stored[entry.sources[0].source_id]
            metadata = source.projection(TEXT_EVIDENCE_PROJECTION_KEY)["metadata"]
            assert metadata["document_id"] == "NORTHSTARLABS_2025_10K"
            locations.add(metadata["page_number"])
        assert locations == {1, 2}
        other = await runtime.scopes.create(ScopeDraft(title="Empty", summary="Isolated", idempotency_key="empty"))
        empty_scope = runtime.memory.for_scope(other.scope_id)
        assert await search_pdf_pages(empty_scope, query) == ()


@pytest.mark.parametrize(
    ("question", "evidence", "distraction"),
    [
        (
            "Has Acme reported materially important ongoing legal battles in 2024?",
            "Item 2. Properties.\nOur facilities support production.\n"
            "Item 3. Legal Proceedings.\nLitigation claims remain pending.\n"
            "Item 4. Mine Safety Disclosures.\nNot applicable.",
            "Important ongoing employee programs were reported in 2024. "
            "Materially important programs and ongoing investment support operations. ",
        ),
        (
            "What geographies does Acme primarily operate in as of 2024?",
            "North America\nManufacturing and distribution.\nEurope\nRetail and wholesale.\n"
            "Asia Pacific\nRegional beverage operations.",
            "The board primarily operates important committees in 2024. "
            "Geographies and changes in operations are mentioned in general risk disclosures. ",
        ),
    ],
)
async def test_disclosure_survives_conversational_distractors(tmp_path, question, evidence, distraction):
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    texts = [evidence] + [distraction * 3 + str(i) for i in range(30)]
    observations = []
    for number, text in enumerate(texts, 1):
        page = PDFPageInput(document_id="ACME_2024_10K", document_sha256="c" * 64, page_number=number, text=text)
        observations.append(project_source_for_transport(registry, await registry.resolve(page)))
    config, scope, stored = await persist(tmp_path, PDF_PAGE_SOURCE_DEFINITION, observations)
    async with open_builtin_runtime(config) as runtime:
        memory = runtime.memory.for_scope(scope)
        citations = await search_pdf_pages(memory, question, limit=1)
        assert len(citations) == 1
        record = await memory.get(GetMemoryEntryRequest(citation=citations[0]))
        source = stored[record.entry.sources[0].source_id]
        assert source.projection(TEXT_EVIDENCE_PROJECTION_KEY)["metadata"]["page_number"] == 1
