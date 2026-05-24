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

import json
import re
import sys
from pathlib import Path

CORRECTIONS_PATH = Path(__file__).with_name("corrections.json")


def load_corrections(year: int) -> list[tuple[str, str]]:
    if not CORRECTIONS_PATH.exists():
        return []
    data = json.loads(CORRECTIONS_PATH.read_text(encoding="utf-8"))
    return [tuple(pair) for pair in data.get(str(year), [])]


def apply_corrections(text: str, year: int) -> str:
    for find, replace in load_corrections(year):
        if find in text:
            text = text.replace(find, replace, 1)
        else:
            print(
                f"WARNING: correction for year {year} did not match: {find[:60]!r}",
                file=sys.stderr,
            )
    return text


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

# Performance-table detection ------------------------------------------------

PERF_YEAR_ROW_RE = re.compile(r"^\s*(?:19[6-9]\d|20[0-2]\d)\b.*\.\s?\.")
PERF_TITLE_KEYWORDS = ("performance", "corporate performance")


def is_perf_data(block: list[str]) -> bool:
    year_rows = sum(1 for l in block if PERF_YEAR_ROW_RE.match(l))
    return year_rows >= 5


def is_perf_summary(text_lower: str) -> bool:
    # The summary phrases must START a line in the perf table — otherwise
    # they're prose ("For the entire 42 years, our compounded annual gain
    # in per-share investments was 27.1%").
    return bool(
        re.search(r"(?:^|\n)\s*(?:compounded|average) annual gain", text_lower)
        or re.search(r"(?:^|\n)\s*overall gain\s*[–-]", text_lower)
    )


def is_perf_title(block: list[str]) -> bool:
    text = " ".join(block).strip()
    low = text.lower()
    if "berkshire" not in low or "s&p 500" not in low:
        return False
    if not any(k in low for k in PERF_TITLE_KEYWORDS):
        return False
    # Short title-only block, no big data run.
    return len(block) <= 8 and not is_perf_data(block)


def is_perf_notes(text_lower: str) -> bool:
    if "calendar years" in text_lower and "1965" in text_lower:
        return True
    if "s&p 500 numbers are pre-tax" in text_lower:
        return True
    if "starting in 1979, accounting rules" in text_lower:
        return True
    return False


def is_perf_preface(text_lower: str) -> bool:
    return "following table appears" in text_lower and "chairman" in text_lower


def is_perf_related(block: list[str]) -> bool:
    if is_perf_data(block):
        return True
    if is_perf_title(block):
        return True
    low = " ".join(block).lower()
    if is_perf_summary(low):
        return True
    if is_perf_notes(low):
        return True
    if is_perf_preface(low):
        return True
    return False

# Paragraph break detection: a line that starts with this much (or more)
# leading whitespace, while the previous non-blank line started with less,
# marks a new paragraph in the older letters.
PARA_INDENT_THRESHOLD = 5


