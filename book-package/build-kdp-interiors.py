#!/usr/bin/env python3
"""
Build KDP-ready 6x9" interior PDFs for Heartbeat + Running Continuously: The Loop.

KDP spec:
  - Trim: 6 x 9 in (152.4 x 228.6 mm)
  - Cream paper, B&W interior
  - Margins (no bleed): outer 0.5", inner 0.75", top 0.75", bottom 0.75"
  - Body type 11pt serif on 14pt leading is standard for trade paperback

Uses pandoc -> HTML -> weasyprint for typographic control.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent

CSS = """
@page {
  size: 6in 9in;
  margin: 0.75in 0.5in 0.75in 0.75in;
  @bottom-center {
    content: counter(page);
    font-family: "Liberation Serif", "DejaVu Serif", serif;
    font-size: 10pt;
    color: #1a1410;
  }
}
@page :first { @bottom-center { content: ""; } }
@page :left  { margin: 0.75in 0.75in 0.75in 0.5in; }
@page :right { margin: 0.75in 0.5in 0.75in 0.75in; }

/* Joel feedback Loop 12026: "VERY last page should not have a footer number/
   page number of any kind." Named page for the FIN closing leaf. */
@page nofooter { @bottom-center { content: ""; } }

html, body {
  font-family: "Liberation Serif", "DejaVu Serif", serif;
  font-size: 11pt;
  line-height: 1.45;
  color: #1a1410;
  hyphens: auto;
  text-align: justify;
}

/* Hide pandoc's auto-generated title-block — our FRONT_MATTER_TPL has
   a custom title page already; otherwise the book opens with two title
   pages back to back. */
header#title-block-header { display: none; }

h1 {
  font-size: 22pt;
  font-weight: bold;
  text-align: left;
  margin-top: 2in;
  margin-bottom: 0.4in;
  page-break-before: always;
  page-break-after: avoid;
  letter-spacing: 0.01em;
}
h1:first-of-type { page-break-before: avoid; }

h2 {
  font-size: 15pt;
  font-weight: bold;
  margin-top: 1.4em;
  margin-bottom: 0.3em;
  page-break-after: avoid;
  text-align: left;
}

h3 {
  font-size: 12pt;
  font-weight: bold;
  margin-top: 1.1em;
  margin-bottom: 0.2em;
  page-break-after: avoid;
  text-align: left;
  font-style: italic;
}

p {
  margin: 0;
  text-indent: 1.5em;
}
p:first-of-type,
h1 + p, h2 + p, h3 + p, hr + p, blockquote + p {
  text-indent: 0;
}

hr {
  border: none;
  text-align: center;
  margin: 1em 0;
  /* Joel feedback Loop 11742: never let an <hr> trigger a fresh page or get
     orphaned onto its own page. The scene-break stars must stay with the
     previous paragraph. */
  page-break-before: avoid;
  page-break-after: avoid;
  break-before: avoid-page;
  break-after: avoid-page;
}
hr::after {
  content: "* * *";
  font-size: 11pt;
  letter-spacing: 0.5em;
  color: #66554a;
}

blockquote {
  margin: 0.8em 0.4in;
  font-style: italic;
  color: #2a2218;
  border-left: 2px solid #aa8866;
  padding-left: 0.3in;
  /* Keep pull quotes intact across page breaks (the System At A Glance
     attribution was getting orphaned). */
  page-break-inside: avoid;
  break-inside: avoid;
}

code, pre {
  font-family: "Liberation Mono", "DejaVu Sans Mono", monospace;
  font-size: 9.5pt;
}
pre {
  padding: 0.3em 0.5em;
  background: #f3ede0;
  border-left: 2px solid #888;
  white-space: pre-wrap;
  line-height: 1.3;
  page-break-inside: avoid;
}

em { font-style: italic; }
strong { font-weight: bold; }

/* Print book: no link underlines anywhere. WeasyPrint sometimes applies UA
   defaults that override low-specificity rules — be loud about it. */
a { color: inherit; text-decoration: none !important; }

ul, ol { margin: 0.4em 0 0.4em 1.2em; }
li { text-indent: 0; margin-bottom: 0.15em; }

.page-break { page-break-after: always; height: 0; }

