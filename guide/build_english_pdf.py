"""Typeset the English M10/Muse tutorial as a print-friendly PDF."""

from __future__ import annotations

import html
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "English Preview.html"
OUTPUT = ROOT / "output" / "pdf" / "UNIHIKER-M10-Muse-Guide.pdf"

PAGE_W, PAGE_H = A4
MARGIN_X = 51
TOP = 54
BOTTOM = 50
CONTENT_W = PAGE_W - 2 * MARGIN_X

INK = colors.HexColor("#203029")
GREEN = colors.HexColor("#174D38")
MID_GREEN = colors.HexColor("#39795A")
MUTED = colors.HexColor("#69786F")
RULE = colors.HexColor("#C8D8CB")
PALE = colors.HexColor("#F0F5EF")
PAPER = colors.HexColor("#FCFCF9")

pdfmetrics.registerFont(TTFont("Segoe", "C:/Windows/Fonts/segoeui.ttf"))
pdfmetrics.registerFont(TTFont("Segoe-Bold", "C:/Windows/Fonts/segoeuib.ttf"))
pdfmetrics.registerFont(TTFont("Segoe-Italic", "C:/Windows/Fonts/segoeuii.ttf"))
pdfmetrics.registerFont(TTFont("Consolas", "C:/Windows/Fonts/consola.ttf"))
pdfmetrics.registerFontFamily(
    "Segoe", normal="Segoe", bold="Segoe-Bold", italic="Segoe-Italic", boldItalic="Segoe-Bold"
)

STYLES = {
    "kicker": ParagraphStyle(
        "Kicker", fontName="Segoe-Bold", fontSize=8.3, leading=11,
        textColor=MID_GREEN, spaceAfter=12, tracking=1.0,
    ),
    "title": ParagraphStyle(
        "Title", fontName="Segoe-Bold", fontSize=27.5, leading=33,
        textColor=GREEN, spaceAfter=13,
    ),
    "body": ParagraphStyle(
        "Body", fontName="Segoe", fontSize=10.2, leading=15.5,
        textColor=INK, spaceAfter=10,
        allowWidows=0, allowOrphans=0,
    ),
    "lead": ParagraphStyle(
        "Lead", fontName="Segoe", fontSize=11.4, leading=18,
        textColor=INK, spaceAfter=11,
        allowWidows=0, allowOrphans=0,
    ),
    "byline": ParagraphStyle(
        "Byline", fontName="Segoe-Bold", fontSize=10.5, leading=15,
        textColor=MID_GREEN, spaceAfter=12,
    ),
    "section": ParagraphStyle(
        "Section", fontName="Segoe-Bold", fontSize=17.2, leading=22,
        textColor=GREEN, spaceBefore=21, spaceAfter=11,
        keepWithNext=True,
    ),
    "caption": ParagraphStyle(
        "Caption", fontName="Segoe", fontSize=8.5, leading=12,
        textColor=MUTED, alignment=TA_CENTER, spaceAfter=15,
    ),
    "quote": ParagraphStyle(
        "Quote", fontName="Segoe", fontSize=9.8, leading=15.1,
        textColor=INK, alignment=TA_LEFT,
    ),
    "references": ParagraphStyle(
        "References", fontName="Segoe", fontSize=8.7, leading=14,
        textColor=MUTED, spaceBefore=12,
    ),
}

CAPTIONS = {
    "m10-live-story-2x2.jpg": "01  /  A real M10: dashboard, recording, waiting, and reply",
    "muse-sdk-token-steps-aligned.png": "02  /  Find or generate an SDK token",
    "sdk-token-terminal-handoff.png": "03  /  Paste the token into the M10 terminal shown on your computer (illustration)",
    "muse-app-pairing-en-2x2.png": "04  /  Pairing flow in the Muse app; one panel is illustrated",
    "dashboard-overview.png": "05  /  Four Dashboard pages",
    "work-overview.png": "06  /  Work Mode screen states, shown with preview data",
    "m10-muse-plant-guardian-concept.png": "07  /  A possible plant-care extension, shown as concept art",
}

MAX_IMAGE_HEIGHT = {
    "m10-live-story-2x2.jpg": 310,
    "muse-sdk-token-steps-aligned.png": 400,
    "sdk-token-terminal-handoff.png": 210,
    "muse-app-pairing-en-2x2.png": 455,
    "dashboard-overview.png": 382,
    "work-overview.png": 382,
    "m10-muse-plant-guardian-concept.png": 190,
}


def inline(node: Tag | NavigableString) -> str:
    if isinstance(node, NavigableString):
        return html.escape(str(node), quote=False)
    body = "".join(inline(child) for child in node.children)
    if node.name in {"strong", "b"}:
        return f"<b>{body}</b>"
    if node.name in {"em", "i"}:
        return f"<i>{body}</i>"
    if node.name == "code":
        return f'<font name="Consolas" size="9" color="#245A42">{body}</font>'
    if node.name == "a":
        href = html.escape(node.get("href", ""), quote=True)
        if href.startswith("https://"):
            return f'<link href="{href}" color="#24694D">{body}</link>'
        return f'<font color="#24694D">{body}</font>'
    if node.name == "br":
        return "<br/>"
    return body