def leading_ws(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


# Map a few private-use glyphs that pdftotext emits for Berkshire's custom
# em-dash and bullet to their standard Unicode equivalents.
PUA_REPLACEMENTS = {
    "": "—",   # em-dash variant used in 2000-era letters
    "": "•",   # alternate bullet
    "Š": "•",   # bullet glyph emitted in 2012/2013 source font (U+0160)
    "⎯": "—",   # horizontal line used as em-dash in 2003
}


HEADING_CANDIDATE_RE = re.compile(
    r"^[A-Z0-9“”\"']"           # starts with cap, digit, or opening quote
    r"[A-Za-z0-9\s,'’“”\"\-–—/&():.!?]{0,80}$"
)


SIGNATURE_DATE_RE = re.compile(
    r"^(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2}",
    re.I,
)
SIGNATURE_TITLE_RE = re.compile(
    r"^(?:Chairman|President|Vice\s+Chairman|Chief\s+Executive)\b", re.I
)
# A bare "Firstname M. Lastname" — typical signature at end of a section.
SIGNATURE_NAME_RE = re.compile(
    r"^[A-Z][a-z]+(?:\s+[A-Z]\.)?\s+[A-Z][a-z]+$"
)
MEMO_HEADER_RE = re.compile(
    r"^(?:Date|From|To|Subject|Re|Cc|Bcc)\s*:\s", re.I
)
# "(in $ millions) 2024 2023" – column-header line that introduces a table.
TABLE_COLHEADER_RE = re.compile(
    r"^\s*\(\s*in\s+(?:\$|US\$|U\.S\.\s*\$|euro|pound|millions|thousands|"
    r"billions)[^)]*\)", re.I
)


def looks_like_heading_line(line: str) -> bool:
    """Heuristic for a flush-left line that should be promoted to a heading."""
    stripped = line.strip()
    if not (5 <= len(stripped) <= 80):
        return False
    # Reject sentence-ending punctuation, but allow ! and ? since some
    # Buffett headings use them ("What is it with Omaha?", "Surprise!").
    if stripped.endswith(('.', ',', ';', ':')):
        return False
    if "$" in stripped or "%" in stripped:
        return False
    # Reject lines that look like inline financial data.
    if re.search(r"\d{1,3}(?:,\d{3})+", stripped):
        return False
    if re.search(r"\(\s*\d", stripped):
        return False
    # Reject signature blocks (date+name, job title, or bare name).
    if SIGNATURE_DATE_RE.match(stripped):
        return False
    if SIGNATURE_TITLE_RE.match(stripped):
        return False
    if SIGNATURE_NAME_RE.match(stripped):
        return False
    # Reject memo-style headers (Date:, From:, To:).
    if MEMO_HEADER_RE.match(stripped):
        return False
    # Reject table column-header lines like "(in $ millions) 2024 2023".
    if TABLE_COLHEADER_RE.match(stripped):
        return False
    if not HEADING_CANDIDATE_RE.match(stripped):
        return False
    # Most non-stopword tokens should start with a capital letter.
    tokens = [t for t in re.split(r"\W+", stripped) if t]
    if not tokens:
        return False
    stopwords = {
        # articles, prepositions, conjunctions
        "a", "an", "the", "of", "and", "or", "in", "on", "at", "to", "for",
        "with", "by", "from", "as", "vs", "into", "but", "nor", "yet", "so",
        # short pronouns and to-be verbs (lowercase in many sentence-case heads)
        "is", "it", "be", "are", "was", "were", "we", "us", "i", "you",
        "do", "did", "does", "if", "not", "no",
    }
    meaningful = [t for t in tokens if t.lower() not in stopwords]
    if not meaningful:
        return False
    # A single-word heading is OK only when flush-left (real section heading
    # at column 0). Otherwise it's almost certainly a column header in a
    # table ("Owned", "Average", "Gain to").
    if len(meaningful) < 2:
        indent_orig = len(line) - len(line.lstrip(" "))
        if indent_orig > 4:
            return False
    caps = sum(1 for t in meaningful if t[0].isupper() or t[0].isdigit())
    # Either strict title case (>= 50% caps) OR at least 2 capitalised
    # meaningful words — handles sentence-case heads with proper nouns,
    # e.g. "The Bet (or how your money finds its way to Wall Street)".
    return caps >= 2 or caps / len(meaningful) >= 0.5


def normalise(text: str, year: int | None = None) -> list[str]:
    """Drop noise and insert blank lines around structural breaks."""
    # Stage 0a: apply manual corrections (e.g. words lost by pdftotext).
    if year is not None:
        text = apply_corrections(text, year)
    # Stage 0b: map private-use glyphs.
    for src, dst in PUA_REPLACEMENTS.items():
        text = text.replace(src, dst)
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

    # Stage 3: isolate flush-left heading-like lines that didn't get a blank
    # line of their own (very common in pre-2010 letters where headings sit
    # at column 0 between indented paragraphs).
    out2: list[str] = []
    for i, line in enumerate(out):
        if line.strip() == "":
            out2.append(line)
            continue
        indent = leading_ws(line)
        if indent == 0 and looks_like_heading_line(line):
            # Check the previous non-blank line: only promote if previous
            # was a regular indented paragraph line (avoids splitting tables
            # and the in-progress sentence continuations).
            prev_idx = i - 1
            while prev_idx >= 0 and out[prev_idx].strip() == "":
                prev_idx -= 1
            prev_indent = leading_ws(out[prev_idx]) if prev_idx >= 0 else None
            prev_text = out[prev_idx].rstrip() if prev_idx >= 0 else ""
            # Only split if the previous line ended a sentence — avoids
            # cutting normal continuation lines that wrap to column 0.
            sentence_end = prev_text.endswith(('.', '!', '?', '”', '"', ')'))
            if prev_idx >= 0 and sentence_end:
                if out2 and out2[-1] != "":
                    out2.append("")
                out2.append(line)
                # Force a blank after too so it becomes its own block.
                # (Will be merged with following blank if present.)
                # We'll only insert if the next line is non-blank.
                if i + 1 < len(out) and out[i + 1].strip() != "":
                    out2.append("")
                continue
        out2.append(line)

    return out2


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


# Pattern for an enumerated list item — "(1)", "(a)", "1.", "i.", etc.
# Uses a lookahead for the trailing non-whitespace so that re.sub() can strip
# the marker without eating the first letter of the item body.
ENUM_ITEM_RE = re.compile(
    r"^\s{0,12}(?:\(?(?:\d{1,2}|[ivxIVX]{1,4}|[a-z])\)\.?|\d{1,2}\.)\s+(?=\S)"
)


def is_list_marker(line: str) -> bool:
    return bool(BULLET_LINE_RE.match(line) or ENUM_ITEM_RE.match(line))


def split_on_list_markers(blocks: list[list[str]]) -> list[list[str]]:
    """Split a block at any bullet-glyph occurrence that isn't on its first
    line — this undoes pdftotext's habit of merging the continuation of one
    bullet with the start of the next when no blank line sat between them.

    Only bullet glyphs trigger a split, not "(1)/(2)" enumerations: those
    appear inline in Buffett's prose too often (e.g. "criteria: (1) X, (2) Y")
    and would otherwise be mis-split.
    """
    out: list[list[str]] = []
    for block in blocks:
        current: list[str] = []
        for i, line in enumerate(block):
            if i > 0 and BULLET_LINE_RE.match(line):
                if current:
                    out.append(current)
                    current = []
            current.append(line)
        if current:
            out.append(current)
    return out


ORPHAN_FOOTNOTE_MARKER_RE = re.compile(r"^\s*\(\d+\)\s*$")
NUMERIC_ONLY_RE = re.compile(r"^[\s$%(),.\-\d]+$")


def merge_orphan_totals(blocks: list[list[str]]) -> list[list[str]]:
    """Re-attach a single-line numeric block that fell off the end of a table.

    pdftotext sometimes emits the totals row of a table as a separate
    paragraph when the row had different spacing in the source PDF; the
    block is short and contains only dollar amounts.
    """
    out: list[list[str]] = []
    for block in blocks:
        if (
            out
            and block_has_table_signals(out[-1])
            and len(block) == 1
            and len(block[0].strip()) > 0
            and NUMERIC_ONLY_RE.match(block[0].strip())
        ):
            out[-1].append(block[0])
        else:
            out.append(block)
    return out


def merge_orphan_footnote_markers(blocks: list[list[str]]) -> list[list[str]]:
    """A bare "(1)" / "(2)" line is a footnote marker abandoned by pdftotext.

    Drop the marker line; its meaning is gone but the surrounding text is
    cleaner without an orphan parenthesised digit.
    """
    return [b for b in blocks if not (len(b) == 1 and ORPHAN_FOOTNOTE_MARKER_RE.match(b[0]))]


def merge_bullet_continuations(blocks: list[list[str]]) -> list[list[str]]:
    """Merge non-bullet blocks that follow a bullet block when they're
    indented — these are bullet items whose body got orphaned across an
    original PDF page break. Threshold of 3 because a continuation across
    a page can land at the page's new left margin (e.g. indent 4) rather
    than at the deep bullet-text indent (e.g. 17).
    """
    out: list[list[str]] = []
    for block in blocks:
        if not block:
            continue
        starts_with_marker = is_list_marker(block[0])
        first_indent = len(block[0]) - len(block[0].lstrip())
        if (
            out
            and any(is_list_marker(l) for l in out[-1])
            and not starts_with_marker
            and first_indent >= 3
            and not block_has_table_signals(block)
            and not looks_like_heading_line(block[0])
        ):
            out[-1].extend(block)
        else:
            out.append(block)
    return out


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


def looks_like_table_caption(line: str) -> bool:
    """A line that introduces a table — not a section heading.

    Real section headings ("Insurance", "Acquisitions") can also precede a
    table, so we only demote lines that explicitly look like a table caption.
    """
    low = line.lower()
    if "balance sheet" in low:
        return True
    if "(in millions)" in low or "(in thousands)" in low or "(in $" in low:
        return True
    if re.search(r"\d{1,2}/\d{1,2}", line):
        return True
    # Column-header style: 2+ runs of 4+ spaces (column gutters).
    if len(re.findall(r" {4,}", line)) >= 2:
        return True
    return False


def classify_block(block: list[str], next_block: list[str] | None = None) -> str:
    if all(SEP_LINE_RE.match(l) for l in block):
        return "sep"
    if block_has_table_signals(block):
        return "table"
    if any(BULLET_LINE_RE.match(l) for l in block):
        return "bullet"
    # Single-line "(in $ millions) ..." block followed by a table → caption.
    if (
        len(block) == 1
        and TABLE_COLHEADER_RE.match(block[0].strip())
        and next_block is not None
        and block_has_table_signals(next_block)
    ):
        return "caption"
    if len(block) == 1 and looks_like_heading_line(block[0]):
        # Demote to caption only when both (a) the next block is a table AND
        # (b) the line itself reads like a table caption. This preserves real
        # section headings ("Insurance", "Investments") that happen to be
        # followed by a small data table.
        if (
            next_block is not None
            and block_has_table_signals(next_block)
            and looks_like_table_caption(block[0])
        ):
            return "caption"
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
        # Split items only on bullet glyphs; inline "(1)/(2)/(3)" enumerations
        # appear inside prose in Berkshire letters and must stay put.
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


def render_caption(line: str) -> str:
    text = typst_escape(line.strip())
    return f"\n#align(center)[#text(size: 10pt, style: \"italic\")[{text}]]\n"


def render_para(block: list[str], *, footnote: bool = False) -> str:
    text = typst_escape(join_paragraph(block))
    if footnote:
        return f"#footnoteblock[{text}]\n"
    return text + "\n"


def convert(text: str, year: int) -> tuple[str, list[list[str]]]:
    lines = normalise(text, year=year)
    blocks = split_blocks(lines)
    blocks = merge_orphan_totals(blocks)
    blocks = merge_orphan_footnote_markers(blocks)
    blocks = split_on_list_markers(blocks)
    blocks = merge_bullet_continuations(blocks)

    pieces: list[str] = [
        '#import "_helpers.typ": *\n',
        f"= {year} Annual Letter <letter-{year}>\n",
    ]
    intro_seen = False
    perf_blocks: list[list[str]] = []  # captured for appendix (2024 only)
    perf_title_seen = False

    for idx, block in enumerate(blocks):
        if is_perf_related(block):
            # Always strip from the main flow; capture for appendix on 2024.
            if is_perf_title(block):
                if not perf_title_seen:
                    perf_blocks.append(block)
                    perf_title_seen = True
            else:
                perf_blocks.append(block)
            continue

        # Look ahead to the next non-perf block for caption demotion.
        next_block = None
        for j in range(idx + 1, len(blocks)):
            if not is_perf_related(blocks[j]):
                next_block = blocks[j]
                break

        kind = classify_block(block, next_block)
        if kind == "sep":
            pieces.append("#sectionbreak\n")
            continue
        if kind == "table":
            pieces.append(render_table(block))
            continue
        if kind == "heading":
            pieces.append(render_heading(block[0]))
            continue
        if kind == "caption":
            pieces.append(render_caption(block[0]))
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

    return "\n".join(pieces), perf_blocks


def render_appendix(perf_blocks: list[list[str]]) -> str:
    pieces = [
        '#import "_helpers.typ": *\n',
        '= Appendix: Berkshire Performance, 1965–2024 <appendix-performance>\n',
        (
            "Warren Buffett opens every annual letter with the same multi-decade "
            "comparison: Berkshire's per-share results against the S&P 500. "
            "Rather than repeat twenty-five lightly-incremented copies of this "
            "table — one per letter — this edition keeps only the most recent "
            "version, taken verbatim from the 2024 letter. The earlier versions "
            "are available in the original PDFs at "
            "#link(\"https://www.berkshirehathaway.com/letters/letters.html\")"
            "[berkshirehathaway.com/letters].\n"
        ),
    ]
    for block in perf_blocks:
        low = " ".join(block).lower()
        if is_perf_notes(low) and not is_perf_data(block):
            pieces.append(render_para(block, footnote=True))
        elif is_perf_title(block):
            text = typst_escape(" ".join(block).strip())
            pieces.append(f"\n#align(center)[#text(size: 11pt, weight: \"bold\")[{text}]]\n")
        else:
            pieces.append(render_table(block))
    return "\n".join(pieces)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: clean_letter.py <input.txt> <output.typ>", file=sys.stderr)
        return 2
    src = Path(argv[1])
    dst = Path(argv[2])
    year = int(src.stem)
    body, perf_blocks = convert(src.read_text(encoding="utf-8"), year)
    dst.write_text(body, encoding="utf-8")
    if year == 2024 and perf_blocks:
        appendix_path = dst.parent / "_appendix.typ"
        appendix_path.write_text(render_appendix(perf_blocks), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
