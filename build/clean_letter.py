#!/usr/bin/env python3
"""Convert pdftotext -layout output of a Berkshire letter into Typst content.

Pipeline:
 1. Strip running headers and isolated page numbers.
 2. Insert blank lines around separators and where indentation jumps signal a
    new paragraph (the older letters separate paragraphs by leading indent, not
    by blank lines).
 3. Split into blocks (groups of non-blank lines separated by blank lines).
 4. Classify and render each block (heading, table, paragraph, bullet, sep).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


RUNNING_HEADER_RE = re.compile(r"^\s*BERKSHIRE\s+HATHAWAY\s+INC\.?\s*$", re.I)
PAGE_NUMBER_RE = re.compile(r"^\s*\d{1,3}\s*$")
SEP_LINE_RE = re.compile(r"^\s*\*{3,}\s*$")
# Dot leader: four or more dots separated by optional single spaces.
DOT_LEADER_RE = re.compile(r"(?:\.\s?){4,}\.")
BULLET_LINE_RE = re.compile(r"^\s*(?:‹|•|·)\s+")
FOOTNOTE_RE = re.compile(r"^\s*\*+\s+\S")
SHAREHOLDERS_INTRO_RE = re.compile(
    r"^To the Shareholders of Berkshire Hathaway Inc\.:", re.I
)
ASTERISK_FOOTER_RE = re.compile(r"^\s*\*\s*$")

# Paragraph break detection: a line that starts with this much (or more)
# leading whitespace, while the previous non-blank line started with less,
# marks a new paragraph in the older letters.
PARA_INDENT_THRESHOLD = 5


def leading_ws(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def normalise(text: str) -> list[str]:
    """Drop noise and insert blank lines around structural breaks."""
    raw = text.splitlines()

    # Stage 1: drop running headers and isolated page numbers.
    cleaned: list[str] = []
    for line in raw:
        stripped = line.rstrip()
        if RUNNING_HEADER_RE.match(stripped):
            continue
        if PAGE_NUMBER_RE.match(stripped) and stripped.strip():
            cleaned.append("")  # treat as blank
            continue
        cleaned.append(stripped)

    # Stage 2: insert blank lines around separator lines so they form their
    # own blocks, and break paragraphs on big indentation jumps.
    out: list[str] = []
    prev_nonblank_indent: int | None = None
    for line in cleaned:
        stripped = line.strip()

        # Separator -> isolate it.
        if SEP_LINE_RE.match(line):
            if out and out[-1] != "":
                out.append("")
            out.append(line)
            out.append("")
            prev_nonblank_indent = None
            continue

        # Blank line -> reset.
        if stripped == "":
            if out and out[-1] != "":
                out.append("")
            prev_nonblank_indent = None
            continue

        # Indentation-based paragraph break (older letters).
        indent = leading_ws(line)
        if (
            prev_nonblank_indent is not None
            and indent >= PARA_INDENT_THRESHOLD
            and indent >= prev_nonblank_indent + PARA_INDENT_THRESHOLD
        ):
            if out and out[-1] != "":
                out.append("")
        out.append(line)
        prev_nonblank_indent = indent

    return out


def split_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.strip() == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line.rstrip())
    if current:
        blocks.append(current)
    return blocks


def block_has_table_signals(block: list[str]) -> bool:
    """Detect tables both by dot leaders and by columnar number layout."""
    dot_lines = sum(1 for l in block if DOT_LEADER_RE.search(l))
    if dot_lines >= 2:
        return True
    # Wide-column heuristic: 3+ lines that have 2+ runs of 3+ spaces AND
    # contain at least one number — typical of small financial tables that
    # don't use dot leaders.
    columnar = 0
    for l in block:
        if len(re.findall(r" {3,}", l)) >= 2 and re.search(r"\d", l):
            columnar += 1
    if columnar >= 4 and columnar >= len(block) * 0.6:
        return True
    return False


def classify_block(block: list[str]) -> str:
    if all(SEP_LINE_RE.match(l) for l in block):
        return "sep"
    if block_has_table_signals(block):
        return "table"
    if any(BULLET_LINE_RE.match(l) for l in block):
        return "bullet"
    if len(block) == 1:
        line = block[0].strip()
        if (
            5 <= len(line) <= 90
            and not line.endswith(('.', ',', ';', ':', '?', '!', '”', '"'))
            and not line.startswith('*')
            and not DOT_LEADER_RE.search(line)
            and not SHAREHOLDERS_INTRO_RE.match(line)
            and re.match(r"^[A-Z0-9“”\"'].*", line)
            and not re.search(r"\d{3,}", line)  # avoid table fragments
        ):
            return "heading"
    return "para"


TYPST_ESCAPE = {
    "\\": "\\\\",
    "#": "\\#",
    "$": "\\$",
    "*": "\\*",
    "_": "\\_",
    "`": "\\`",
    "<": "\\<",
    ">": "\\>",
    "@": "\\@",
    "=": "\\=",
    "~": "\\~",
    "[": "\\[",
    "]": "\\]",
}


def typst_escape(s: str) -> str:
    return "".join(TYPST_ESCAPE.get(ch, ch) for ch in s)


def join_paragraph(block: list[str]) -> str:
    joined = " ".join(l.strip() for l in block)
    return re.sub(r"\s+", " ", joined).strip()


def render_table(block: list[str]) -> str:
    body = "\n".join(l.rstrip() for l in block)
    # Use raw block; the template configures small monospace styling.
    return f"#tablebox[\n```\n{body}\n```\n]\n"


def render_bullet(block: list[str]) -> str:
    items: list[str] = []
    current: list[str] = []
    for line in block:
        if BULLET_LINE_RE.match(line):
            if current:
                items.append(" ".join(current).strip())
            current = [BULLET_LINE_RE.sub("", line).strip()]
        else:
            current.append(line.strip())
    if current:
        items.append(" ".join(current).strip())
    body = "\n".join(f"- {typst_escape(item)}" for item in items if item)
    return body + "\n"


def render_heading(line: str) -> str:
    return f"== {typst_escape(line.strip())}\n"


def render_para(block: list[str], *, footnote: bool = False) -> str:
    text = typst_escape(join_paragraph(block))
    if footnote:
        return f"#footnoteblock[{text}]\n"
    return text + "\n"


def convert(text: str, year: int) -> str:
    lines = normalise(text)
    blocks = split_blocks(lines)

    pieces: list[str] = [
        '#import "_helpers.typ": *\n',
        f"= {year} Annual Letter <letter-{year}>\n",
    ]
    intro_seen = False

    for block in blocks:
        kind = classify_block(block)
        if kind == "sep":
            pieces.append("#sectionbreak\n")
            continue
        if kind == "table":
            pieces.append(render_table(block))
            continue
        if kind == "heading":
            pieces.append(render_heading(block[0]))
            continue
        if kind == "bullet":
            pieces.append(render_bullet(block))
            continue

        first = block[0].lstrip()
        is_footnote = bool(FOOTNOTE_RE.match(block[0]))
        is_intro = bool(SHAREHOLDERS_INTRO_RE.match(first))
        if is_intro:
            if intro_seen:
                continue
            intro_seen = True
            pieces.append(f"#letterintro[{typst_escape(first)}]\n")
            if len(block) > 1:
                pieces.append(render_para(block[1:]))
            continue
        pieces.append(render_para(block, footnote=is_footnote))

    return "\n".join(pieces)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: clean_letter.py <input.txt> <output.typ>", file=sys.stderr)
        return 2
    src = Path(argv[1])
    dst = Path(argv[2])
    year = int(src.stem)
    dst.write_text(convert(src.read_text(encoding="utf-8"), year), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
