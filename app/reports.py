# app/reports.py
import io
import csv
from datetime import datetime
from typing import List, Dict, Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)


def generate_csv(data: List[Dict[str, Any]], headers: List[str] = None) -> str:
    """Return CSV as string"""
    if not data:
        return ""
    
    output = io.StringIO()
    headers = headers or list(data[0].keys())
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    for row in data:
        writer.writerow({k: row.get(k, "") for k in headers})
    return output.getvalue()


def generate_pdf_report(
    title: str,
    data: List[Dict[str, Any]],
    headers: List[str],
    column_widths: List[float] = None,
    summary: Dict[str, Any] = None,
) -> bytes:
    """Generate a PDF report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=30, leftMargin=30,
        topMargin=30, bottomMargin=30
    )
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'],
        fontSize=18, textColor=colors.HexColor("#1e40af"),
        spaceAfter=20
    )
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles['Normal']
    ))
    elements.append(Spacer(1, 12))
    
    # Summary
    if summary:
        summary_data = [[k, str(v)] for k, v in summary.items()]
        summary_table = Table(summary_data, colWidths=[2*inch, 3*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#e0e7ff")),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 20))
    
    # Data table
    if data:
        table_data = [headers]
        for row in data:
            table_data.append([str(row.get(h, "")) for h in headers])
        
        table = Table(table_data, colWidths=column_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.read()