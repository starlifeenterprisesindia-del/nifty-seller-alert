"""App-native PDF report generator for Nifty Seller AI V50.8.7."""
from __future__ import annotations

from io import BytesIO
from html import escape
from typing import Any, Iterable, Mapping

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)


def _text(value: Any) -> str:
    if value is None:
        return "-"
    return escape(str(value).replace("₹", "INR ").replace("—", "-").replace("–", "-"))


def _rows(value: Any) -> list[dict]:
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _table(data: list[dict], max_rows: int = 40) -> Table | Paragraph:
    if not data:
        return Paragraph("No data available.", getSampleStyleSheet()["BodyText"])
    columns = list(data[0].keys())
    body_style = ParagraphStyle(
        "TableCell", fontName="Helvetica", fontSize=5.8, leading=7.0,
        wordWrap="CJK", spaceAfter=0, spaceBefore=0,
    )
    head_style = ParagraphStyle(
        "TableHead", parent=body_style, fontName="Helvetica-Bold",
        fontSize=5.7, leading=6.8,
    )
    matrix = [[Paragraph(_text(col), head_style) for col in columns]]
    for row in data[:max_rows]:
        matrix.append([Paragraph(_text(row.get(col, "-")), body_style) for col in columns])
    width = 265 * mm
    col_width = width / max(1, len(columns))
    table = Table(matrix, repeatRows=1, colWidths=[col_width] * len(columns), splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9CA3AF")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return table


def _page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(285 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_ai_report_pdf(report: Mapping[str, Any]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=12 * mm,
        title="Nifty Seller AI Live Report",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCenter", parent=styles["Title"], alignment=TA_CENTER, fontSize=17, leading=20))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=11, leading=13, spaceBefore=7, spaceAfter=4))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))

    story = [
        Paragraph("Nifty Seller AI - Live Market Report", styles["TitleCenter"]),
        Paragraph(_text(report.get("generated_at", "")), styles["Small"]),
        Spacer(1, 4 * mm),
    ]

    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    summary_rows = [{"Field": key, "Value": value} for key, value in summary.items()]
    story += [Paragraph("Executive Summary", styles["Section"]), _table(summary_rows, max_rows=60)]

    for title, key in (
        ("Source and Readiness Status", "source_rows"),
        ("Market Path Forecast — 15m Primary / 30m Confirmation", "market_path_rows"),
        ("Signal Reliability", "evidence_rows"),
        ("Strategy Matrix", "strategy_rows"),
        ("Candidate Matrix", "candidate_rows"),
        ("Option Chain Analysis", "option_rows"),
        ("DSP Branch Evidence Integrity", "branch_integrity_rows"),
        ("Department Status", "department_rows"),
    ):
        rows = _rows(report.get(key, []))
        if not rows:
            continue
        story += [Spacer(1, 3 * mm), Paragraph(title, styles["Section"]), _table(rows)]
        if key == "market_path_rows":
            summary_text = _text(report.get("market_path_summary", ""))
            authority_text = _text(report.get("market_path_authority_note", ""))
            if summary_text and summary_text != "-":
                story.append(Spacer(1, 1.5 * mm))
                story.append(Paragraph(f"<b>Likely Path:</b> {summary_text}", styles["Small"]))
            if authority_text and authority_text != "-":
                story.append(Paragraph(f"<b>One-Brain Authority Lock:</b> {authority_text}", styles["Small"]))
        if key in {"option_rows", "department_rows"}:
            story.append(PageBreak())

    reasons = report.get("reasons", []) if isinstance(report.get("reasons"), list) else []
    warnings = report.get("warnings", []) if isinstance(report.get("warnings"), list) else []
    story += [Paragraph("AI Reasons", styles["Section"])]
    story.append(Paragraph("<br/>".join(f"- {_text(item)}" for item in reasons) or "- None", styles["Small"]))
    story += [Paragraph("Warnings / Blockers", styles["Section"])]
    story.append(Paragraph("<br/>".join(f"- {_text(item)}" for item in warnings) or "- None", styles["Small"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Decision-support only. Verify broker data, chart confirmation, spreads, margin and hedge before any trade.", styles["Small"]))

    doc.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
    return buffer.getvalue()
