import io
import zlib

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, EncodedStreamObject, IndirectObject, NameObject

from powercontext.sources.pdf_pages import PDFDocumentInput, parse_pdf_document


@pytest.mark.parametrize("kind", ["damaged_deflate", "truncated_deflate", "damaged_form", "missing_content"])
def test_broken_page_contents_are_not_returned_as_blank_pages(kind):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    page = writer.add_blank_page(width=100, height=100)
    if kind != "missing_content":
        stream = EncodedStreamObject()
        stream[NameObject("/Filter")] = NameObject("/FlateDecode")
        stream._data = (
            zlib.compress(b"q Q")[:-4] if kind == "truncated_deflate" else b"not a valid compressed content stream"
        )
        if kind == "damaged_form":
            stream[NameObject("/Subtype")] = NameObject("/Form")
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/XObject"): DictionaryObject({NameObject("/Fm0"): writer._add_object(stream)})
            })
        else:
            page[NameObject("/Contents")] = writer._add_object(stream)
    else:
        page[NameObject("/Contents")] = IndirectObject(999, 0, writer)
    raw = io.BytesIO()
    writer.write(raw)
    with pytest.raises(ValueError):
        parse_pdf_document(PDFDocumentInput(document_id="broken", content=raw.getvalue()))


def test_valid_compressed_empty_page_remains_a_real_blank_page():
    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    stream = EncodedStreamObject()
    stream[NameObject("/Filter")] = NameObject("/FlateDecode")
    stream._data = zlib.compress(b"")
    page[NameObject("/Contents")] = writer._add_object(stream)
    raw = io.BytesIO()
    writer.write(raw)
    pages = parse_pdf_document(PDFDocumentInput(document_id="blank", content=raw.getvalue()))
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].text == ""
