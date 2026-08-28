"""Document text extraction service with MIME validation, size bounds, and Markdown conversion."""

from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import Any

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
    """
    Extract text and embedded hyperlink annotations from a PDF document.

    Uses pypdf to read text layout-aware streams and parse embedded link
    annotations (/Annots, /URI, mailto:) ensuring contact links are preserved.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        pages_text: list[str] = []
        embedded_links: list[str] = []

        for page in reader.pages:
            # 1. Extract embedded PDF link annotations (/Annots)
            try:
                annots: Any = getattr(page, "annotations", None) or []
                for annot in annots:
                    annot_obj = annot.get_object() if hasattr(annot, "get_object") else annot
                    if isinstance(annot_obj, dict):
                        action = annot_obj.get("/A")
                        if isinstance(action, dict):
                            uri = action.get("/URI")
                            if uri:
                                uri_str = str(uri).strip()
                                if uri_str and uri_str not in embedded_links:
                                    embedded_links.append(uri_str)
            except Exception as annot_exc:
                logger.debug("Non-fatal error reading PDF annotations: %s", annot_exc)

            # 2. Extract page text
            page_text = ""
            try:
                page_text = page.extract_text(extraction_mode="layout") or ""
            except Exception:
                page_text = page.extract_text() or ""

            if page_text.strip():
                pages_text.append(page_text.strip())

        raw_text = "\n\n".join(pages_text)

        # 3. Append discovered embedded annotations if present
        if embedded_links:
            links_block = "\n".join(f"[Link: {link_url}]" for link_url in embedded_links)
            raw_text = f"{raw_text}\n\n{links_block}"

        cleaned = clean_extracted_text(raw_text)
        return convert_text_to_markdown_structure(cleaned)
    except Exception as exc:
        logger.error("Failed to parse PDF: %s", exc)
        raise DocumentExtractionError(f"Corrupt or unreadable PDF document: {exc}", status_code=422) from exc


def extract_text_from_docx(content: bytes) -> str:
    """Extract text from a DOCX document and convert to structured markdown."""
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
        raw_text = "\n\n".join(paragraphs)
        cleaned = clean_extracted_text(raw_text)
        return convert_text_to_markdown_structure(cleaned)
    except Exception as exc:
        logger.error("Failed to parse DOCX: %s", exc)
        raise DocumentExtractionError(f"Corrupt or unreadable DOCX document: {exc}", status_code=422) from exc


def extract_text_from_plain(content: bytes) -> str:
    """Extract text from plain text formats with encoding fallbacks."""
    for encoding in ("utf-8", "utf-16", "latin-1", "cp1252"):
        try:
            raw_text = content.decode(encoding).strip()
            cleaned = clean_extracted_text(raw_text)
            return convert_text_to_markdown_structure(cleaned)
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


def convert_text_to_markdown_structure(text: str) -> str:
    """
    Convert raw extracted document text into structured Markdown format.

    - Detects section headings and transforms them to markdown headers (## Section)
    - Normalizes bullet points into Markdown list items (- item)
    - Preserves contact header lines
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return text

    md_lines: list[str] = []
    heading_patterns = [
        r"^(professional\s+summary|summary|profile|about\s+me)$",
        r"^(work\s+experience|experience|employment\s+history|career\s+history)$",
        r"^(technical\s+skills|skills|technologies|core\s+competencies)$",
        r"^(education|academic\s+background|education\s+&\s+certifications)$",
        r"^(certifications|certificates|courses)$",
        r"^(projects|notable\s+projects|selected\s+projects)$",
        r"^(languages|spoken\s+languages)$",
        r"^(achievements|awards|honors)$",
    ]

    for idx, line in enumerate(lines):
        line_lower = line.lower()
        is_heading = False

        # First line is usually Candidate Name
        if idx == 0 and len(line.split()) <= 4 and not any(w in line_lower for w in ["curriculum", "resume", "cv"]):
            md_lines.append(f"# {line}\n")
            continue

        # Check section headings
        for pattern in heading_patterns:
            if re.match(pattern, line_lower):
                md_lines.append(f"\n## {line.title()}\n")
                is_heading = True
                break

        if is_heading:
            continue

        # Format bullet points as Markdown list items
        if line.startswith(("•", "-", "*", "–", "—")):
            clean_bullet = re.sub(r"^[•\-*–—]\s*", "", line).strip()
            md_lines.append(f"- {clean_bullet}")
        else:
            md_lines.append(line)

    return "\n".join(md_lines)


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
