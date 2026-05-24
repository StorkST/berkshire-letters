// Helper blocks used inside each per-letter file.

#let letterintro(body) = block(
  above: 1.2em, below: 1em,
  text(weight: "bold")[#body]
)

#let tablebox(body) = block(
  above: 1em, below: 1em, breakable: true,
  {
    set text(font: "DejaVu Sans Mono", size: 7pt)
    set par(justify: false, leading: 0.4em, first-line-indent: 0pt)
    body
  }
)

#let footnoteblock(body) = block(
  above: 0.8em, below: 0.8em,
  {
    set text(size: 9pt, style: "italic")
    set par(first-line-indent: 0pt)
    body
  }
)

#let sectionbreak = block(
  above: 0.9em, below: 0.9em,
  align(center)[
    #text(size: 10pt, tracking: 0.4em)[\* \* \*]
  ]
)
