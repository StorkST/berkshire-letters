// Berkshire Hathaway Shareholder Letters: 2000-2024
// A4 print edition, re-typeset from PDFs published at berkshirehathaway.com

#set document(
  title: "Berkshire Hathaway Letters to Shareholders 2000–2024",
  author: "Warren E. Buffett",
)

#set page(
  paper: "a4",
  margin: (top: 22mm, bottom: 22mm, inside: 22mm, outside: 18mm),
  numbering: "1",
  number-align: center,
)

#set text(font: "EB Garamond 12", size: 11pt, lang: "en", hyphenate: true)
#set par(justify: true, leading: 0.72em, spacing: 1em)

// Headings -----------------------------------------------------------------

#set heading(numbering: none)
#show heading: set text(font: "EB Garamond 12")
#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  v(1fr)
  align(center)[
    #text(size: 30pt, weight: "regular", tracking: 0.15em)[#it.body]
  ]
  v(1fr)
  pagebreak(weak: true)
}
#show heading.where(level: 2): it => {
  v(1.8em, weak: true)
  block(below: 0.9em)[
    #text(size: 14pt, weight: "bold")[#it.body]
  ]
}

// Running state for the current year header --------------------------------

#let current-year = state("year", none)
#show heading.where(level: 1): it => {
  current-year.update(it.body)
  pagebreak(weak: true)
  v(1fr)
  align(center)[
    #text(
      size: 26pt,
      weight: "regular",
      tracking: 0.08em,
      hyphenate: false,
    )[#it.body]
  ]
  v(1fr)
  pagebreak(weak: true)
}

#set page(
  paper: "a4",
  margin: (top: 22mm, bottom: 22mm, inside: 22mm, outside: 18mm),
  numbering: "1",
  number-align: center,
  header: context {
    let y = current-year.get()
    if y == none [] else [
      #set text(size: 9pt, fill: gray.darken(20%))
      #align(center)[#y]
      #v(-0.6em)
      #line(length: 100%, stroke: 0.4pt + gray.lighten(30%))
    ]
  },
)

// Raw block styling (used inside tablebox) ---------------------------------

#show raw.where(block: true): it => it
#show raw: set text(font: "DejaVu Sans Mono")

// --------------------------------------------------------------------------
// Front matter
// --------------------------------------------------------------------------

#set page(numbering: none, header: none)

#v(1fr)
#align(center)[
  #text(size: 36pt, weight: "regular", tracking: 0.05em)[Berkshire Hathaway]
  #v(0.4em)
  #text(size: 22pt, weight: "regular", style: "italic")[Letters to Shareholders]
  #v(0.8em)
  #text(size: 28pt, weight: "bold")[2000 — 2024]
  #v(2.5em)
  #text(size: 14pt, style: "italic")[Warren E. Buffett]
]
#v(1fr)
#align(center)[
  #text(size: 9pt, fill: gray.darken(20%))[
    Compiled from the public shareholder letters at berkshirehathaway.com/letters\
    Typeset in EB Garamond on A4
  ]
]
#pagebreak()

#align(center)[
  #text(size: 16pt, weight: "bold")[About this edition]
]
#v(1em)

This volume collects Warren Buffett's annual letters to Berkshire Hathaway shareholders for fiscal years 2000 through 2024 — twenty-five letters covering a quarter-century of capital-allocation commentary.

The source PDFs are freely published by Berkshire at #link("https://www.berkshirehathaway.com/letters/letters.html")[berkshirehathaway.com/letters]. They were extracted, re-flowed, and re-typeset in EB Garamond to deliver a consistent reading experience on A4 paper. Buffett's prose, including punctuation, italics, and the running #emph[\* \* \*] separators, is preserved verbatim. Financial tables are reproduced in a monospace face at smaller size to maintain their column alignment.

A handful of cosmetic artefacts from the original PDFs (page numbers, running headers such as "BERKSHIRE HATHAWAY INC.") have been stripped. Otherwise no editorial changes have been made.

#v(1em)
#align(right)[
  #text(size: 9pt, style: "italic")[Compiled #datetime.today().display("[month repr:long] [year]").]
]

#pagebreak()

// Table of Contents -------------------------------------------------------

#align(center)[
  #text(size: 18pt, weight: "bold")[Contents]
]
#v(1em)

#outline(title: none, depth: 1, indent: 0pt)

#pagebreak()

// --------------------------------------------------------------------------
// Body: chapters
// --------------------------------------------------------------------------

#set page(numbering: "1", header: context {
  let y = current-year.get()
  if y == none [] else [
    #set text(size: 9pt, fill: gray.darken(20%))
    #align(center)[#y]
    #v(-0.6em)
    #line(length: 100%, stroke: 0.4pt + gray.lighten(30%))
  ]
})
#counter(page).update(1)

#include "typ/2000.typ"
#include "typ/2001.typ"
#include "typ/2002.typ"
#include "typ/2003.typ"
#include "typ/2004.typ"
#include "typ/2005.typ"
#include "typ/2006.typ"
#include "typ/2007.typ"
#include "typ/2008.typ"
#include "typ/2009.typ"
#include "typ/2010.typ"
#include "typ/2011.typ"
#include "typ/2012.typ"
#include "typ/2013.typ"
#include "typ/2014.typ"
#include "typ/2015.typ"
#include "typ/2016.typ"
#include "typ/2017.typ"
#include "typ/2018.typ"
#include "typ/2019.typ"
#include "typ/2020.typ"
#include "typ/2021.typ"
#include "typ/2022.typ"
#include "typ/2023.typ"
#include "typ/2024.typ"

#include "typ/_appendix.typ"
