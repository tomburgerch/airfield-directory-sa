#!/usr/bin/env python3
"""
Generate a compact PDF airfield directory from AIRFIELD_DIRECTORY.md.
Designed as a lightweight offline backup for phones — no diagrams, multiple
airfields per page, essential info only.
"""

import os

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable,
)

from parse_markdown import parse_airfields
from shared import MD_FILE, BASE_DIR, get_icao

OUTPUT_PDF = os.path.join(BASE_DIR, 'Airfield_Directory_A5.pdf')

# ── Page dimensions ──
A5_WIDTH, A5_HEIGHT = A5
MARGIN = 8 * mm
CONTENT_WIDTH = A5_WIDTH - 2 * MARGIN

# ── Colors ──
NAVY = HexColor('#1a365d')
BLUE = HexColor('#2b6cb0')
RED = HexColor('#c53030')
GRAY = HexColor('#4a5568')
LIGHT_GRAY = HexColor('#f7fafc')
BORDER = HexColor('#e2e8f0')
DARK_RED = HexColor('#9b2c2c')
DARK_GRAY = HexColor('#2d3748')

# ── Emoji cleanup ──
EMOJI_MAP = {
    '⬅️': '[L]', '➡️': '[R]',
    '🌙': '', '🚫': '', '🔒': '', '✈️': '', '🪖': '', '⛽': '',
    '❓': '(?)', '📅': '', '⚠️': '[!]', '⛔': '[X]',
    '🏠': '', '🛩️': '', '🔴': '', '🟢': '', '🟡': '',
}


def clean(text):
    for emoji, rep in EMOJI_MAP.items():
        text = text.replace(emoji, rep)
    return text.strip()


def get_styles():
    styles = getSampleStyleSheet()
    defs = {
        'AFName': dict(fontSize=9, leading=11, textColor=white, fontName='Helvetica-Bold'),
        'AFCode': dict(fontSize=7, leading=9, textColor=HexColor('#bee3f8'), fontName='Helvetica',
                       alignment=TA_RIGHT),
        'AFLabel': dict(fontSize=6.5, leading=8, textColor=GRAY, fontName='Helvetica-Bold'),
        'AFValue': dict(fontSize=6.5, leading=8, fontName='Helvetica'),
        'AFFreq': dict(fontSize=7, leading=8.5, textColor=BLUE, fontName='Helvetica-Bold'),
        'AFRwyHead': dict(fontSize=6, leading=7, textColor=white, fontName='Helvetica-Bold',
                          alignment=TA_CENTER),
        'AFRwyCell': dict(fontSize=6, leading=7, fontName='Helvetica', alignment=TA_CENTER),
        'AFWarning': dict(fontSize=6, leading=7.5, textColor=RED, fontName='Helvetica-Bold'),
        'AFNote': dict(fontSize=5.5, leading=7, textColor=GRAY, fontName='Helvetica'),
        'AFGroup': dict(fontSize=8, leading=10, textColor=NAVY, fontName='Helvetica-Bold',
                        alignment=TA_CENTER, spaceBefore=4, spaceAfter=2),
    }
    for name, kwargs in defs.items():
        styles.add(ParagraphStyle(name, parent=styles['Normal'], **kwargs))
    return styles


