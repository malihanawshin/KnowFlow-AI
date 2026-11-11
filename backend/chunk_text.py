"""Split a page into passages without losing its page boundary."""

import textwrap


def chunk_text(text: str, max_chars: int = 1000) -> list[str]:
    paragraphs = text.strip().split("\n\n")
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        for part in textwrap.wrap(" ".join(paragraph.split()), width=max_chars,
                                  break_on_hyphens=False):
            combined = f"{current}\n\n{part}" if current else part
            if len(combined) > max_chars:
                chunks.append(current)
                current = part
            else:
                current = combined
    if current:
        chunks.append(current)
    return chunks
