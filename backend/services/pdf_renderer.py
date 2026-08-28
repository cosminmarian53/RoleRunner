"""ReportLab PDF renderer creating clean, single-column, ATS-optimized CV documents."""

from __future__ import annotations

import io
import re
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
)

# Palette
PRIMARY_COLOR = HexColor("#1A202C")
SECONDARY_COLOR = HexColor("#2D3748")
ACCENT_COLOR = HexColor("#3182CE")
DIVIDER_COLOR = HexColor("#CBD5E0")
MUTED_COLOR = HexColor("#4A5568")


def build_pdf_styles():
    """Construct stylesheet optimized for high-readability single-column ATS CVs."""
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="CVName",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=PRIMARY_COLOR,
            alignment=0,  # Left align
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVTitle",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=ACCENT_COLOR,
            alignment=0,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVContact",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=MUTED_COLOR,
            alignment=0,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVSectionHeader",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=PRIMARY_COLOR,
            spaceBefore=8,
            spaceAfter=2,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVSubHeader",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=13,
            textColor=SECONDARY_COLOR,
            spaceBefore=4,
            spaceAfter=1,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVBody",
            fontName="Helvetica",
            fontSize=9,
            leading=12.5,
            textColor=SECONDARY_COLOR,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVBullet",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=SECONDARY_COLOR,
            leftIndent=12,
            firstLineIndent=-8,
            spaceAfter=2,
        )
    )

    return styles


class CVReportLabRenderer:
    """Renders structured Markdown CV text into an ATS-optimized PDF."""

    def __init__(self) -> None:
        self.styles = build_pdf_styles()

    def render_markdown_to_pdf_bytes(self, markdown_text: str) -> bytes:
        """Parse markdown lines and render directly to in-memory PDF bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=0.5 * inch,
            rightMargin=0.5 * inch,
            topMargin=0.4 * inch,
            bottomMargin=0.4 * inch,
        )

        story = []
        lines = markdown_text.splitlines()

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Level 1: Full Name
            if stripped.startswith("# "):
                name = stripped[2:].strip()
                story.append(Paragraph(f"<b>{name}</b>", self.styles["CVName"]))
                continue

            # Sub-title / Role (**Role**)
            if (
                stripped.startswith("**")
                and stripped.endswith("**")
                and not stripped.startswith("**Key")
                and not stripped.startswith("**Technical")
            ):
                title_text = stripped[2:-2].strip()
                story.append(Paragraph(title_text, self.styles["CVTitle"]))
                continue

            # Level 2 Section Header
            if stripped.startswith("## "):
                section_title = stripped[3:].strip().upper()
                story.append(Paragraph(f"<b>{section_title}</b>", self.styles["CVSectionHeader"]))
                story.append(HRFlowable(width="100%", thickness=0.75, color=DIVIDER_COLOR, spaceBefore=1, spaceAfter=4))
                continue

            # Level 3 Item Header (Role | Company | Date)
            if stripped.startswith("### "):
                role_header = stripped[4:].strip()
                # Bold the role parts
                clean_header = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", role_header)
                story.append(Paragraph(f"<b>{clean_header}</b>", self.styles["CVSubHeader"]))
                continue

            # Bullet points
            if stripped.startswith(("- ", "* ", "● ", "▪ ")):
                bullet_content = stripped[2:].strip()
                # Format bold markdown **text** to <b>text</b>
                html_bullet = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", bullet_content)
                html_bullet = re.sub(r"\[(.*?)\]\((.*?)\)", r'<font color="#3182CE"><u>\1</u></font>', html_bullet)
                story.append(Paragraph(f"&bull;  {html_bullet}", self.styles["CVBullet"]))
                continue

            # Regular paragraph text (Contact row or summary)
            if "•" in stripped or "@" in stripped:
                html_contact = re.sub(r"\[(.*?)\]\((.*?)\)", r'<font color="#3182CE"><u>\1</u></font>', stripped)
                story.append(Paragraph(html_contact, self.styles["CVContact"]))
            else:
                html_body = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", stripped)
                html_body = re.sub(r"\[(.*?)\]\((.*?)\)", r'<font color="#3182CE"><u>\1</u></font>', html_body)
                story.append(Paragraph(html_body, self.styles["CVBody"]))

        doc.build(story)
        return buffer.getvalue()

    def render_markdown_to_file(self, markdown_text: str, output_path: Path) -> Path:
        """Render markdown to a file on disk."""
        pdf_bytes = self.render_markdown_to_pdf_bytes(markdown_text)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)
        return output_path