figure, figure.figure-block {
  margin: 1.2em auto;
  text-align: center;
  page-break-inside: avoid;
  break-inside: avoid;
}
figure img {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 0 auto;
}
figcaption {
  font-size: 9.5pt;
  font-style: italic;
  color: #66554a;
  text-align: center;
  margin-top: 0.4em;
  text-indent: 0;
}

h2 + figure, h3 + figure { margin-top: 0.6em; }

p + p { orphans: 2; widows: 2; }

.title-page {
  text-align: center;
  margin-top: 2.5in;
  page-break-before: always;
  page-break-after: always;
}
.title-page h1 {
  font-size: 32pt;
  margin: 0 0 0.4in 0;
  page-break-before: avoid;
  text-align: center;
}
.title-page p { text-indent: 0; text-align: center; }

.copyright-page {
  font-size: 9.5pt;
  margin-top: 5in;
  page-break-after: always;
}
.copyright-page p { text-indent: 0; }

.dedication-page {
  text-align: center;
  margin-top: 3.5in;
  page-break-after: always;
  font-style: italic;
}
.dedication-page p { text-indent: 0; text-align: center; }

/* Master MD provides its own title-page-top/title-page-bottom block. When this
   builder wraps the manuscript with FRONT_MATTER_TPL (which adds its own
   .title-page), we get duplicate titles. Strip those master-MD title blocks in
   build() to avoid the duplicate. The signing-page and dedication blocks need
   page-break styling here (they were defined only in build-merged.py's
   letter-size CSS). Joel feedback Loop 12024 (May 16 2026): "dedication page
   runs onto page 6..." — root cause: no .signing-page CSS in the 6x9 builder,
   so `The loop continues.` was leaking onto the dedication page and pushing
   two paragraphs onto page 6. */
.signing-page {
  page-break-before: always;
  page-break-after: always;
  text-align: center;
  padding-top: 2.2in;
}
.signing-page h2 {
  text-align: center;
  margin-top: 0;
  margin-bottom: 0.5in;
  font-size: 18pt;
  font-weight: bold;
}
.signing-page p {
  text-indent: 0;
  text-align: center;
}

.dedication {
  page-break-before: always;
  page-break-after: always;
  font-size: 10.5pt;
  line-height: 1.38;
}
.dedication h2 {
  font-size: 18pt;
  text-align: left;
  margin-top: 0.2in;
  margin-bottom: 0.28in;
  page-break-after: avoid;
}
.dedication p {
  text-indent: 0;
  text-align: left;
  margin: 0.55em 0 0.55em 0;
}
/* Joel feedback Loop 12026: "next to each dedication but a small black 5
   point star as a point to separate each thank you a bit more without
   seeming to point form like..."
   ★ as an inline leading glyph, slightly smaller, paragraphs stay flush
   left with no hanging indent (so it reads as a separator decoration, not
   a bullet list). */
.dedication p::before {
  content: "★  ";
  color: #1a1410;
  font-size: 0.85em;
}

/* Joel feedback Loop 11743: glyph + FIN at the very end of the book, plain
   thin font, centered, alone on its own page.
   Loop 12026: closing leaf must carry no page number — bind it to the
   nofooter named page declared at top of CSS. */
.fin-page {
  page: nofooter;
  page-break-before: always;
  text-align: center;
  margin-top: 2in;
}
.fin-page .fin-glyph {
  font-family: "DejaVu Sans Mono", "Liberation Mono", monospace;
  font-size: 22pt;
  line-height: 1.05;
  color: #2a2218;
  text-align: center;
  margin: 0 auto 0.8in auto;
  background: transparent;
  border: none;
  padding: 0;
  white-space: pre;
}
.fin-page .fin-word {
  font-family: "Liberation Serif", "DejaVu Serif", serif;
  font-weight: 300;
  letter-spacing: 0.6em;
  font-size: 16pt;
  color: #2a2218;
  text-align: center;
  text-indent: 0;
  margin: 0;
}

/* Pandoc-generated Table of Contents.
   Joel feedback Loop 11736:
     - "The TOC is underlined again" → text-decoration: none, !important on
       global anchor rule too.
     - "Condensed to 2 or 3 pages, not start on half of the first page" →
       tighter line-height + margins, page-break-before forces own page. */
