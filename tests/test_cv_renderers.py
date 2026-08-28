"""Unit tests for ReportLab PDF and DOCX CV renderers."""

from pathlib import Path

from backend.services.document_extractor import detect_file_type, extract_document_text
from backend.services.docx_renderer import CVDocxRenderer
from backend.services.pdf_renderer import CVReportLabRenderer

SAMPLE_CV_MARKDOWN = """# Cosmin Lavric
**Web3 Security Researcher**
cosmin@test.com • +40 700 000 000 • Brasov, Romania • [GitHub](https://github.com/cosmin) • [LinkedIn](https://linkedin.com/in/cosmin)

Security Researcher specializing in smart contract security, invariant testing, and formal verification.

## Key Achievements
- Achieved 3rd Place (out of 723) in Kuru Contracts Cantina Audit Competition.
- Ranked Top 7% in Avon Protocol private audit competition.

## Technical Skills
- **Languages:** Rust, Solidity, Python, Move
- **Security Tools:** Foundry, Slither, Certora, Echidna

## Experience
### Independent Security Researcher | Cantina & CodeHawks | Aug 2025 - Present
- Discovered high-severity logic vulnerability in AMM vault.
- Conducted shadow audits on Aave V4 and Tier-1 DeFi protocols.

## Education & Certifications
- **Smart Contract Security** - Cyfrin (2025)
- **B.S. in Computer Science** - Transylvania University (2022 - 2026)
"""


def test_pdf_renderer_generates_valid_pdf_with_selectable_text(tmp_path: Path) -> None:
    renderer = CVReportLabRenderer()
    pdf_bytes = renderer.render_markdown_to_pdf_bytes(SAMPLE_CV_MARKDOWN)

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000

    # Test file output & extraction
    out_file = tmp_path / "rendered_cv.pdf"
    renderer.render_markdown_to_file(SAMPLE_CV_MARKDOWN, out_file)
    assert out_file.exists()

    # Validate with DocumentExtractor that text is selectable and complete
    file_type = detect_file_type(out_file.name, pdf_bytes)
    assert file_type == "pdf"

    extracted_text, _ = extract_document_text(out_file.name, pdf_bytes)
    assert "Cosmin Lavric" in extracted_text
    assert "Kuru Contracts" in extracted_text
    assert "Foundry" in extracted_text


def test_docx_renderer_generates_valid_docx(tmp_path: Path) -> None:
    renderer = CVDocxRenderer()
    docx_bytes = renderer.render_markdown_to_docx_bytes(SAMPLE_CV_MARKDOWN)

    # Valid ZIP/DOCX starts with PK\x03\x04
    assert docx_bytes.startswith(b"PK\x03\x04")
    assert len(docx_bytes) > 1000

    # Test file output & extraction
    out_file = tmp_path / "rendered_cv.docx"
    renderer.render_markdown_to_file(SAMPLE_CV_MARKDOWN, out_file)
    assert out_file.exists()

    file_type = detect_file_type(out_file.name, docx_bytes)
    assert file_type == "docx"

    extracted_text, _ = extract_document_text(out_file.name, docx_bytes)
    assert "Cosmin Lavric" in extracted_text
    assert "KEY ACHIEVEMENTS" in extracted_text or "Key Achievements" in extracted_text
    assert "Cyfrin" in extracted_text
