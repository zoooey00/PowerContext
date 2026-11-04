import pytest
from selftest_support.source_acceptance import persist

from powercontext.builtin.runtime import GetMemoryEntryRequest, open_builtin_runtime
from powercontext.sources import SourceDefinitionRegistry, project_source_for_transport
from powercontext.sources.pdf_pages import PDF_PAGE_SOURCE_DEFINITION, PDFPageInput, search_pdf_pages


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question,statement",
    [
        ("What is the return on equity?", "STATEMENTS OF OPERATIONS\nNet earnings 73\nNet sales 410"),
        ("What is free cash flow?", "STATEMENTS OF CASH FLOWS\nOperating activities 93\nPurchases of property 22"),
        ("What is the current ratio?", "BALANCE SHEETS\nCurrent assets 180\nCurrent liabilities 60"),
        ("What is asset turnover?", "STATEMENTS OF OPERATIONS\nNet sales 410\nNet earnings 73"),
        ("What is the return on equity?", "CONSOLIDATED   STATEMENTS\nOF OPERATIONS\nNet earnings 73"),
    ],
)
async def test_metric_question_recalls_inputs_not_repeated_metric_mentions(tmp_path, question, statement):
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    texts = [f"Discussion {i}. {question} This metric informs our outlook and strategy." for i in range(30)]
    texts.append(statement)
    observations = [
        project_source_for_transport(
            registry,
            await registry.resolve(
                PDFPageInput(document_id="report", document_sha256="a" * 64, page_number=i, text=text)
            ),
        )
        for i, text in enumerate(texts, 1)
    ]
    config, scope, _ = await persist(tmp_path, PDF_PAGE_SOURCE_DEFINITION, observations)
    async with open_builtin_runtime(config) as runtime:
        memory = runtime.memory.for_scope(scope)
        citations = await search_pdf_pages(memory, question, 20)
        entries = [(await memory.get(GetMemoryEntryRequest(citation=c))).entry.text for c in citations]
        assert any(statement in text for text in entries)