def draw_footer(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont('Helvetica', 5)
    canvas_obj.setFillColor(HexColor('#a0aec0'))
    canvas_obj.drawCentredString(A5_WIDTH / 2, 4 * mm, f"SA Airfield Directory — p.{doc.page}")
    canvas_obj.restoreState()


def build_airfield_block(airfield, styles):
    """Build a compact block for one airfield (no page break)."""
    elements = []
    f = airfield['fields']

    is_closed = '[X]' in clean(airfield['name']) or 'CLOSED' in airfield['name'].upper()
    is_military = 'MILITARY' in f.get('Access', '').upper()

    # ── Header row ──
    name = clean(airfield['name'])
    if len(name) > 50:
        name = name[:47] + '...'
    code = clean(get_icao(airfield))

    bg = DARK_RED if is_closed else (DARK_GRAY if is_military else NAVY)
    header = Table(
        [[Paragraph(f"<b>{name}</b>", styles['AFName']),
          Paragraph(code, styles['AFCode'])]],
        colWidths=[CONTENT_WIDTH * 0.75, CONTENT_WIDTH * 0.25],
    )
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (0, 0), 4),
        ('RIGHTPADDING', (-1, -1), (-1, -1), 4),
    ]))
    elements.append(header)

    if is_closed:
        elements.append(Paragraph(
            "<b>CLOSED — DO NOT PLAN OPERATIONS</b>",
            ParagraphStyle('Closed', parent=styles['AFWarning'], alignment=TA_CENTER, fontSize=7)))
        return KeepTogether(elements)

    # ── Key info (compact 2-col grid) ──
    coords = clean(f.get('Coordinates', ''))
    elev = clean(f.get('Elevation', ''))
    freq = clean(f.get('Frequencies', f.get('Frequency', '')))
    joining = clean(f.get('Joining Alt', ''))
    circuit = clean(f.get('Circuit Alt', f.get('Circuit', f.get('Pattern Alt', ''))))
    night = clean(f.get('Night Ops', ''))
    fuel = clean(f.get('Fuel', ''))
    hours = clean(f.get('Hours', ''))
    access = clean(f.get('Access', ''))

    rows = []
    for label, val in [('Coords', coords), ('Elev', elev), ('Freq', freq),
                        ('Join', joining), ('Circuit', circuit), ('Access', access),
                        ('Fuel', fuel), ('Night', night), ('Hours', hours)]:
        if val:
            val_display = val[:70] if len(val) > 70 else val
            if label == 'Freq':
                val_para = Paragraph(f"<b>{val_display}</b>", styles['AFFreq'])
            else:
                val_para = Paragraph(val_display, styles['AFValue'])
            rows.append([Paragraph(f"<b>{label}</b>", styles['AFLabel']), val_para])

    if rows:
        info = Table(rows, colWidths=[CONTENT_WIDTH * 0.14, CONTENT_WIDTH * 0.86])
        info.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 0.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
            ('LEFTPADDING', (0, 0), (0, -1), 2),
            ('LEFTPADDING', (1, 0), (1, -1), 3),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [white, LIGHT_GRAY]),
        ]))
        elements.append(info)

    # ── Frequencies table (only if multi-freq) ──
    if airfield['frequencies_table']:
        freq_rows = []
        for row in airfield['frequencies_table'][:6]:
            freq_rows.append([
                Paragraph(clean(row[0]), styles['AFValue']),
                Paragraph(f"<b>{clean(row[1])}</b>", styles['AFFreq']),
            ])
        if freq_rows:
            ft = Table(freq_rows, colWidths=[CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.5])
            ft.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 0.3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0.3),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('LINEBELOW', (0, 0), (-1, -1), 0.15, BORDER),
            ]))
            elements.append(ft)

    # ── Runways (compact) ──
    if airfield['runways']:
        max_cols = max(len(r) for r in airfield['runways'])
        if max_cols >= 5:
            heads = ['RWY', 'Len', 'Wid', 'Sfc', 'Cct']
            widths = [0.12, 0.22, 0.16, 0.28, 0.22]
        else:
            heads = ['RWY', 'Surface']
            widths = [0.3, 0.7]
        heads = heads[:max_cols]
        widths = [CONTENT_WIDTH * w for w in widths[:max_cols]]

        rwy_data = [[Paragraph(h, styles['AFRwyHead']) for h in heads]]
        for row in airfield['runways']:
            cells = [clean(c) for c in row]
            while len(cells) < max_cols:
                cells.append('')
            rwy_data.append([Paragraph(c[:18], styles['AFRwyCell']) for c in cells[:max_cols]])

        rt = Table(rwy_data, colWidths=widths)
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('GRID', (0, 0), (-1, -1), 0.2, BORDER),
        ]))
        elements.append(rt)

    # ── Warnings (max 2) ──
    for w in airfield['warnings'][:2]:
        elements.append(Paragraph(f"[!] {clean(w)[:120]}", styles['AFWarning']))

    # ── Key notes (max 3, short) ──
    for note in airfield['notes'][:3]:
        elements.append(Paragraph(f"- {clean(note)[:120]}", styles['AFNote']))

    # ── Contact ──
    if airfield['contact']:
        elements.append(Paragraph(
            f"<b>Contact:</b> {clean(airfield['contact'])[:100]}", styles['AFNote']))

    elements.append(Spacer(1, 3 * mm))
    return KeepTogether(elements)


