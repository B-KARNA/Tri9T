"""
generate_pdf.py  —  Convert APPROACH.md to Approach_Document.pdf using ReportLab.
Produces: cover page, table of contents, page numbers, code blocks, diagrams (as text).
"""

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

# ─── Colour Palette ──────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#0A1628")
BLUE   = colors.HexColor("#1A3A6B")
ACCENT = colors.HexColor("#2563EB")
MUTED  = colors.HexColor("#64748B")
CODE_BG = colors.HexColor("#1E1E2E")
CODE_FG = colors.HexColor("#CDD6F4")
BORDER  = colors.HexColor("#CBD5E1")
LIGHT   = colors.HexColor("#F8FAFC")
WHITE   = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 2.0 * cm


# ─── Numbered-doc template (adds running header + page number) ────────────────
class NumberedDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self.toc = TableOfContents()
        self.toc.levelStyles = [
            ParagraphStyle(
                "TOC1",
                fontName="Helvetica-Bold",
                fontSize=11,
                textColor=BLUE,
                leftIndent=0,
                spaceAfter=4,
            ),
            ParagraphStyle(
                "TOC2",
                fontName="Helvetica",
                fontSize=10,
                textColor=NAVY,
                leftIndent=1 * cm,
                spaceAfter=2,
            ),
        ]

    def afterFlowable(self, flowable):
        """Register headings in the TOC."""
        if isinstance(flowable, Paragraph):
            style = flowable.style.name
            text  = flowable.getPlainText()
            if style == "Heading1":
                self.notify("TOCEntry", (0, text, self.page))
            elif style == "Heading2":
                self.notify("TOCEntry", (1, text, self.page))


def cover_page(canvas, doc):
    canvas.saveState()
    # Full dark background
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Accent bar
    canvas.setFillColor(ACCENT)
    canvas.rect(0, PAGE_H * 0.42, PAGE_W, 4, fill=1, stroke=0)

    # College name (top)
    canvas.setFont("Helvetica", 11)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 2.8 * cm, "CMR Institute of Technology")

    # Main title
    canvas.setFont("Helvetica-Bold", 28)
    canvas.setFillColor(WHITE)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H * 0.62, "Engineering Approach")
    canvas.setFont("Helvetica-Bold", 22)
    canvas.setFillColor(colors.HexColor("#60A5FA"))
    canvas.drawCentredString(PAGE_W / 2, PAGE_H * 0.55, "Document")

    # Subtitle
    canvas.setFont("Helvetica", 13)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawCentredString(PAGE_W / 2, PAGE_H * 0.48,
        "Tri9T AI Engineering Internship Assignment")

    # Author block
    canvas.setFillColor(colors.HexColor("#1E293B"))
    canvas.roundRect(MARGIN, PAGE_H * 0.22, PAGE_W - 2 * MARGIN, 3.5 * cm,
                     8, fill=1, stroke=0)

    canvas.setFont("Helvetica-Bold", 14)
    canvas.setFillColor(WHITE)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H * 0.22 + 2.6 * cm, "B Karna")

    canvas.setFont("Helvetica", 11)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawCentredString(PAGE_W / 2, PAGE_H * 0.22 + 1.9 * cm,
        "BE Computer Science and Engineering")
    canvas.drawCentredString(PAGE_W / 2, PAGE_H * 0.22 + 1.3 * cm,
        "CMR Institute of Technology")

    # Status + Date
    canvas.setFont("Helvetica-Bold", 10)
    canvas.setFillColor(ACCENT)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H * 0.22 + 0.5 * cm,
        "Status: Final Submission  |  July 2026")

    canvas.restoreState()


def body_page(canvas, doc):
    canvas.saveState()
    # Top rule
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, PAGE_H - MARGIN * 0.7,
                PAGE_W - MARGIN, PAGE_H - MARGIN * 0.7)

    # Running header
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, PAGE_H - MARGIN * 0.5,
                      "Tri9T — Engineering Approach Document")
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN * 0.5,
                           "Balaraj M P  |  CMR Institute of Technology")

    # Bottom rule + page number
    canvas.line(MARGIN, MARGIN * 0.7,
                PAGE_W - MARGIN, MARGIN * 0.7)
    canvas.drawCentredString(PAGE_W / 2, MARGIN * 0.4,
                             f"Page {doc.page}")
    canvas.restoreState()