def paragraph_markup(tag: Tag) -> str:
    return "".join(inline(child) for child in tag.children).strip()


def figure(src: str) -> list:
    path = (ROOT / src).resolve()
    with PILImage.open(path) as im:
        width, height = im.size
    name = path.name
    max_h = MAX_IMAGE_HEIGHT.get(name, 420)
    scale = min(CONTENT_W / width, max_h / height)
    image = Image(str(path), width=width * scale, height=height * scale, kind="proportional")
    image.hAlign = "CENTER"
    if name == "m10-muse-plant-guardian-concept.png":
        # The following italic paragraph already serves as its caption.
        return [Spacer(1, 7), image, Spacer(1, 8)]
    caption = Paragraph(CAPTIONS.get(name, path.stem), STYLES["caption"])
    return [Spacer(1, 9), image, Spacer(1, 7), caption]


def page_furniture(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN_X, PAGE_H - 38, PAGE_W - MARGIN_X, PAGE_H - 38)
    canvas.setFillColor(MID_GREEN)
    canvas.setFont("Segoe-Bold", 7.7)
    canvas.drawString(MARGIN_X, PAGE_H - 31, "UNIHIKER M10  /  MUSE")
    canvas.setFillColor(MUTED)
    canvas.setFont("Segoe", 7.7)
    canvas.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 31, "BUILD GUIDE")
    canvas.line(MARGIN_X, 38, PAGE_W - MARGIN_X, 38)
    canvas.drawString(MARGIN_X, 25, "GADGET SDK  /  DEBIAN 12")
    canvas.drawRightString(PAGE_W - MARGIN_X, 25, f"{doc.page:02d}")
    canvas.restoreState()


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    soup = BeautifulSoup(INPUT.read_text(encoding="utf-8"), "html.parser")
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=TOP, bottomMargin=BOTTOM,
        title="Make Your UNIHIKER M10 Talk to Muse",
        author="Chuan Lei",
        subject="Hands-on guide to pairing a UNIHIKER M10 with Muse",
        pageCompression=1,
    )
    story = [Paragraph("HANDS-ON PROJECT  /  LINUX DEVICE SDK", STYLES["kicker"])]
    intro_paragraphs = 0
    for element in soup.body.children:
        if not isinstance(element, Tag):
            continue
        if element.name == "h1":
            story.append(Paragraph(paragraph_markup(element), STYLES["title"]))
        elif element.name == "h2":
            story.append(CondPageBreak(90))
            story.append(Paragraph(paragraph_markup(element), STYLES["section"]))
        elif element.name == "p":
            if "byline" in element.get("class", []):
                story.append(Paragraph(paragraph_markup(element), STYLES["byline"]))
                story.append(HRFlowable(width="100%", thickness=1.4, color=MID_GREEN, spaceAfter=16))
                continue
            img = element.find("img")
            if img:
                story.append(KeepTogether(figure(img["src"])))
            else:
                markup = paragraph_markup(element)
                if not markup:
                    continue
                if markup.startswith("Four moments from the working build:"):
                    # The preceding figure already has a print caption;
                    # the click-to-zoom instruction only applies to HTML.
                    continue
                if markup.startswith("<i>Illustration: the terminal"):
                    # The preceding figure already supplies the print caption.
                    continue
                if markup.startswith("References:"):
                    story.append(HRFlowable(width="100%", thickness=0.7, color=RULE, spaceBefore=10, spaceAfter=5))
                    story.append(Paragraph(markup, STYLES["references"]))
                elif intro_paragraphs < 2:
                    story.append(Paragraph(markup, STYLES["lead"]))
                    intro_paragraphs += 1
                else:
                    story.append(Paragraph(markup, STYLES["body"]))
        elif element.name == "figure":
            img = element.find("img")
            if img:
                story.append(KeepTogether(figure(img["src"])))
        elif element.name == "blockquote":
            quote = " ".join(paragraph_markup(p) for p in element.find_all("p"))
            box = Table([[Paragraph(quote, STYLES["quote"])]], colWidths=[CONTENT_W])
            box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("LINEBEFORE", (0, 0), (0, -1), 3, MID_GREEN),
                ("LEFTPADDING", (0, 0), (-1, -1), 15),
                ("RIGHTPADDING", (0, 0), (-1, -1), 15),
                ("TOPPADDING", (0, 0), (-1, -1), 13),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 13),
            ]))
            story.extend([Spacer(1, 6), KeepTogether(box), Spacer(1, 14)])
    doc.build(story, onFirstPage=page_furniture, onLaterPages=page_furniture)
    print(OUTPUT)


if __name__ == "__main__":
    build()
