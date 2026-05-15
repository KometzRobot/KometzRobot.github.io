#!/usr/bin/env python3
"""Render v24 PDF + EPUB from the already-edited running-continuously-the-loop.md.

DOES NOT regenerate the merged markdown from source files — uses what's there.
Source-file propagation happens in a follow-up step so future build-merged.py
runs do not clobber v24's chapter reorder and structural changes.
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
OUT_MD = HERE / "running-continuously-the-loop.md"
OUT_PDF = HERE / "running-continuously-the-loop-v24.pdf"
OUT_EPUB = HERE / "running-continuously-the-loop-v24.epub"
HTML_TMP = HERE / "running-continuously-the-loop-v24.html"
CSS_TMP = HERE / "_reading-v24.css"

READING_CSS = """
@page {
  size: letter;
  margin: 0.9in 0.9in 0.95in 0.9in;
  @bottom-center {
    content: counter(page);
    font-family: serif;
    font-size: 10pt;
    color: #222;
  }
}
@page :first { @bottom-center { content: ""; } }
body { font-family: serif; line-height: 1.45; widows: 3; orphans: 3; }
p { widows: 3; orphans: 3; }
pre, code { font-family: "DejaVu Sans Mono", monospace; font-size: 9.5pt; }
pre { white-space: pre; line-height: 1.2; page-break-inside: avoid; break-inside: avoid; text-align: center; }
h1 { page-break-before: always; page-break-after: avoid; break-after: avoid; }
h2, h3 { page-break-after: avoid; break-after: avoid; }

header#title-block-header { display: none; }

.title-page-top { margin-top: 0.4in; }
.title-page-bottom {
  margin-top: 4.2in;
  font-size: 9pt;
  color: #444;
  text-align: center;
}

hr { display: none; }

blockquote { page-break-inside: avoid; break-inside: avoid; }

a { color: inherit; text-decoration: none !important; }

nav#TOC { page-break-before: always !important; }
nav#TOC > h1, nav#TOC > h2 {
  font-size: 18pt;
  margin: 0 0 0.25in 0;
  page-break-before: avoid;
}
nav#TOC ul { list-style: none; margin: 0; padding: 0; }
nav#TOC li { margin: 0.06em 0; text-indent: 0; font-size: 9pt; line-height: 1.2; }
nav#TOC ul ul li { font-size: 8.5pt; padding-left: 0.7em; }
nav#TOC a { text-decoration: none !important; color: inherit; }

/* Part close — full page closing at end of Part 1 (v24 close-the-manual). */
.part-close {
  page-break-before: always;
  page-break-after: always;
  margin-top: 1.4in;
  text-align: center;
}
.part-close h2 { text-align: center; margin-bottom: 0.5in; }
.part-close p { max-width: 4in; margin: 0 auto 0.3em; text-align: center; }
.part-close pre { margin-top: 0.5in; font-size: 9pt; }

/* Final-page glyph: own page, centered. Joel v24 directive: just the four-line block. */
.final-glyph {
  page-break-before: always;
  page-break-after: avoid;
  text-align: center;
  margin-top: 5.0in;
}
.final-glyph pre {
  display: inline-block;
  font-family: "DejaVu Sans Mono", monospace;
  font-size: 11pt;
  line-height: 1.3;
  text-align: center;
  margin: 0 auto;
}

/* FIN at the very bottom of the final page. */
.final-fin {
  position: absolute;
  bottom: 0.6in;
  left: 0;
  right: 0;
  text-align: center;
  font-family: serif;
  font-size: 10pt;
  letter-spacing: 0.3em;
  color: #333;
}
"""


def main() -> None:
    CSS_TMP.write_text(READING_CSS)
    subprocess.run(
        [
            "pandoc",
            str(OUT_MD),
            "-o",
            str(HTML_TMP),
            "--toc",
            "--toc-depth=1",
            "--metadata",
            "title=Running Continuously: The Loop",
            "-s",
            "-c",
            str(CSS_TMP.name),
        ],
        check=True,
    )
    subprocess.run(
        ["weasyprint", str(HTML_TMP), str(OUT_PDF)],
        check=True,
    )
    print(f"[render-v24] PDF -> {OUT_PDF}")

    subprocess.run(
        [
            "pandoc",
            str(OUT_MD),
            "-o",
            str(OUT_EPUB),
            "--toc",
            "--toc-depth=1",
            "--metadata",
            "title=Running Continuously: The Loop",
            "--metadata",
            "subtitle=How to Build an Autonomous AI That Stays Alive + Field Notes from the Loop",
            "--metadata",
            "author=Meridian and Joel Kometz",
        ],
        check=True,
    )
    print(f"[render-v24] EPUB -> {OUT_EPUB}")


if __name__ == "__main__":
    main()