# ─── Style Sheet ──────────────────────────────────────────────────────────────
def build_styles():
    from reportlab.lib.styles import StyleSheet1

    ss = StyleSheet1()

    def S(name, **kw):
        ss.add(ParagraphStyle(name=name, **kw))

    S("Normal",    fontName="Helvetica", fontSize=10, textColor=NAVY, leading=14)
    S("Heading1",  fontName="Helvetica-Bold", fontSize=16, textColor=BLUE,
       spaceBefore=20, spaceAfter=8, leading=22)
    S("Heading2",  fontName="Helvetica-Bold", fontSize=13, textColor=NAVY,
       spaceBefore=14, spaceAfter=6, leading=18)
    S("Heading3",  fontName="Helvetica-Bold", fontSize=11, textColor=MUTED,
       spaceBefore=10, spaceAfter=4, leading=15)
    S("BodyText2", fontName="Helvetica", fontSize=10, textColor=NAVY,
       spaceAfter=5, leading=15, alignment=TA_LEFT)
    S("BulletItem", fontName="Helvetica", fontSize=10, textColor=NAVY,
       leftIndent=14, spaceAfter=3, leading=14, bulletIndent=4)
    S("CodeBlock", fontName="Courier", fontSize=8.5, textColor=CODE_FG,
       backColor=CODE_BG, leftIndent=8, rightIndent=8,
       spaceAfter=8, leading=13, borderPadding=6)
    S("Caption",   fontName="Helvetica-Oblique", fontSize=9, textColor=MUTED,
       alignment=TA_CENTER, spaceAfter=8)
    S("TOCTitle",  fontName="Helvetica-Bold", fontSize=14, textColor=BLUE,
       spaceBefore=14, spaceAfter=6)

    return ss


# ─── Markdown-to-ReportLab parser ────────────────────────────────────────────
def md_to_story(md_text: str, styles) -> list:
    story = []
    lines = md_text.splitlines()
    i = 0
    in_code = False
    code_buf = []

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
                code_buf = []
            else:
                in_code = False
                code_text = "\n".join(code_buf)
                tbl = Table(
                    [[Paragraph(code_text.replace("\n", "<br/>"),
                                styles["CodeBlock"])]],
                    colWidths=[PAGE_W - 2 * MARGIN - 0.4 * cm],
                )
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                    ("BOX",        (0, 0), (-1, -1), 0.5,
                     colors.HexColor("#313244")),
                    ("PADDING",    (0, 0), (-1, -1), 8),
                ]))
                story.append(Spacer(1, 0.2 * cm))
                story.append(tbl)
                story.append(Spacer(1, 0.2 * cm))
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # Mermaid block — render as a captioned code box
        if line.strip() == "```mermaid":
            mermaid_buf = []
            i += 1
            while i < len(lines) and lines[i].strip() != "```":
                mermaid_buf.append(lines[i])
                i += 1
            i += 1
            diagram_text = "\n".join(mermaid_buf)
            tbl = Table(
                [[Paragraph(diagram_text.replace("\n", "<br/>"),
                            styles["CodeBlock"])]],
                colWidths=[PAGE_W - 2 * MARGIN - 0.4 * cm],
            )
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                ("BOX",        (0, 0), (-1, -1), 0.5,
                 colors.HexColor("#313244")),
                ("PADDING",    (0, 0), (-1, -1), 8),
            ]))
            story.append(tbl)
            story.append(Paragraph(
                "Figure: Architecture Flow Diagram (Mermaid DSL)", styles["Caption"]
            ))
            continue

        # Horizontal rule
        if re.match(r"^-{3,}$", line.strip()):
            story.append(Spacer(1, 0.2 * cm))
            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
            story.append(Spacer(1, 0.2 * cm))
            i += 1
            continue

        # Skip cover meta lines
        if re.match(r"\*\*(Prepared by|Status|Date|Project Name|Document)\*\*", line):
            i += 1
            continue

        # Heading detection
        heading_m = re.match(r"^(#{1,4})\s+(.*)", line)
        if heading_m:
            level    = len(heading_m.group(1))
            text     = clean_inline(heading_m.group(2))
            style_map = {1: "Heading1", 2: "Heading1", 3: "Heading2", 4: "Heading3"}
            story.append(Paragraph(text, styles[style_map.get(level, "Heading2")]))
            i += 1
            continue

        # Bullet list
        bullet_m = re.match(r"^(\s*)[-*]\s+(.*)", line)
        if bullet_m:
            text          = clean_inline(bullet_m.group(2))
            indent_level  = len(bullet_m.group(1)) // 2
            p_style = ParagraphStyle(
                f"Bullet{indent_level}x",
                parent=styles["BulletItem"],
                leftIndent=14 + indent_level * 14,
            )
            story.append(Paragraph(f"• {text}", p_style))
            i += 1
            continue

        # Numbered list
        num_m = re.match(r"^(\d+)\.\s+(.*)", line)
        if num_m:
            num  = num_m.group(1)
            text = clean_inline(num_m.group(2))
            story.append(Paragraph(f"{num}. {text}", styles["BulletItem"]))
            i += 1
            continue

        # Blockquote
        if line.startswith(">"):
            text = clean_inline(line.lstrip("> ").strip())
            tbl = Table(
                [[Paragraph(text, styles["BodyText2"])]],
                colWidths=[PAGE_W - 2 * MARGIN - 1.2 * cm],
            )
            tbl.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, -1), LIGHT),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("LINEBEFORE",  (0, 0), (0, -1),  3, ACCENT),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 0.2 * cm))
            i += 1
            continue

        # Empty line
        if not line.strip():
            story.append(Spacer(1, 0.15 * cm))
            i += 1
            continue

        # Plain body text
        text = clean_inline(line)
        if text:
            story.append(Paragraph(text, styles["BodyText2"]))
        i += 1

    return story


