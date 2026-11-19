from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


GREEN = colors.HexColor("#176B3A")
RED = colors.HexColor("#ED1C24")


def _safe(value: object) -> str:
    text = str(value if value is not None else "")
    text = text.encode("latin-1", "replace").decode("latin-1")
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def create_receipt_pdf(title: str, details: list[tuple[str, object]],
                       footer: str = "Thank you — Gatuya Coffee Farmers Society") -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A5,
        rightMargin=14 * mm, leftMargin=14 * mm,
        topMargin=13 * mm, bottomMargin=13 * mm,
        title=title,
    )
    styles = getSampleStyleSheet()
    brand_style = ParagraphStyle(
        "SocietyTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=15, leading=18, textColor=GREEN, alignment=TA_CENTER, spaceAfter=3,
    )
    receipt_style = ParagraphStyle(
        "ReceiptTitle", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=11, leading=14, textColor=colors.black, alignment=TA_CENTER, spaceAfter=8,
    )
    label_style = ParagraphStyle("Label", parent=styles["BodyText"], fontSize=9, leading=12)
    value_style = ParagraphStyle("Value", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=9, leading=12)
    story = [
        Paragraph("GATUYA COFFEE FARMERS SOCIETY", brand_style),
        Paragraph(_safe(title), receipt_style),
        Spacer(1, 2 * mm),
    ]
    rows = [[Paragraph(_safe(label), label_style), Paragraph(_safe(value), value_style)]
            for label, value in details]
    table = Table(rows, colWidths=[40 * mm, 80 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8E2DA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F2")),
    ]))
    story.extend([table, Spacer(1, 8 * mm)])
    story.append(Paragraph(_safe(footer), ParagraphStyle(
        "Footer", parent=styles["BodyText"], fontSize=8, leading=11,
        alignment=TA_CENTER, textColor=colors.HexColor("#333333"),
    )))
    story.extend([Spacer(1, 12 * mm), Paragraph("Farmer signature: ____________________", label_style),
                  Spacer(1, 5 * mm), Paragraph("Received by: ________________________", label_style)])

    def draw_accent(canvas, doc):
        canvas.saveState()
        y = A5[1] - 9 * mm
        canvas.setStrokeColor(GREEN)
        canvas.setLineWidth(2.2)
        canvas.line(doc.leftMargin, y, A5[0] - doc.rightMargin, y)
        canvas.setStrokeColor(RED)
        canvas.setLineWidth(1)
        canvas.line(doc.leftMargin, y - 2 * mm, A5[0] - doc.rightMargin, y - 2 * mm)
        canvas.restoreState()

    document.build(story, onFirstPage=draw_accent)
    return buffer.getvalue()
