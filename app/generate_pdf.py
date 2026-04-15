"""
generate_pdf.py — Convert audit report markdown to a branded PDF using WeasyPrint.
"""

import re
from datetime import datetime
from pathlib import Path

import markdown_it


LOGO_PATH = Path(__file__).parent / "static" / "cavela-logo.jpg"


# ---------------------------------------------------------------------------
# CSS for the PDF
# ---------------------------------------------------------------------------

PDF_CSS = """
@page {
    size: A4;
    margin: 35mm 22mm 22mm 20mm;

    @top-right {
        content: element(logo-header);
        padding-top: 8mm;
        vertical-align: top;
    }

    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-size: 9pt;
        color: #999;
    }
}

/* Logo in top-right margin box */
#logo-header {
    position: running(logo-header);
    text-align: right;
}

#logo-header img {
    height: 76px;
    width: auto;
}

/* Base typography */
body {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: #1a1a1a;
    margin: 0;
    padding: 0;
}

/* Cover / title area */
.report-title {
    margin-bottom: 6mm;
    padding-bottom: 4mm;
    border-bottom: 2px solid #1a1aff;
}

.report-title h1 {
    font-size: 22pt;
    font-weight: 700;
    margin: 0 0 2mm 0;
    color: #1a1a1a;
}

.report-title .meta {
    font-size: 9pt;
    color: #666;
    margin: 0;
}

/* Headings */
h1 {
    font-size: 18pt;
    font-weight: 700;
    color: #1a1a1a;
    margin: 8mm 0 3mm 0;
    page-break-after: avoid;
}

h2 {
    font-size: 13pt;
    font-weight: 700;
    color: #1a1a1a;
    margin: 6mm 0 2mm 0;
    padding-bottom: 1mm;
    border-bottom: 1px solid #e0e0e0;
    page-break-after: avoid;
}

h3 {
    font-size: 11pt;
    font-weight: 600;
    color: #1a1a1a;
    margin: 5mm 0 2mm 0;
    page-break-after: avoid;
}

h4 {
    font-size: 10.5pt;
    font-weight: 600;
    color: #333;
    margin: 4mm 0 1mm 0;
    page-break-after: avoid;
}

/* Paragraphs */
p {
    margin: 0 0 3mm 0;
}

/* Lists */
ul, ol {
    margin: 0 0 3mm 0;
    padding-left: 6mm;
}

li {
    margin-bottom: 1mm;
}

/* Blockquotes (customer quotes) */
blockquote {
    margin: 3mm 0 3mm 4mm;
    padding: 3mm 4mm;
    border-left: 3px solid #1a1aff;
    background: #f5f5ff;
    color: #333;
    font-style: italic;
    font-size: 10pt;
}

blockquote p {
    margin: 0;
}

/* Inline code */
code {
    font-family: 'Courier New', monospace;
    font-size: 9pt;
    background: #f0f0f0;
    padding: 0 2px;
    border-radius: 2px;
}

/* Section dividers */
hr {
    border: none;
    border-top: 1px solid #e0e0e0;
    margin: 5mm 0;
}

/* Strong (bold) */
strong {
    font-weight: 700;
    color: #111;
}

/* Footer strip */
.footer-strip {
    margin-top: 10mm;
    padding-top: 3mm;
    border-top: 1px solid #e0e0e0;
    font-size: 8.5pt;
    color: #999;
    text-align: center;
}
"""


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def render_markdown(md_text: str) -> str:
    """Convert markdown to HTML using markdown-it-py."""
    md = markdown_it.MarkdownIt()
    return md.render(md_text)


def extract_title_and_meta(md_text: str) -> tuple[str, str]:
    """Extract the H1 title and generate meta line."""
    title = "Product Feedback Report"
    meta = f"Prepared by Cavela \u00b7 {datetime.now().strftime('%B %d, %Y')}"

    lines = md_text.strip().splitlines()
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    return title, meta


# ---------------------------------------------------------------------------
# HTML assembly
# ---------------------------------------------------------------------------

def build_html(md_text: str) -> str:
    title, meta = extract_title_and_meta(md_text)

    # Remove the H1 line from body since we render it in the title block
    body_md = re.sub(r'^#\s+.+\n', '', md_text.strip(), count=1)
    # Remove *Prepared by* meta line if present
    body_md = re.sub(r'^\*Prepared by.+\*\n?', '', body_md.strip(), count=1)
    body_html = render_markdown(body_md)

    logo_src = LOGO_PATH.resolve().as_uri() if LOGO_PATH.exists() else ""

    logo_block = ""
    if logo_src:
        logo_block = f"""
<!-- Running logo element for page header -->
<div id="logo-header">
  <img src="{logo_src}" alt="Cavela">
</div>
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
{PDF_CSS}
</style>
</head>
<body>

{logo_block}

<!-- Report title block -->
<div class="report-title">
  <h1>{title}</h1>
  <p class="meta">{meta}</p>
</div>

{body_html}

</body>
</html>"""

    return html