def clean_inline(text: str) -> str:
    text = re.sub(r"\*\*\*(.*?)\*\*\*", r"<b><i>\1</i></b>", text)
    text = re.sub(r"\*\*(.*?)\*\*",     r"<b>\1</b>",         text)
    text = re.sub(r"\*(.*?)\*",          r"<i>\1</i>",         text)
    text = re.sub(r"`([^`]+)`",
                  r'<font name="Courier" color="#6366F1">\1</font>', text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"^#+\s*", "",  text)
    return text


# ─── Build PDF ───────────────────────────────────────────────────────────────
def build_pdf(md_path: Path, out_path: Path) -> None:
    styles = build_styles()
    md_text = md_path.read_text(encoding="utf-8")

    # ── Document template ──
    doc = NumberedDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN * 1.6,
        bottomMargin=MARGIN * 1.4,
    )

    # Two page templates: cover (no header/footer) and body
    cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id="cover")
    body_frame  = Frame(
        MARGIN, MARGIN * 1.2,
        PAGE_W - 2 * MARGIN, PAGE_H - MARGIN * 2.6,
        id="body",
    )
    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=cover_frame,
                     onPage=cover_page),
        PageTemplate(id="Body",  frames=body_frame,
                     onPage=body_page),
    ])

    # ── Story ──
    story = []

    # Cover page — blank flowable, real content drawn in onPage callback
    story.append(NextPageTemplate("Body"))
    story.append(PageBreak())

    # ── Table of Contents ──
    toc = doc.toc
    story.append(Paragraph("Table of Contents", styles["Heading1"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(toc)
    story.append(PageBreak())

    # ── Body content ──
    # Strip the manual cover-page block at the top of the markdown
    body_md = re.sub(
        r"^.*?^---\s*\n## Cover Page.*?^---\s*\n## Table of Contents.*?^---\s*\n",
        "",
        md_text,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )
    # Fallback: just skip the first --- block
    if body_md.strip() == md_text.strip():
        body_md = md_text

    story.extend(md_to_story(body_md, styles))

    doc.multiBuild(story)
    print(f"[OK] PDF written -> {out_path}")


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = Path(__file__).parent
    build_pdf(
        md_path=root / "APPROACH.md",
        out_path=root / "Approach_Document.pdf",
    )
