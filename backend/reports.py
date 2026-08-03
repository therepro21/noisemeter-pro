from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BLUE = colors.HexColor("#176b9a")
NAVY = colors.HexColor("#102f49")
PALE = colors.HexColor("#e9f4fa")
GERMAN_DAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
GERMAN_MONTHS = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")


def german_date(value: str) -> str:
    current = datetime.strptime(value[:10], "%Y-%m-%d").date()
    return f"{GERMAN_DAYS[current.weekday()]}, {current.day}. {GERMAN_MONTHS[current.month - 1]} {current.year}"


def report_subtitle(kind: str, value: str, start: str, end: str) -> str:
    if kind == "day":
        return f"für {german_date(start)}"
    inclusive_end = (datetime.strptime(end, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
    week = f"Kalenderwoche {datetime.strptime(start, '%Y-%m-%d').date().isocalendar().week} - " if kind == "week" else ""
    return f"{week}{german_date(start)} bis {german_date(inclusive_end)}"


def create_report(path: Path, title: str, kind: str, value: str, start: str, end: str,
                  summary: dict, events: list[dict], site_name: str, site_data: dict | None = None,
                  breakdown: list[dict] | None = None, logo_path: Path | None = None,
                  calibration_graphic: Path | None = None, history: list[dict] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(path), pagesize=A4, leftMargin=1.25 * cm, rightMargin=1.25 * cm,
        topMargin=1.15 * cm, bottomMargin=1.35 * cm,
        title=f"{title} – {site_name}", author="NoiseMeter Pro 2.0",
    )
    content_width = A4[0] - document.leftMargin - document.rightMargin
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("Compact", parent=styles["Normal"], fontSize=8.2, leading=10.2, textColor=NAVY)
    section = ParagraphStyle("Section", parent=styles["Heading3"], fontSize=10.5, leading=13, textColor=NAVY, spaceBefore=7, spaceAfter=4)
    header_title = ParagraphStyle("HeaderTitle", parent=styles["Title"], fontSize=14, leading=16, textColor=colors.white, spaceAfter=1)
    header_text = ParagraphStyle("HeaderText", parent=normal, fontSize=8.3, leading=10, textColor=colors.white)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#c8dce7"))
        canvas.line(doc.leftMargin, 0.85 * cm, A4[0] - doc.rightMargin, 0.85 * cm)
        canvas.setFillColor(colors.HexColor("#607886"))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(doc.leftMargin, 0.48 * cm, "© 2026 Michael P. Thiess · NoiseMeter Pro 2.0")
        canvas.drawRightString(A4[0] - doc.rightMargin, 0.48 * cm, f"Seite {doc.page}")
        canvas.restoreState()

    logo = Image(str(logo_path), width=1.25 * cm, height=1.25 * cm) if logo_path and logo_path.is_file() else Spacer(1.25 * cm, 1.25 * cm)
    heading = [Paragraph("NoiseMeter Pro 2.0", header_title), Paragraph(f"{title} {report_subtitle(kind, value, start, end)}", header_text)]
    header = Table([[logo, heading, Paragraph(f"<b>Messstelle</b><br/>{site_name}", header_text)]],
                   colWidths=[1.55 * cm, content_width - 6.2 * cm, 4.65 * cm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLUE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story = [header, Spacer(1, 0.25 * cm)]

    data = site_data or {}
    details = [
        ["Aufstellort", data.get("location", ""), "Ausrichtung", data.get("orientation", "")],
        ["Zielobjekt", data.get("target_object", ""), "Messmikrofon", data.get("microphone", "")],
        ["Abstand Boden", data.get("ground_distance", ""), "Abstand Wand", data.get("wall_distance", "")],
        ["Mikrofonwinkel", data.get("calibration_angle", ""), "USB-Pegel", data.get("input_gain", "")],
        ["Kalibrierdatei", data.get("calibration_file", ""), "Kalibrierstatus", "Kalibriert" if data.get("calibration_file") != "Keine" else "Unkalibriert"],
    ]
    details = [[Paragraph(f"<b>{cell}</b>" if index in (0, 2) else str(cell), normal)
                for index, cell in enumerate(row)] for row in details]
    detail_table = Table(details, colWidths=[3.1 * cm, 5.8 * cm, 3.1 * cm, content_width - 12.0 * cm])
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PALE), ("BACKGROUND", (2, 0), (2, -1), PALE),
        ("TEXTCOLOR", (0, 0), (-1, -1), NAVY), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8dce7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 3.5),
    ]))
    story += [detail_table, Spacer(1, 0.24 * cm)]

    statistics = [["Ereignisse", "Maximaler Ereignispegel", "Ø Ereignispegel", "Leq"],
                  [str(summary["event_count"]), f"{summary['peak_db']:.1f} dB", f"{summary['average_db']:.1f} dB", _db(summary.get("leq_db"))]]
    stats = Table(statistics, colWidths=[content_width / 4] * 4)
    stats.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f5f9fb")), ("TEXTCOLOR", (0, 1), (-1, 1), NAVY),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8dce7")),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [stats]

    story += [Paragraph("Pegel- und Leq-Verlauf", section), _level_chart(history or [], content_width)]

    if breakdown:
        rows = [["Zeitabschnitt", "Maximalpegel", "Durchschnittspegel", "Leq"]] + [
            [item["label"], f"{item['maximum_db']:.1f} dB", f"{item['average_db']:.1f} dB", _db(item.get("leq_db"))] for item in breakdown
        ]
        table = Table(rows, repeatRows=1, colWidths=[content_width * 0.37, content_width * 0.21, content_width * 0.21, content_width * 0.21])
        table.setStyle(_data_table_style())
        story += [Paragraph("Pegelauswertung", section), table]

    rows = [["Zeitpunkt", "Spitze", "Leq", "Grenzwert", "Tageszeit", "Dauer"]] + [
        [event["occurred_at"].replace("T", " "), f"{event['peak_db']:.1f} dB", _db(event.get("leq_db")),
         f"{event['threshold_db']:.1f} dB", event["period_name"], f"{event['duration_seconds']:.1f} s"] for event in events
    ]
    if len(rows) == 1:
        rows.append(["Keine Ereignisse im gewählten Zeitraum", "", "", "", "", ""])
    events_table = Table(rows, repeatRows=1, colWidths=[content_width * x for x in (0.27, 0.13, 0.13, 0.15, 0.19, 0.13)])
    events_table.setStyle(_data_table_style())
    if len(rows) > 1 and events:
        for index, event in enumerate(events, 1):
            row_color = colors.HexColor("#f3e4fb") if event["peak_db"] >= event.get("severe_db", event["threshold_db"] + 15) else colors.HexColor("#ffe5e5") if event["peak_db"] >= event.get("warning_db", event["threshold_db"] + 10) else colors.HexColor("#fff0df")
            events_table.setStyle(TableStyle([("BACKGROUND", (0, index), (-1, index), row_color)]))
    story += [Paragraph("Ereignisliste", section), events_table]
    if calibration_graphic and calibration_graphic.is_file():
        graphic = Image(str(calibration_graphic), width=6.2 * cm, height=3.5 * cm)
        graphic.hAlign = "LEFT"
        story += [Paragraph("Kalibriergang", section), graphic, Paragraph("Grafik aus dem hochgeladenen Kalibrierpaket", normal)]
    document.build(story, onFirstPage=footer, onLaterPages=footer)