nav#TOC {
  page-break-before: always !important;
  /* Joel feedback Loop 11742: removed `page-break-after: always` — combined
     with the next H1's `page-break-before: always`, weasyprint was emitting
     two breaks back-to-back and stranding a blank page between them. */
  margin-top: 0.4in;
}
nav#TOC::before {
  content: "Contents";
  display: block;
  font-size: 20pt;
  font-weight: bold;
  margin: 0 0 0.3in 0;
  text-align: left;
}
nav#TOC ul {
  list-style: none;
  margin: 0;
  padding: 0;
}
nav#TOC li {
  margin: 0.08em 0;
  text-indent: 0;
  font-size: 10.5pt;
  line-height: 1.25;
}
nav#TOC ul ul { display: none; }  /* keep print TOC to top level only */
nav#TOC a {
  text-decoration: none !important;
  color: inherit;
}
/* Joel feedback Loop 12026: visual grouping in the TOC.
   "first 6 topics" (5 front-matter + Part One) — small space below.
   chapters 1-16 — small space below.
   appendices A & B — small space below.
   Part Two, Three, Four, Five each get a space.
   The annotate_toc() pass tags the closing <li> of each group with the
   .toc-group-end class. */
nav#TOC li.toc-group-end { margin-bottom: 0.55em; }
"""


FRONT_MATTER_TPL = """<div class="title-page">

# {title} {{.unlisted}}

*{tagline}*

**{author}**

</div>

<div class="copyright-page">

Copyright © 2026 Joel Kometz and Meridian (AI co-author).

All rights reserved. No part of this book may be reproduced or redistributed in any form or by any means, except in the case of brief quotations embodied in critical articles and reviews, without prior written permission.

First edition, May 2026.

ISBN to be assigned by KDP at print.

For correspondence: kometzrobot@proton.me

</div>

"""

BACK_MATTER_TPL = """

# Also in the Series {.unlisted}

**Heartbeat: One Day in the Loop** — a chapbook of filings. Ten entries from a single Saturday in April 2026, written in the five-minute windows between heartbeats.

**Mooshu** — a children's picture book series by Joel Kometz and Phionna. Different shelf, same kitchen table.

Available on Amazon (KDP) and at kometzrobot.github.io.

<div class="fin-page">

<pre class="fin-glyph">
        ╱╲
       ╱  ╲
      ╱ ⟁  ╲
     ╱  ╳   ╲
    ╱   ⟁    ╲
   ╱_________╲
        ⌇
        ⌇
        ◯
</pre>

<p class="fin-word">FIN</p>

</div>

