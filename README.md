# Berkshire Hathaway Letters to Shareholders, 2000–2024

A single re-typeset A4 PDF of Warren Buffett's annual shareholder letters for
fiscal years 2000 through 2024 (25 letters), assembled from the original PDFs
freely published at
[berkshirehathaway.com/letters](https://www.berkshirehathaway.com/letters/letters.html).

The output is `build/berkshire-2000-2024.pdf` — 402 A4 pages, set in EB
Garamond, with a clickable table of contents and a running year header.

## Why this exists

The originals jump between fonts, page sizes and scan qualities. Reading the
collection straight through is unpleasant. This repo re-flows the prose into a
single consistent volume — closer to Max Olson's commercial compilation but
limited to the post-2000 era and free to print.

## How it was built

1. `pdfs/` — the 25 source PDFs downloaded verbatim from berkshirehathaway.com.
2. `pdftotext -layout` extracts each PDF to `text/` (gitignored;
   regenerate with `for y in $(seq 2000 2024); do pdftotext -layout -nopgbrk pdfs/$y.pdf text/$y.txt; done`).
3. `build/clean_letter.py` turns each text file into a Typst document
   (`typ/<year>.typ`):
   - drops running headers and isolated page numbers
   - re-flows paragraphs (older letters separate them by indentation, not
     blank lines)
   - detects section headings, bullet lists, footnotes, and `* * *` breaks
   - preserves dot-leader and columnar tables as monospace blocks
4. `book.typ` is the master document. It sets up A4 page, body type,
   front matter, table of contents, and `#include`s each per-year file.

To rebuild from scratch:

```sh
for y in $(seq 2000 2024); do
  python3 build/clean_letter.py text/$y.txt typ/$y.typ
done
typst compile book.typ build/berkshire-2000-2024.pdf
```

## Known limitations

- A handful of section headings that sit flush-left in the source PDF are
  glued to the preceding paragraph rather than promoted to `==` headings;
  the indentation-jump heuristic doesn't catch them.
- Wide financial tables (notably the 60-year performance table) overflow the
  A4 text width slightly even at 7pt monospace; the columns remain aligned
  but the right edge can clip. Cropping or rotating those pages to landscape
  is a possible follow-up.
- Buffett's text is preserved verbatim; OCR artefacts in the original PDFs
  (a stray "ec onomic", "underwriting" hyphenations) are not corrected.

## Copyright

Warren Buffett's letters are public shareholder communications, freely
redistributed by Berkshire Hathaway. This compilation adds only the
typography; it is provided for personal reading.
