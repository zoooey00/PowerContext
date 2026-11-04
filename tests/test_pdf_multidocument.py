import pytest
from selftest_support.source_acceptance import persist

from powercontext.builtin.runtime import GetMemoryEntryRequest, open_builtin_runtime
from powercontext.sources import SourceDefinitionRegistry, project_source_for_transport
from powercontext.sources.pdf_pages import PDF_PAGE_SOURCE_DEFINITION, PDFPageInput, search_pdf_pages


@pytest.mark.asyncio
@pytest.mark.parametrize("company,query_name", [("ALPHA", "Alpha"), ("NORTHSTARLABS", "Northstar Labs")])
async def test_explicit_company_survives_competing_reports(tmp_path, company, query_name):
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    data = [
        (f"{company}_2025_10K", i, "Ordinary business operations and risk disclosures. " + str(i))
        for i in range(1, 121)
    ]
    data += [
        (
            "BETA_2025_10K",
            i,
            "Consolidated Statement of Income\nRevenue costs profit income restructuring costs income statements. "
            + str(i),
        )
        for i in range(1, 31)
    ]
    data += [(f"{company}_2025_10K", 121, "Consolidated Statement of Income\nNet sales 100\nOperating profit 20")]
    observations = [
        project_source_for_transport(
            registry,
            await registry.resolve(
                PDFPageInput(document_id=doc, document_sha256="a" * 64, page_number=page, text=text)
            ),
        )
        for doc, page, text in data
    ]
    config, scope, _ = await persist(tmp_path, PDF_PAGE_SOURCE_DEFINITION, observations)
    async with open_builtin_runtime(config) as runtime:
        memory = runtime.memory.for_scope(scope)
        citations = await search_pdf_pages(
            memory, f"What restructuring costs are in {query_name} income statements for 2025?", 20
        )
        entries = [(await memory.get(GetMemoryEntryRequest(citation=c))).entry.text for c in citations]
        assert any("Net sales 100" in text for text in entries)
        assert all(text.startswith(f"{company}_2025_10K\n") for text in entries)
