#!/usr/bin/env python3
"""CLI utility to convert Markdown CV files to ATS-compliant PDFs."""

import argparse
import sys
from pathlib import Path

from backend.services.pdf_renderer import CVReportLabRenderer


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Markdown CV to ATS-friendly PDF")
    parser.add_argument("input_file", type=Path, help="Path to input Markdown CV file")
    parser.add_argument("-o", "--output", type=Path, help="Path to output PDF file", default=None)

    args = parser.parse_args()

    input_path: Path = args.input_file
    if not input_path.exists():
        print(f"Error: input file '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)

    output_path = args.output or input_path.with_suffix(".pdf")

    markdown_text = input_path.read_text(encoding="utf-8")
    renderer = CVReportLabRenderer()
    renderer.render_markdown_to_file(markdown_text, output_path)

    print(f"Successfully generated ATS CV PDF: {output_path}")


if __name__ == "__main__":
    main()
