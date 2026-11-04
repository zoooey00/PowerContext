import base64
import io
import zlib

import pytest
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, EncodedStreamObject, IndirectObject, NameObject

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


@pytest.mark.parametrize("damaged", [False, True])
@pytest.mark.parametrize("encryption", [None, "RC4-128", "AES-128", "AES-256"])
def test_chained_compression_and_empty_password_with_real_text(damaged, encryption):
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    })
    stream = EncodedStreamObject()
    stream[NameObject("/Filter")] = ArrayObject([NameObject("/ASCII85Decode"), NameObject("/FlateDecode")])
    compressed = b"broken compression" if damaged else zlib.compress(b"BT /F1 12 Tf 10 100 Td (Revenue 12345) Tj ET")
    stream._data = base64.a85encode(compressed) + b"~>"
    page[NameObject("/Contents")] = writer._add_object(stream)
    if encryption:
        writer.encrypt(user_password="", owner_password="owner", algorithm=encryption)  # noqa: S106
    raw = io.BytesIO()
    writer.write(raw)
    value = PDFDocumentInput(document_id="permissions", content=raw.getvalue())
    if damaged:
        with pytest.raises(ValueError):
            parse_pdf_document(value)
    else:
        assert "Revenue 12345" in parse_pdf_document(value)[0].text
