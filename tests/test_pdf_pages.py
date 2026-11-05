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


async def test_continued_table_with_no_repeated_query_words(tmp_path):
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    texts = [
        "Consolidated Statement of Cash Flows\nOperating cash 200\nInvesting activities",
        "Acquisition payments (7)\nProperty purchases (12)\nTotal (19)",
    ] + ["Working capital and operating cash estimates in sensitivity analysis. " * 4 for _ in range(28)]
    observations = []
    for number, text in enumerate(texts, 1):
        page = PDFPageInput(document_id="SEABIRD_2024_10K", document_sha256="d" * 64, page_number=number, text=text)
        observations.append(project_source_for_transport(registry, await registry.resolve(page)))
    config, scope, stored = await persist(tmp_path, PDF_PAGE_SOURCE_DEFINITION, observations)
    async with open_builtin_runtime(config) as runtime:
        citations = await search_pdf_pages(
            runtime.memory.for_scope(scope), "What is capex for Seabird in 2024?", limit=20
        )
        locations = set()
        for citation in citations:
            entry = (await runtime.memory.for_scope(scope).get(GetMemoryEntryRequest(citation=citation))).entry
            page = stored[entry.sources[0].source_id].projection(TEXT_EVIDENCE_PROJECTION_KEY)["metadata"][
                "page_number"
            ]
            locations.add(page)
        assert len(locations) == len(citations) <= 20
        assert {1, 2} <= locations


async def test_large_document_identity_is_bounded_and_distinct():
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    page = PDFPageInput(document_id="财务报表|" * 2000, document_sha256="e" * 64, page_number=10**150, text="")
    first = await registry.resolve(page)
    second = await registry.resolve(page.model_copy(update={"page_number": page.page_number + 1}))
    assert len(first.name) <= 256 and len(second.name) <= 256
    assert first.name != second.name
    assert await registry.read(first) == page


async def test_metric_operands_and_explicit_report_year(tmp_path):
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    statements = [
        "Consolidated Statements of Income\nNet sales 900 Cost of goods 500 Operating profit 120 "
        "Interest expense 10 Income taxes 20 Net earnings 90 Diluted shares 30",
        "Consolidated Balance Sheets\nCurrent assets 200 Current liabilities 100 "
        "Total assets 600 Shareholders equity 350 Accounts receivable 60 Inventory 70 Accounts payable 80",
        "Consolidated Statements of Cash Flows\nOperating activities cash 160 "
        "Depreciation and amortization 25 Purchases of property plant equipment 45",
    ]
    observations = []
    for year in (2023, 2024):
        texts = statements + ["Forward-looking risks involving assets, income and cash. " * 6 for _ in range(22)]
        for number, text in enumerate(texts, 1):
            page = PDFPageInput(
                document_id=f"SEABIRD_{year}_10K", document_sha256=str(year % 10) * 64, page_number=number, text=text
            )
            observations.append(project_source_for_transport(registry, await registry.resolve(page)))
    config, scope, stored = await persist(tmp_path, PDF_PAGE_SOURCE_DEFINITION, observations)
    cases = [
        ("current ratio", {2}),
        ("return on equity", {1, 2}),
        ("cash conversion cycle", {1, 2}),
        ("EPS", {1}),
        ("EBITDA", {1, 3}),
        ("capex", {3}),
    ]
    async with open_builtin_runtime(config) as runtime:
        memory = runtime.memory.for_scope(scope)
        for metric, required in cases:
            citations = await search_pdf_pages(memory, f"What is {metric} for Seabird in FY2024?", limit=20)
            locations = set()
            for citation in citations:
                entry = (await memory.get(GetMemoryEntryRequest(citation=citation))).entry
                meta = stored[entry.sources[0].source_id].projection(TEXT_EVIDENCE_PROJECTION_KEY)["metadata"]
                assert meta["document_id"] == "SEABIRD_2024_10K"
                locations.add(meta["page_number"])
            assert required <= locations
