"""Build the static site and downloadable copies from content/*.md.

Outputs (in docs/): index.html, one HTML page per letter, and downloads/
with .md, .docx (macOS textutil) and .pdf (headless Chrome) for each letter
plus a combined file of all letters.
"""
import html
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "content"
OUT = ROOT / "docs"
DL = OUT / "downloads"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

TITLE = "Draft letters on the South Brunswick data center air permit"
AS_OF = "October 29, 2026"
BANNER = (
    "DRAFT for discussion. These letters were drafted by a community member for the "
    "Princeton Board of Education to consider. They have not been adopted, approved or "
    "sent by the Board and do not represent its position. Facts as of " + AS_OF + "."
)

CSS = """
:root { --ink:#1b1f24; --muted:#57606a; --rule:#d0d7de; --bg:#ffffff; --accent:#0b5cad; --warn:#fff4d6; --warnline:#d4a72c; }
@media (prefers-color-scheme: dark) { :root { --ink:#e6edf3; --muted:#9da7b1; --rule:#30363d; --bg:#0d1117; --accent:#58a6ff; --warn:#2d2410; --warnline:#9e7a1c; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:17px/1.6 Georgia, "Times New Roman", serif; }
main { max-width: 760px; margin: 0 auto; padding: 24px 16px 64px; }
a { color: var(--accent); }
.banner { background:var(--warn); border-left:4px solid var(--warnline); padding:10px 14px; font:14px/1.45 -apple-system, "Segoe UI", sans-serif; margin-bottom:20px; }
nav { font:14px -apple-system, "Segoe UI", sans-serif; margin-bottom:16px; }
.dl { font:14px -apple-system, "Segoe UI", sans-serif; display:flex; flex-wrap:wrap; gap:6px 14px; margin:4px 0 20px; color:var(--muted); }
h1 { font:700 28px/1.2 -apple-system, "Segoe UI", sans-serif; margin:0 0 6px; }
h2 { font:700 20px/1.3 -apple-system, "Segoe UI", sans-serif; margin:28px 0 8px; }
ol, ul { padding-left: 1.4em; }
li { margin: 4px 0; }
ul.check { list-style: none; padding-left: 0; }
ul.check li::before { content: "\\2610\\00a0"; }
table { border-collapse: collapse; width: 100%; font:15px/1.4 -apple-system, "Segoe UI", sans-serif; }
th, td { text-align:left; border-bottom:1px solid var(--rule); padding:8px 6px; vertical-align:top; }
.muted { color: var(--muted); }
@media print { .banner, nav, .dl { display:none; } body { font-size: 12pt; } main { padding: 0; } }
"""


def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"(?<![\"'>=])(https?://[^\s<]+[^\s<.,;)])", r'<a href="\1">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", text)
    return text


def md_to_html(md):
    """Small converter for the subset of Markdown used in content/."""
    title, parts = None, []
    for block in re.split(r"\n\s*\n", md.strip()):
        lines = block.split("\n")
        if lines[0].startswith("# "):
            title = lines[0][2:].strip()
            continue
        if lines[0].startswith("## "):
            parts.append(f"<h2>{inline(lines[0][3:])}</h2>")
            continue
        if all(re.match(r"\d+\. ", l) for l in lines):
            items = "".join(f"<li>{inline(re.sub(r'^\d+\. ', '', l))}</li>" for l in lines)
            parts.append(f"<ol>{items}</ol>")
            continue
        if all(l.startswith("- [ ] ") for l in lines):
            items = "".join(f"<li>{inline(l[6:])}</li>" for l in lines)
            parts.append(f'<ul class="check">{items}</ul>')
            continue
        if all(l.startswith("- ") for l in lines):
            items = "".join(f"<li>{inline(l[2:])}</li>" for l in lines)
            parts.append(f"<ul>{items}</ul>")
            continue
        parts.append("<p>" + "<br>\n".join(inline(l) for l in lines) + "</p>")
    return title, "\n".join(parts)