def build_cover(styles, count):
    elements = []
    elements.append(Spacer(1, 20 * mm))

    title = ParagraphStyle('T', parent=styles['Normal'], fontSize=18, leading=22,
                           textColor=NAVY, fontName='Helvetica-Bold', alignment=TA_CENTER)
    sub = ParagraphStyle('S', parent=styles['Normal'], fontSize=9, leading=12,
                         textColor=GRAY, fontName='Helvetica', alignment=TA_CENTER)
    disc = ParagraphStyle('D', parent=styles['Normal'], fontSize=6.5, leading=8.5,
                          textColor=white, fontName='Helvetica', alignment=TA_CENTER)

    elements.append(Paragraph("Wagyu Wings", title))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph("SA Airfield Directory", sub))
    elements.append(Paragraph(f"<b>{count} Airfields</b> — Offline Backup", sub))
    elements.append(Spacer(1, 12 * mm))

    # Disclaimer box
    disc_rows = [
        [Paragraph("<b>DISCLAIMER</b>", ParagraphStyle('DT', parent=disc, fontSize=8,
                   fontName='Helvetica-Bold'))],
        [Paragraph(
            "Supplementary reference only. Does <b>NOT replace</b> SACAA AIP, NOTAMs, or "
            "official charts. Verify all data before flight. Use at own risk.", disc)],
    ]
    dt = Table(disc_rows, colWidths=[CONTENT_WIDTH * 0.85])
    dt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), RED),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (0, 0), 4),
        ('BOTTOMPADDING', (0, -1), (0, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROUNDEDCORNERS', [3, 3, 3, 3]),
    ]))
    elements.append(dt)

    elements.append(Spacer(1, 8 * mm))
    info = ParagraphStyle('I', parent=styles['Normal'], fontSize=6, leading=8,
                          textColor=HexColor('#718096'), fontName='Helvetica', alignment=TA_CENTER)
    elements.append(Paragraph("Updated: 2026-03-11", info))
    elements.append(Paragraph("Sources: SACAA AIP, OpenAIP, AvCom forums", info))
    elements.append(PageBreak())
    return elements


def generate_pdf(airfields, output_path):
    """Generate a compact A5 PDF — no diagrams, multiple airfields per page."""
    styles = get_styles()

    doc = SimpleDocTemplate(
        output_path, pagesize=A5,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=8 * mm,
        title="SA Airfield Directory",
        author="Compiled from SACAA AIP & public sources",
    )

    story = []
    story.extend(build_cover(styles, len(airfields)))

    current_group = ''
    for airfield in airfields:
        group = airfield.get('group', '')
        if group and group != current_group:
            current_group = group
            story.append(Paragraph(clean(group), styles['AFGroup']))
        story.append(build_airfield_block(airfield, styles))

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    print(f"PDF generated: {output_path}")
    print(f"Total airfields: {len(airfields)}")


if __name__ == '__main__':
    print("SA Airfield Directory - Compact PDF Generator")
    print("=" * 50)

    print("\nParsing airfield directory...")
    airfields = parse_airfields(MD_FILE)
    print(f"  Found {len(airfields)} airfields")

    print("\nGenerating compact PDF...")
    generate_pdf(airfields, OUTPUT_PDF)

    file_size = os.path.getsize(OUTPUT_PDF)
    print(f"\nDone! {OUTPUT_PDF}")
    print(f"File size: {file_size / 1024:.0f} KB")
