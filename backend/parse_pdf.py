"""Extract one JSON record per page from a text-based PDF."""

import argparse
import json
from pathlib import Path

import pymupdf


def extract_pages(pdf_bytes: bytes) -> list[tuple[int, str]]:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        if not document.is_pdf or document.needs_pass:
            raise ValueError("Provide an unencrypted PDF.")
        return [
            (number, page.get_text(sort=True))
            for number, page in enumerate(document, start=1)
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", type=Path, help="Path to the PDF")
    args = parser.parse_args()

    try:
        pages = extract_pages(args.pdf_path.read_bytes())
    except (OSError, ValueError, pymupdf.FileDataError) as error:
        parser.exit(1, f"Could not read {args.pdf_path}: {error}\n")

    for page_number, text in pages:
        print(json.dumps({"page_number": page_number, "text": text}))


if __name__ == "__main__":
    main()
