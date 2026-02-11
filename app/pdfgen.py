# app/pdfgen.py
from __future__ import annotations

from pathlib import Path
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _wrap_text(c: canvas.Canvas, text: str, x: float, y: float, max_width: float, leading: float) -> float:
    """
    Draw a paragraph with crude word-wrapping. Returns new y.
    """
    words = text.split()
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        if c.stringWidth(test, c._fontname, c._fontsize) <= max_width:
            line = test
        else:
            c.drawString(x, y, line)
            y -= leading
            line = w
            if y < 20 * mm:
                c.showPage()
                y = A4[1] - 20 * mm
                c.setFont("Helvetica", 11)
    if line:
        c.drawString(x, y, line)
        y -= leading
    return y


def markdown_to_pdf(md_text: str, pdf_path: Path, title: str | None = None) -> None:
    """
    Minimal Markdown -> PDF renderer supporting:
    - # / ## headings
    - bullet lines starting with "- "
    - normal paragraphs
    """
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(pdf_path), pagesize=A4)

    width, height = A4
    x = 20 * mm
    y = height - 20 * mm
    max_width = width - 40 * mm

    def new_page():
        nonlocal y
        c.showPage()
        y = height - 20 * mm

    # Optional title
    if title:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(x, y, title)
        y -= 10 * mm
        c.setFont("Helvetica", 11)

    lines: List[str] = md_text.splitlines()

    for raw in lines:
        line = raw.rstrip()

        if not line.strip():
            y -= 4 * mm
            if y < 20 * mm:
                new_page()
            continue

        # Headings
        if line.startswith("# "):
            c.setFont("Helvetica-Bold", 16)
            y = _wrap_text(c, line[2:].strip(), x, y, max_width, leading=18)
            c.setFont("Helvetica", 11)
            y -= 2 * mm
        elif line.startswith("## "):
            c.setFont("Helvetica-Bold", 13)
            y = _wrap_text(c, line[3:].strip(), x, y, max_width, leading=15)
            c.setFont("Helvetica", 11)
            y -= 1 * mm
        # Bullets
        elif line.startswith("- "):
            bullet = "• " + line[2:].strip()
            y = _wrap_text(c, bullet, x, y, max_width, leading=13)
        else:
            y = _wrap_text(c, line.strip(), x, y, max_width, leading=13)

        if y < 20 * mm:
            new_page()
            c.setFont("Helvetica", 11)

    c.save()