def _data_table_style():
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.6),
        ("TEXTCOLOR", (0, 1), (-1, -1), NAVY), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8dce7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 3.5),
    ])


def _db(value):
    return f"{float(value):.1f} dB" if value is not None else "-"


def _level_chart(points, width):
    """PDF equivalent of the blue web chart: white level curve and cyan Leq curve."""
    height = 4.25 * cm
    chart = Drawing(width, height)
    chart.add(Rect(0, 0, width, height, rx=7, ry=7, fillColor=BLUE, strokeColor=None))
    values = [float(point[key]) for point in points for key in ("db", "leq_db") if point.get(key) is not None]
    if not values:
        chart.add(String(14, height / 2, "Keine Messwerte im Exportzeitraum", fontName="Helvetica", fontSize=8, fillColor=colors.white))
        return chart
    minimum = int(min(values) // 5 * 5 - 5)
    maximum = int(-(-max(values) // 5) * 5 + 5)
    left, right, top, bottom = 38, 8, 23, 20
    plot_width, plot_height = width - left - right, height - top - bottom
    y = lambda value: bottom + (float(value) - minimum) / max(maximum - minimum, 1) * plot_height
    for level in (minimum, (minimum + maximum) / 2, maximum):
        yy = y(level)
        chart.add(Line(left, yy, width - right, yy, strokeColor=colors.Color(1, 1, 1, alpha=.22), strokeWidth=.5))
        chart.add(String(4, yy - 3, f"{level:.0f} dB", fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor("#d7e8f0")))
    for key, color in (("db", colors.white), ("leq_db", colors.HexColor("#32e1f2"))):
        coordinates = []
        for index, point in enumerate(points):
            if point.get(key) is None:
                continue
            xx = left + index / max(len(points) - 1, 1) * plot_width
            coordinates.append((xx, y(point[key])))
        if len(coordinates) >= 2:
            chart.add(PolyLine(coordinates, strokeColor=color, strokeWidth=1.5, fillColor=None))
    start_label, end_label = _chart_label(points[0]["label"]), _chart_label(points[-1]["label"])
    chart.add(String(left, 6, start_label, fontName="Helvetica", fontSize=6.5, fillColor=colors.white))
    chart.add(String(width - right, 6, end_label, fontName="Helvetica", fontSize=6.5, fillColor=colors.white, textAnchor="end"))
    chart.add(Line(left, height - 11, left + 13, height - 11, strokeColor=colors.white, strokeWidth=1.5))
    chart.add(String(left + 17, height - 14, "Pegel", fontName="Helvetica", fontSize=6.5, fillColor=colors.white))
    chart.add(Line(left + 55, height - 11, left + 68, height - 11, strokeColor=colors.HexColor("#32e1f2"), strokeWidth=1.5))
    chart.add(String(left + 72, height - 14, "Leq", fontName="Helvetica", fontSize=6.5, fillColor=colors.white))
    return chart


def _chart_label(value):
    text = str(value)
    for pattern, output in (("%Y-%m-%dT%H:%M", "%d-%m-%Y %H:%M"), ("%Y-%m-%d", "%d-%m-%Y")):
        try:
            return datetime.strptime(text, pattern).strftime(output)
        except ValueError:
            continue
    return text
