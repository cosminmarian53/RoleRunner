"""Unit tests for document extractor (PDF, DOCX, text) with MIME and size checks."""

from io import BytesIO

import pytest
from docx import Document
from reportlab.pdfgen import canvas

from backend.services.document_extractor import (
    DocumentExtractionError,
    detect_file_type,
    extract_document_text,
    validate_file_size,
)


def make_pdf_bytes(text: str = "Test resume text in PDF format.") -> bytes:
    buf = BytesIO()
    p = canvas.Canvas(buf)
    p.drawString(100, 750, text)
    p.showPage()
    p.save()
    return buf.getvalue()


def make_docx_bytes(text: str = "Test resume text in DOCX format.") -> bytes:
    buf = BytesIO()
    doc = Document()
    doc.add_paragraph(text)
    doc.save(buf)
    return buf.getvalue()


def test_validate_file_size_rejects_empty_and_oversized() -> None:
    with pytest.raises(DocumentExtractionError, match="file is empty"):
        validate_file_size(b"")

    large_content = b"x" * (9 * 1024 * 1024)
    with pytest.raises(DocumentExtractionError, match="exceeds maximum allowed limit"):
        validate_file_size(large_content)


def test_detect_file_type_magic_bytes() -> None:
    pdf_bytes = make_pdf_bytes()
    assert detect_file_type("resume.pdf", pdf_bytes) == "pdf"

    docx_bytes = make_docx_bytes()
    assert detect_file_type("resume.docx", docx_bytes) == "docx"

    assert detect_file_type("data.json", b'{"key": "val"}') == "json"
    assert detect_file_type("notes.txt", b"plain text") == "text"


def test_detect_file_type_rejects_mismatched_magic_bytes() -> None:
    with pytest.raises(DocumentExtractionError, match="Invalid PDF signature"):
        detect_file_type("fake.pdf", b"not a pdf")

    with pytest.raises(DocumentExtractionError, match="Invalid DOCX signature"):
        detect_file_type("fake.docx", b"not a docx")


def test_extract_document_text_pdf() -> None:
    pdf_bytes = make_pdf_bytes("Alice Smith - Senior Engineer")
    text, detected = extract_document_text("resume.pdf", pdf_bytes)

    assert detected == "pdf"
    assert "Alice Smith" in text
    assert "Senior Engineer" in text


def test_extract_document_text_docx() -> None:
    docx_bytes = make_docx_bytes("Bob Jones - Lead Developer")
    text, detected = extract_document_text("resume.docx", docx_bytes)

    assert detected == "docx"
    assert "Bob Jones - Lead Developer" in text


def test_extract_document_text_plain_text() -> None:
    plain_bytes = b"Charlie Brown\nPython Developer"
    text, detected = extract_document_text("resume.txt", plain_bytes)

    assert detected == "text"
    assert "Charlie Brown" in text
    assert "Python Developer" in text
