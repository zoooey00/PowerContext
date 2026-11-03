import pytest
from selftest_support.source_acceptance import persist

from powercontext.builtin.runtime import GetMemoryEntryRequest, open_builtin_runtime
from powercontext.sources import SourceDefinitionRegistry, project_source_for_transport
from powercontext.sources.pdf_pages import PDF_PAGE_SOURCE_DEFINITION, PDFPageInput, search_pdf_pages


@pytest.mark.asyncio
async def test_long_question_keeps_page_matching_one_distinctive_term(tmp_path):
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    texts = ("Xylophonereserve accumulated obligations.", "Company annual liquidity outlook.")
    observations = [
        project_source_for_transport(
            registry,
            await registry.resolve(
                PDFPageInput(
                    document_id="TEST_2025",
                    document_sha256="a" * 64,
                    page_number=index,
                    text=text,
                )
            ),
        )
        for index, text in enumerate(texts, 1)
    ]
    config, scope, _ = await persist(tmp_path, PDF_PAGE_SOURCE_DEFINITION, observations)
    async with open_builtin_runtime(config) as runtime:
        memory = runtime.memory.for_scope(scope)
        citations = await search_pdf_pages(
            memory, "company annual liquidity uncertainty xylophonereserve restructuring", 20
        )
        returned = [(await memory.get(GetMemoryEntryRequest(citation=c))).entry.text for c in citations]
        assert any("Xylophonereserve" in text for text in returned)
