#!/usr/bin/env python3
"""Build the current DosePilot technical report with ReportLab.

The source is deliberately plain Markdown so every judge-facing claim remains
diffable. The renderer supports only the small Markdown subset used by the
report and fails on malformed tables rather than silently dropping content.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


INK = colors.HexColor("#12212E")
MUTED = colors.HexColor("#566573")
TEAL = colors.HexColor("#0E8A83")
NAVY = colors.HexColor("#123B5D")
PALE = colors.HexColor("#EAF5F3")
PALE_BLUE = colors.HexColor("#EAF1F7")
LINE = colors.HexColor("#CAD6DE")
WHITE = colors.white

# Stable object identifiers and timestamps make the checked-in PDF byte-for-byte
# reproducible from the checked-in source and renderer in the same environment.
rl_config.invariant = True


def register_fonts() -> tuple[str, str, str]:
    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ),
        (
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
        ),
    ]
    for regular, bold, mono in candidates:
        if all(Path(p).exists() for p in (regular, bold, mono)):
            pdfmetrics.registerFont(TTFont("DoseSans", regular))
            pdfmetrics.registerFont(TTFont("DoseSansBold", bold))
            pdfmetrics.registerFont(TTFont("DoseMono", mono))
            return "DoseSans", "DoseSansBold", "DoseMono"
    return "Helvetica", "Helvetica-Bold", "Courier"


FONT, FONT_BOLD, FONT_MONO = register_fonts()


def inline_markup(text: str) -> str:
    value = html.escape(text.strip())
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"`(.+?)`", r"<font name=\"DoseMono\">\1</font>", value)
    value = re.sub(
        r"(https?://[^\s<]+)",
        lambda match: f'<link href="{match.group(1)}" color="#0E6A70">{match.group(1)}</link>',
        value,
    )
    return value


def make_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName=FONT_BOLD,
            fontSize=32,
            leading=36,
            textColor=INK,
            spaceAfter=8 * mm,
            alignment=TA_LEFT,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Heading2"],
            fontName=FONT,
            fontSize=17,
            leading=22,
            textColor=TEAL,
            spaceAfter=8 * mm,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName=FONT_BOLD,
            fontSize=21,
            leading=25,
            textColor=NAVY,
            spaceBefore=1 * mm,
            spaceAfter=5 * mm,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=12.5,
            leading=16,
            textColor=TEAL,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=8.8,
            leading=12.4,
            textColor=INK,
            spaceAfter=2.6 * mm,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=7.2,
            leading=9.4,
            textColor=MUTED,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=8.6,
            leading=11.7,
            textColor=INK,
            leftIndent=5 * mm,
            firstLineIndent=-3.2 * mm,
            bulletIndent=1 * mm,
            spaceAfter=1.4 * mm,
        ),
        "quote": ParagraphStyle(
            "Quote",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=10.2,
            leading=14.5,
            textColor=NAVY,
            leftIndent=5 * mm,
            rightIndent=5 * mm,
            spaceAfter=5 * mm,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontName=FONT_MONO,
            fontSize=7.2,
            leading=10,
            textColor=INK,
            backColor=colors.HexColor("#F3F6F8"),
            borderColor=LINE,
            borderWidth=0.5,
            borderPadding=5,
            spaceBefore=1 * mm,
            spaceAfter=3 * mm,
        ),
        "covermeta": ParagraphStyle(
            "CoverMeta",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=13,
            textColor=MUTED,
            spaceAfter=4 * mm,
        ),
    }


STYLES = make_styles()


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(
            filename,
            pagesize=A4,
            rightMargin=16 * mm,
            leftMargin=16 * mm,
            topMargin=18 * mm,
            bottomMargin=17 * mm,
            title="von DosePilot - Current Technical Report",
            author="Joseph Ayanda",
            subject="Measurement-aware drug-screen reconstruction",
        )
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="main")
        self.addPageTemplates(PageTemplate(id="content", frames=frame, onPage=self._decorate))

    def _decorate(self, canvas, doc):
        page = canvas.getPageNumber()
        canvas.saveState()
        if page > 1:
            canvas.setStrokeColor(LINE)
            canvas.setLineWidth(0.4)
            canvas.line(16 * mm, A4[1] - 12 * mm, A4[0] - 16 * mm, A4[1] - 12 * mm)
            canvas.setFont(FONT_BOLD, 7)
            canvas.setFillColor(NAVY)
            canvas.drawString(16 * mm, A4[1] - 9 * mm, "VON DOSEPILOT")
            canvas.setFont(FONT, 7)
            canvas.setFillColor(MUTED)
            canvas.drawRightString(A4[0] - 16 * mm, A4[1] - 9 * mm, "Current public technical report")
        canvas.setStrokeColor(LINE)
        canvas.line(16 * mm, 12 * mm, A4[0] - 16 * mm, 12 * mm)
        canvas.setFont(FONT, 6.8)
        canvas.setFillColor(MUTED)
        canvas.drawString(16 * mm, 8 * mm, "Repeated adaptive development - not clinical guidance")
        canvas.drawRightString(A4[0] - 16 * mm, 8 * mm, f"Page {page}")
        canvas.restoreState()


def table_flow(rows: list[list[str]], available_width: float) -> Table:
    if not rows or len(rows) < 2:
        raise ValueError("Markdown table must include a header and at least one row")
    columns = len(rows[0])
    if any(len(row) != columns for row in rows):
        raise ValueError("Markdown table has inconsistent column counts")
    parsed = [[Paragraph(inline_markup(cell), STYLES["small"]) for cell in row] for row in rows]
    if columns == 2:
        widths = [available_width * 0.66, available_width * 0.34]
    elif columns == 3:
        widths = [available_width * 0.48, available_width * 0.22, available_width * 0.30]
    elif columns == 4:
        widths = [available_width * 0.36, available_width * 0.19, available_width * 0.19, available_width * 0.26]
    elif columns == 5:
        widths = [available_width * 0.30] + [available_width * 0.175] * 4
    else:
        widths = [available_width / columns] * columns
    table = Table(parsed, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
            + [("BACKGROUND", (0, row), (-1, row), colors.HexColor("#F4F8FA")) for row in range(2, len(rows), 2)]
        )
    )
    table.spaceAfter = 3 * mm
    return table


def parse_markdown(source: str, width: float):
    lines = source.splitlines()
    story = []
    paragraph = []
    code = []
    in_code = False
    title_seen = False
    cover_mode = True

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            story.append(Paragraph(inline_markup(" ".join(p.strip() for p in paragraph)), STYLES["body"]))
            paragraph = []

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            if in_code:
                story.append(Paragraph("<br/>".join(html.escape(x) for x in code), STYLES["code"]))
                code = []
                in_code = False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code.append(line)
            index += 1
            continue
        if stripped == "<!-- pagebreak -->":
            flush_paragraph()
            story.append(PageBreak())
            cover_mode = False
            index += 1
            continue
        if not stripped:
            flush_paragraph()
            index += 1
            continue
        if stripped.startswith("|"):
            flush_paragraph()
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [c.strip() for c in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                index += 1
            story.append(table_flow(rows, width))
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            text = stripped[2:]
            if not title_seen:
                story.append(Spacer(1, 18 * mm))
                story.append(Paragraph(inline_markup(text), STYLES["title"]))
                story.append(HRFlowable(width="32%", thickness=3, color=TEAL, hAlign="LEFT", spaceAfter=7 * mm))
                title_seen = True
            else:
                story.append(Paragraph(inline_markup(text), STYLES["h1"]))
            index += 1
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            style = STYLES["subtitle"] if cover_mode else STYLES["h2"]
            story.append(Paragraph(inline_markup(stripped[3:]), style))
            index += 1
            continue
        if stripped.startswith("> "):
            flush_paragraph()
            box = Table(
                [[Paragraph(inline_markup(stripped[2:]), STYLES["quote"]) ]],
                colWidths=[width],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), PALE),
                        ("BOX", (0, 0), (-1, -1), 0.8, TEAL),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                ),
            )
            box.spaceAfter = 5 * mm
            story.append(box)
            index += 1
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            story.append(Paragraph(inline_markup(stripped[2:]), STYLES["bullet"], bulletText="•"))
            index += 1
            continue
        if re.match(r"^\d+\. ", stripped):
            flush_paragraph()
            number, item = stripped.split(". ", 1)
            story.append(Paragraph(inline_markup(item), STYLES["bullet"], bulletText=f"{number}."))
            index += 1
            continue
        if cover_mode and ("Joseph Ayanda" in stripped or stripped.startswith("Repository:") or stripped.startswith("Live fictional")):
            flush_paragraph()
            story.append(Paragraph(inline_markup(stripped), STYLES["covermeta"]))
            index += 1
            continue
        paragraph.append(stripped)
        index += 1
    flush_paragraph()
    return story


def build(source_path: Path, output_path: Path):
    source = source_path.read_text(encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = ReportDoc(str(output_path))
    story = parse_markdown(source, doc.width)
    doc.build(story)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("docs/DosePilot_Technical_Report_Current.md"))
    parser.add_argument("--output", type=Path, default=Path("docs/DosePilot_Technical_Report_Current.pdf"))
    args = parser.parse_args()
    build(args.source, args.output)


if __name__ == "__main__":
    main()
