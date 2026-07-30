from __future__ import annotations

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def create_report(path: Path, title: str, start: str, end: str, summary: dict, events: list[dict], site_name: str, site_data: dict | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=1.6*cm, rightMargin=1.6*cm, topMargin=1.5*cm)
    styles["Title"].textColor = colors.HexColor("#17324d")
    story = [Paragraph("NoiseMeter Pro", styles["Title"]), Paragraph(f"Messstelle: {site_name}", styles["Heading2"]), Paragraph(title, styles["Heading2"]),
             Paragraph(f"Zeitraum: {start} bis {end}", styles["Normal"]), Spacer(1, 0.5*cm)]
    data = site_data or {}
    details = [["Aufstellort", data.get("location", "")], ["Ausrichtung", data.get("orientation", "")], ["Zielobjekt", data.get("target_object", "")], ["Abstand Boden/Wand", f"{data.get('ground_distance','')} / {data.get('wall_distance','')}"], ["Mikrofon", data.get("microphone", "")]]
    story += [Table(details, colWidths=[4*cm, 12*cm], style=[("BACKGROUND",(0,0),(0,-1),colors.HexColor("#e8f1f5")),("GRID",(0,0),(-1,-1),.25,colors.lightgrey),("PADDING",(0,0),(-1,-1),4)]), Spacer(1,.4*cm)]
    statistics = [["Ereignisse", "Maximalpegel", "Durchschnitt Ereignisse"],
                  [str(summary["event_count"]), f"{summary['peak_db']:.1f} dB", f"{summary['average_db']:.1f} dB"]]
    table = Table(statistics, colWidths=[5.5*cm]*3)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#17324d")), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                               ("GRID", (0,0), (-1,-1), .25, colors.grey), ("ALIGN", (0,0), (-1,-1), "CENTER"), ("PADDING", (0,0), (-1,-1), 7)]))
    story += [table, Spacer(1, 0.6*cm), Paragraph("Ereignisliste", styles["Heading3"])]
    rows = [["Zeitpunkt", "Pegel", "Grenzwert", "Bereich", "Dauer"]]
    rows += [[e["occurred_at"].replace("T", " "), f"{e['peak_db']:.1f} dB", f"{e['threshold_db']:.1f} dB", e["period_name"], f"{e['duration_seconds']:.1f} s"] for e in events]
    events_table = Table(rows, repeatRows=1, colWidths=[4.4*cm, 2.4*cm, 2.5*cm, 3.5*cm, 2.3*cm])
    events_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2a6f97")), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), .25, colors.lightgrey), ("FONT", (0,0), (-1,0), "Helvetica-Bold"), ("PADDING", (0,0), (-1,-1), 5)]))
    for index, event in enumerate(events, 1):
        color = colors.HexColor("#f3e4fb") if event["peak_db"] >= event.get("severe_db", event["threshold_db"] + 15) else colors.HexColor("#ffe5e5") if event["peak_db"] >= event.get("warning_db", event["threshold_db"] + 10) else colors.HexColor("#fff0df")
        events_table.setStyle(TableStyle([("BACKGROUND", (0,index), (-1,index), color)]))
    story.append(events_table)
    story += [Spacer(1, .5*cm), Paragraph("Copyright by Michael P. Thiess", styles["Normal"])]
    document.build(story)