def page(title, body, *, nav=True, downloads=None, banner=True):
    head = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style></head><body><main>'
    top = f'<div class="banner">{BANNER}</div>' if banner else ""
    if nav:
        top += '<nav><a href="index.html">&larr; All letters</a></nav>'
    dl = ""
    if downloads:
        dl = '<div class="dl">Download: ' + " ".join(
            f'<a href="downloads/{f}">{label}</a>' for label, f in downloads) + "</div>"
    return f"{head}{top}<h1>{html.escape(title)}</h1>{dl}{body}</main></body></html>"


def export_page(title, body):
    """Plain page used for Word and PDF output: draft notice as a line of text, no navigation."""
    note = f"<p><em>{BANNER}</em></p>"
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            '<style>body{font:12pt/1.5 Georgia,serif;margin:0;padding:0} h1{font:bold 16pt Georgia,serif} '
            'h2{font:bold 13pt Georgia,serif;page-break-before:always} h2.first{page-break-before:auto} '
            'ul.check{list-style:none;padding-left:0}</style></head><body>'
            f"{note}<h1>{html.escape(title)}</h1>{body}</body></html>")


def to_docx(src_html, dest):
    subprocess.run(["textutil", "-convert", "docx", "-output", str(dest), str(src_html)], check=True)


def to_pdf(src_html, dest):
    profile = ROOT / ".build" / "chrome-profile"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                    "--no-default-browser-check", f"--user-data-dir={profile}",
                    "--no-pdf-header-footer", f"--print-to-pdf={dest}", src_html.resolve().as_uri()],
                   check=True, capture_output=True, timeout=90)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    DL.mkdir(parents=True)
    tmp = ROOT / ".build"
    tmp.mkdir(exist_ok=True)
    (OUT / ".nojekyll").write_text("")

    entries, combined_html, combined_md = [], [], []
    for i, src in enumerate(sorted(SRC.glob("*.md"))):
        md = src.read_text()
        title, body = md_to_html(md)
        stem = src.stem
        downloads = [("Word (.docx)", f"{stem}.docx"), ("PDF", f"{stem}.pdf"), ("Markdown", f"{stem}.md")]
        (OUT / f"{stem}.html").write_text(page(title, body, downloads=downloads))
        (DL / f"{stem}.md").write_text(f"*{BANNER}*\n\n{md}")
        ex = tmp / f"{stem}.html"
        ex.write_text(export_page(title, body))
        to_docx(ex, DL / f"{stem}.docx")
        to_pdf(ex, DL / f"{stem}.pdf")
        entries.append((stem, title, downloads))
        cls = ' class="first"' if i == 0 else ""
        combined_html.append(f"<h2{cls}>{html.escape(title)}</h2>{body}")
        combined_md.append(md.replace("# ", "## ", 1))

    ex = tmp / "all-letters.html"
    ex.write_text(export_page(TITLE, "\n".join(combined_html)))
    to_docx(ex, DL / "all-letters.docx")
    to_pdf(ex, DL / "all-letters.pdf")
    (DL / "all-letters.md").write_text(f"# {TITLE}\n\n*{BANNER}*\n\n" + "\n\n".join(combined_md))

    rows = "".join(
        f'<tr><td><a href="{stem}.html">{html.escape(title)}</a></td><td>'
        + " · ".join(f'<a href="downloads/{f}">{label.split(" ")[0]}</a>' for label, f in dl)
        + "</td></tr>" for stem, title, dl in entries)
    intro = (
        "<p>Five draft letters on NJDEP draft air permit PCP250001 for twelve diesel backup "
        "generators at the data center at 4405 Route 1, South Brunswick. "
        "<strong>Public comments on the permit are due November 9, 2026.</strong></p>"
        f"<table><tr><th>Letter</th><th>Download</th></tr>{rows}</table>"
        '<h2>All letters in one file</h2><div class="dl">'
        '<a href="downloads/all-letters.docx">Word (.docx)</a> '
        '<a href="downloads/all-letters.pdf">PDF</a> '
        '<a href="downloads/all-letters.md">Markdown</a></div>'
        '<p class="muted">Word files open in Microsoft Word, Pages and Google Docs '
        "(File &rarr; Open, or upload to Google Drive).</p>")
    (OUT / "index.html").write_text(page(TITLE, intro, nav=False))
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
