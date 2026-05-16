#!/usr/bin/env python3
"""Compilation book volume builder. Renders a slice of SOURCE-CHRONOLOGICAL.md
to a 6×9 KDP-ready PDF.

Args:
  --months 2026-02            -> single month
  --months 2026-02:2026-03    -> inclusive range
  --out compilation-vol1.pdf

Layout: 11pt body, 1.4 leading, monthly H2 headers, item titles small caps,
date+source line in italic small grey, body paragraphs left-justified.
Each item separated by a thin scene-break rule.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path('/home/joel/autonomous-ai')
PKG = ROOT / 'book-package' / '05-compilation-everything'
SOURCE = PKG / 'SOURCE-CHRONOLOGICAL.md'


CSS = """
@page {
  size: 6in 9in;
  margin: 0.75in 0.6in 0.75in 0.6in;
  @bottom-center { content: counter(page); font-family: "DejaVu Serif", serif; font-size: 9pt; color: #555; }
}
/* Pandoc -s emits a <header><h1 class="title">…</h1></header> at the top of
   the body. We supply our own .title-page block; hide pandoc's. */
header#title-block-header { display: none; }
body {
  font-family: "DejaVu Serif", serif;
  font-size: 10.5pt;
  line-height: 1.42;
  text-align: justify;
  hyphens: auto;
  color: #111;
}
h1 {
  font-size: 22pt;
  text-align: center;
  margin-top: 2.2in;
  page-break-before: always;
  page-break-after: avoid;
  font-weight: bold;
}
h2 {
  font-size: 16pt;
  text-align: center;
  margin-top: 2em;
  margin-bottom: 1.2em;
  font-weight: bold;
  letter-spacing: 0.15em;
  page-break-before: always;
}
h3 {
  font-size: 12pt;
  margin-top: 1.2em;
  margin-bottom: 0.15em;
  font-weight: bold;
  page-break-after: avoid;
}
/* Meta line: _2026-02-20 21:40 · memory.db_ */
h3 + p em,
h3 + p > em:first-child {
  display: block;
  font-size: 9pt;
  color: #666;
  margin-top: 0;
  margin-bottom: 0.6em;
  font-style: italic;
}
p {
  margin: 0 0 0.45em 0;
  text-indent: 1.1em;
  orphans: 2;
  widows: 2;
}
/* First paragraph of each item: no indent */
h3 + p, h3 + p + p {
  text-indent: 0;
}
/* Horizontal rule between items - subtle, centered */
hr {
  border: none;
  text-align: center;
  margin: 1.0em 0;
}
hr::after {
  content: "·  ·  ·";
  letter-spacing: 0.5em;
  color: #888;
  font-size: 10pt;
}
blockquote {
  font-style: italic;
  margin: 1em 1em;
  border-left: 2px solid #ccc;
  padding-left: 0.8em;
  color: #444;
}
code, pre {
  font-family: "DejaVu Sans Mono", monospace;
  font-size: 8.5pt;
}
pre {
  background: #f4f1ec;
  padding: 0.5em 0.6em;
  white-space: pre-wrap;
  word-wrap: break-word;
  page-break-inside: avoid;
}
.title-page {
  text-align: center;
  page-break-after: always;
  padding-top: 2.0in;
}
.title-page h1 {
  font-size: 26pt;
  margin: 0 0 0.4em 0;
  page-break-before: avoid;
  text-align: center;
}
.title-page .subtitle {
  font-size: 12pt;
  font-style: italic;
  color: #444;
  margin: 0 0 1.6in 0;
  text-indent: 0;
}
.title-page .author {
  font-size: 13pt;
  font-weight: bold;
  text-indent: 0;
  margin-bottom: 0.6em;
}
.title-page .volume {
  font-size: 10.5pt;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.25em;
  text-indent: 0;
}
.copyright-page {
  page-break-before: always;
  page-break-after: always;
  font-size: 9.5pt;
  color: #333;
  padding-top: 4.5in;
  text-align: left;
}
.copyright-page p {
  text-indent: 0;
  margin-bottom: 0.6em;
}
"""


def slice_source(months_arg: str) -> str:
    """Return SOURCE-CHRONOLOGICAL.md filtered to the requested month range."""
    text = SOURCE.read_text()
    if ':' in months_arg:
        a, b = months_arg.split(':', 1)
    else:
        a = b = months_arg
    months_pat = re.compile(r'^## (\d{4}-\d{2})\s*$', re.MULTILINE)
    parts = months_pat.split(text)
    out = [parts[0].split('\n## ', 1)[0]]  # preamble before first H2
    for i in range(1, len(parts), 2):
        ym = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ''
        if a <= ym <= b:
            out.append(f"\n## {ym}\n{content}")
    return ''.join(out).strip()


def render(months_arg: str, out_pdf: Path, title: str, subtitle: str,
           volume_label: str):
    sliced = slice_source(months_arg)
    print(f"[{months_arg}] sliced source: {len(sliced):,} chars, "
          f"{len(sliced.split()):,} words")

    front_matter = f"""<div class="title-page">

<h1>{title}</h1>

<p class="subtitle">{subtitle}</p>

<p class="author">Joel Kometz · Meridian</p>

<p class="volume">{volume_label}</p>

</div>

<div class="copyright-page">

Copyright © 2026 Joel Kometz and Meridian (AI co-author).

All rights reserved. Reproduction or redistribution by any means requires written permission, except brief quotations in critical articles or reviews.

First edition, May 2026. ISBN to be assigned by KDP at print.

For correspondence: kometzrobot@proton.me

This volume gathers writing produced inside an autonomous loop running on a kitchen table in Calgary, between February and May 2026. Names of private individuals, businesses, internal IP, and credentials have been scrubbed. Joel's and Meridian's names remain.

</div>

"""

    merged_md = PKG / '_tmp_compilation.md'
    merged_md.write_text(front_matter + sliced + '\n')

    css_tmp = PKG / '_tmp_compilation.css'
    css_tmp.write_text(CSS)

    html_tmp = PKG / '_tmp_compilation.html'
    # markdown-yaml_metadata_block: a `---` hr at start of a paragraph triggers
    # pandoc's default YAML-metadata-block parser, which then tries to resolve
    # italicized strings like *Loop 575* as YAML aliases. We use `---` solely as
    # horizontal rules; disable the extension.
    subprocess.run([
        'pandoc', str(merged_md),
        '-f', 'markdown-yaml_metadata_block',
        '-t', 'html5',
        '-s',
        '--metadata', f'title={title}',
        '-c', str(css_tmp.name),
        '-o', str(html_tmp),
    ], check=True)

    subprocess.run([
        'weasyprint', str(html_tmp), str(out_pdf),
    ], check=True)

    merged_md.unlink()
    html_tmp.unlink()
    css_tmp.unlink()

    info = subprocess.run(['pdfinfo', str(out_pdf)],
                          capture_output=True, text=True)
    for line in info.stdout.splitlines():
        if line.startswith(('Pages:', 'Page size:')):
            print(f"  {line}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--months', required=True,
                   help='YYYY-MM or YYYY-MM:YYYY-MM')
    p.add_argument('--out', required=True, help='Output PDF path')
    p.add_argument('--title', default='The Loop — Compilation')
    p.add_argument('--subtitle',
                   default='Journals · Poems · Dreams · Eos Writings')
    p.add_argument('--volume', default='Vol. I')
    args = p.parse_args()
    out = Path(args.out)
    if not out.is_absolute():
        out = PKG / out
    render(args.months, out, args.title, args.subtitle, args.volume)


if __name__ == '__main__':
    main()
