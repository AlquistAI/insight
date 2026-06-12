#!/usr/bin/env python3
"""Convert a PDF to Markdown using the marker-pdf library."""

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pdf2md",
        description="Convert a PDF file to Markdown using marker-pdf. "
                    "Extracted images are saved to a sibling folder named after the output file.",
    )
    parser.add_argument("pdf", type=Path, help="Path to the input PDF file.")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Path to the output .md file (default: same name and folder as the PDF).",
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Overwrite the output file and image folder if they already exist.",
    )
    parser.add_argument(
        "-p", "--paginate",
        action="store_true",
        help="Insert page markers in the Markdown output "
             "(\"{page_id}\" followed by a horizontal rule between pages).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    pdf_path: Path = args.pdf
    if not pdf_path.is_file():
        print(f"error: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    md_path: Path = args.output if args.output is not None else pdf_path.with_suffix(".md")
    images_dir: Path = md_path.with_suffix("")

    if md_path.exists() and not args.force:
        print(f"error: {md_path} already exists (use --force to overwrite)", file=sys.stderr)
        return 1
    if images_dir.exists() and not args.force:
        print(f"error: {images_dir} already exists (use --force to overwrite)", file=sys.stderr)
        return 1

    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered
    except ImportError:
        print(
            "error: marker-pdf is not installed. Install it with: pip install marker-pdf",
            file=sys.stderr,
        )
        return 1

    config = {"paginate_output": True} if args.paginate else None
    converter = PdfConverter(artifact_dict=create_model_dict(), config=config)
    rendered = converter(str(pdf_path))
    text, _ext, images = text_from_rendered(rendered)

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(text, encoding="utf-8")

    if images:
        images_dir.mkdir(parents=True, exist_ok=True)
        for name, image in images.items():
            image.save(images_dir / name)

    print(f"wrote {md_path}" + (f" and {len(images)} image(s) in {images_dir}" if images else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
