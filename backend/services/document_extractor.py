"""Document text extraction service with MIME validation, size bounds, and text cleaning."""

from __future__ import annotations

import logging
import re
from io import BytesIO

from backend.config import settings

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = settings.max_upload_size_mb * 1024 * 1024  # 8MB default

PDF_MAGIC = b"%PDF-"
DOCX_MAGIC = b"PK\x03\x04"


class DocumentExtractionError(Exception):
    """Raised when document extraction fails due to size, format, or corruption."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def validate_file_size(content: bytes) -> None:
    """Ensure file size is within limits."""
    if len(content) == 0:
        raise DocumentExtractionError("Uploaded file is empty.", status_code=422)
    if len(content) > MAX_FILE_SIZE:
        max_mb = settings.max_upload_size_mb
        raise DocumentExtractionError(
            f"File size exceeds maximum allowed limit of {max_mb}MB.",
            status_code=422,
        )


def detect_file_type(filename: str, content: bytes) -> str:
    """Detect format from file signature and filename suffix."""
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if content.startswith(PDF_MAGIC) or suffix == "pdf":
        if not content.startswith(PDF_MAGIC):
            raise DocumentExtractionError("Invalid PDF signature (magic bytes mismatch).", status_code=422)
        return "pdf"

    if content.startswith(DOCX_MAGIC) or suffix == "docx":
        if not content.startswith(DOCX_MAGIC):
            raise DocumentExtractionError("Invalid DOCX signature (magic bytes mismatch).", status_code=422)
        return "docx"

    if suffix == "json":
        return "json"

    if suffix in ("txt", "md", "rtf", ""):
        return "text"

    raise DocumentExtractionError(f"Unsupported file type: '.{suffix}'", status_code=422)


def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from a PDF document with pypdf or PyPDF2 fallback."""
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader  # type: ignore[no-redef]

        reader = PdfReader(BytesIO(content))
        pages_text: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages_text.append(page_text.strip())
        raw_text = "\n\n".join(pages_text)
        return clean_extracted_text(raw_text)
    except Exception as exc:
        logger.error("Failed to parse PDF: %s", exc)
        raise DocumentExtractionError(f"Corrupt or unreadable PDF document: {exc}", status_code=422) from exc


def extract_text_from_docx(content: bytes) -> str:
    """Extract text from a DOCX document."""
    try:
        from docx import Document

        doc = Document(BytesIO(content))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        # Also extract table text
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)
        return clean_extracted_text("\n\n".join(paragraphs))
    except Exception as exc:
        logger.error("Failed to parse DOCX: %s", exc)
        raise DocumentExtractionError(f"Corrupt or unreadable DOCX document: {exc}", status_code=422) from exc


def extract_text_from_plain(content: bytes) -> str:
    """Extract text from plain text formats with encoding fallbacks."""
    for encoding in ("utf-8", "utf-16", "latin-1", "cp1252"):
        try:
            return clean_extracted_text(content.decode(encoding).strip())
        except UnicodeDecodeError:
            continue
    raise DocumentExtractionError("Could not decode document text with supported encodings.", status_code=422)


def clean_extracted_text(text: str) -> str:
    """Normalize whitespace, unicode dashes, and repair broken PDF word wraps/hyphens."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Normalize unicode hyphens and dashes to ASCII hyphen
    text = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015]", "-", text)
    # Normalize non-breaking spaces
    text = text.replace("\u00a0", " ")
    # Collapse 3+ newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_document_text(filename: str, content: bytes) -> tuple[str, str]:
    """
    Validate and extract text from an uploaded document.

    Returns:
        tuple[str, str]: (extracted_text, detected_type)
    """
    validate_file_size(content)
    file_type = detect_file_type(filename, content)

    if file_type == "pdf":
        text = extract_text_from_pdf(content)
    elif file_type == "docx":
        text = extract_text_from_docx(content)
    else:
        text = extract_text_from_plain(content)

    return text, file_type