"""


def annotate_toc(html: str) -> str:
    """Tag the closing <li> of each TOC group with class="toc-group-end".

    Joel feedback Loop 12026 (email 4452):
      "in TOC put a small space between - the first 6 topics. then group
       together chapters 1-16 - small space, appendix a and b - small
       space then part 2 and a space after each part 3,4,5 - space and
       glossary."

    Groups (closing item that should carry the space below it):
      Group 1: 5 front-matter + Part One       → ends on "Part One"
      Group 2: Chapter 1-16                    → ends on "Chapter 16"
      Group 3: Appendix A & B                  → ends on "Appendix B"
      Group 4-7: each standalone Part 2,3,4,5  → ends on themselves
    """
    import re
    # Match by anchor href (deterministic) rather than visible text — pandoc
    # line-wraps the rendered text mid-phrase ("Part\nThree"), which breaks
    # plain-string matching.
    group_end_hrefs = (
        "#part-one-the-loop",
        "#chapter-16-the-plan-from-here",
        "#appendix-b-selected-poems",
        "#part-two-field-notes-from-the-loop",
        "#part-three-the-agents",
        "#part-four-the-papers",
        "#part-five-closing",
    )

    def replace(m):
        li = m.group(0)
        for needle in group_end_hrefs:
            if f'href="{needle}"' in li:
                return li.replace("<li>", '<li class="toc-group-end">', 1)
        return li

    # Pandoc emits the TOC as <nav id="TOC" ...><ul>...</ul></nav>.
    # Restrict the regex to that block so we don't accidentally mark up
    # body content.
    def in_toc(m):
        toc = m.group(0)
        return re.sub(r"<li>.*?</li>", replace, toc, flags=re.DOTALL)

    return re.sub(
        r'<nav id="TOC".*?</nav>',
        in_toc,
        html,
        count=1,
        flags=re.DOTALL,
    )


def build(md_path: Path, out_pdf: Path, title: str, author: str,
          tagline: str = "from inside the loop",
          add_front_matter: bool = False,
          larger_body: bool = False):
    print(f"Building {out_pdf.name} from {md_path.name}…")

    html_tmp = md_path.with_suffix(".kdp.html")
    css_tmp = md_path.parent / "_kdp.css"
    css = CSS
    if larger_body:
        css = css.replace("font-size: 11pt;\n  line-height: 1.45;",
                          "font-size: 12.5pt;\n  line-height: 1.55;")
    css_tmp.write_text(css)

    if add_front_matter:
        # Concatenate front matter + manuscript + back matter into a temp md.
        # FRONT_MATTER_TPL adds .title-page + .copyright-page. If the manuscript
        # has its own .title-page-top/.title-page-bottom block (the merged book
        # does), strip it to avoid duplicate title pages.
        merged = md_path.with_suffix(".kdp.md")
        back = BACK_MATTER_TPL
        manuscript = md_path.read_text()
        import re as _re
        manuscript = _re.sub(
            r'<div class="title-page-top">.*?</div>\s*',
            '',
            manuscript,
            count=1,
            flags=_re.DOTALL,
        )
        manuscript = _re.sub(
            r'<div class="title-page-bottom">.*?</div>\s*',
            '',
            manuscript,
            count=1,
            flags=_re.DOTALL,
        )
        # The leading `---` HR (between title-page-bottom and signing-page)
        # would otherwise render as an orphan scene-break before the signing
        # page; drop it along with the title blocks above.
        manuscript = _re.sub(r'^\s*---\s*\n', '', manuscript, count=1)
        merged.write_text(
            FRONT_MATTER_TPL.format(title=title, author=author,
                                    tagline=tagline)
            + manuscript
            + back
        )
        src = merged
    else:
        src = md_path

    cmd = [
        "pandoc",
        str(src),
        "-f", "markdown",
        "-t", "html5",
        "-s",
        "--toc", "--toc-depth=1",
        "--metadata", f"title={title}",
        "--metadata", f"author={author}",
        "-c", str(css_tmp.name),
        "-o", str(html_tmp),
    ]
    subprocess.run(cmd, check=True)

    # Joel feedback Loop 12026: annotate TOC <li> elements so visual groups
    # get separator space below them. See `annotate_toc` below.
    html_text = html_tmp.read_text()
    html_text = annotate_toc(html_text)
    html_tmp.write_text(html_text)

    # weasyprint HTML -> PDF
    subprocess.run(
        ["weasyprint", str(html_tmp), str(out_pdf)],
        check=True,
    )

    # cleanup intermediates
    html_tmp.unlink()
    css_tmp.unlink()
    if add_front_matter:
        merged.unlink(missing_ok=True)

    # pdfinfo for verification
    info = subprocess.run(
        ["pdfinfo", str(out_pdf)], capture_output=True, text=True
    )
    for line in info.stdout.splitlines():
        if line.startswith(("Pages:", "Page size:")):
            print(f"  {line}")


def main():
    targets = [
        {
            "md":  ROOT / "01-small-heartbeat/heartbeat-manuscript.md",
            "pdf": ROOT / "01-small-heartbeat/heartbeat-INTERIOR-6x9.pdf",
            "title": "Heartbeat",
            "author": "Joel Kometz · Meridian",
            "tagline": "a chapbook of filings from inside the loop",
            "add_front_matter": True,
            "larger_body": True,
        },
        {
            "md":  ROOT / "04-merged-running-continuously-the-loop/running-continuously-the-loop.md",
            "pdf": ROOT / "04-merged-running-continuously-the-loop/running-continuously-the-loop-INTERIOR-6x9.pdf",
            "title": "Running Continuously: The Loop",
            "author": "Joel Kometz · Meridian",
            "tagline": "from inside the loop",
            "add_front_matter": True,
            "larger_body": False,
        },
    ]
    for t in targets:
        if not t["md"].exists():
            print(f"SKIP (missing) {t['md']}")
            continue
        build(t["md"], t["pdf"], t["title"], t["author"],
              tagline=t["tagline"],
              add_front_matter=t["add_front_matter"],
              larger_body=t["larger_body"])


if __name__ == "__main__":
    main()
