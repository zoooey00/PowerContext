"""Additional lossless CSV and atomic validation boundaries."""

import asyncio
import json

import pytest

from powercontext.sources import SourceDefinitionRegistry
from powercontext.sources.csv_rows import CSV_ROW_SOURCE_DEFINITION, CSVDocumentInput, parse_csv_document
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY


@pytest.mark.parametrize(
    "content",
    [
        b"\n",
        b"id,note\n1,ok\n2,too,many\n",
        b'id,note\n1,ok\n2,"quoted"trailing\n',
        b"id,note\n1,ok\n ,blank\n",
        b"id,note\n1,ok\n\xff,bad\n",
    ],
)
def test_invalid_suffix_invalidates_entire_document(content):
    with pytest.raises(ValueError):
        parse_csv_document(CSVDocumentInput(document_id="document", primary_key="id", content=content))


def test_unicode_quoted_empty_values_and_primary_keys_remain_exact():
    rows = parse_csv_document(
        CSVDocumentInput(
            document_id="航班:一",
            primary_key=" id ",
            content='" id ",name,note\r\n key ,"机场,东","line one\r\nline two"\r\nkey,"",0001\r\n'.encode(),
        )
    )
    registry = SourceDefinitionRegistry((CSV_ROW_SOURCE_DEFINITION,))
    source = asyncio.run(registry.resolve(rows[0]))
    evidence = registry.project(source, TEXT_EVIDENCE_PROJECTION_KEY)
    assert asyncio.run(registry.read(source)) == rows[0]
    assert json.loads(evidence["content"]) == {" id ": " key ", "name": "机场,东", "note": "line one\r\nline two"}
    assert rows[1].values == ("key", "", "0001")
    assert rows[0].primary_key_value != rows[1].primary_key_value
