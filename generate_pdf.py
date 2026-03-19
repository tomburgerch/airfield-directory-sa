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

import json
from shared import MD_FILE, BASE_DIR, AIRFIELDS_JSON

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


def build_airfield_block(airfield, styles, meta=None):
    """Build a compact block for one airfield (no page break). Reads JSON-schema data."""
    elements = []

    name = clean(airfield['name'])
    icao = airfield.get('icao', '')
    status = airfield.get('status', 'active')
    is_closed = status == 'closed'
    is_military = status == 'military'

    basic = airfield.get('basic_info', {})
    ops = airfield.get('operations', {})
    comms = airfield.get('communications', {})
    rwy_data = airfield.get('runways', {})

    # ── Header row ──
    if len(name) > 50:
        name = name[:47] + '...'

    bg = DARK_RED if is_closed else (DARK_GRAY if is_military else NAVY)
    header = Table(
        [[Paragraph(f"<b>{name}</b>", styles['AFName']),
          Paragraph(icao, styles['AFCode'])]],
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
    coords = basic.get('coordinates', {})
    coord_dms = clean(coords.get('dms', ''))
    elev = clean(basic.get('elevation', '') or '')
    freq = clean(comms.get('primary_freq', '') or '')
    joining = clean(ops.get('joining_alt', '') or '')
    circuit = clean(ops.get('circuit_alt', '') or '')
    access = clean(ops.get('access', '') or '')
    fuel = clean(ops.get('fuel', '') or '')
    hours = clean(ops.get('hours', '') or '')
    night_val = ops.get('night_ops')
    night = '' if night_val is None or night_val is False else (clean(str(night_val)) if night_val is not True else 'Yes')

    rows = []
    for label, val in [('Coords', coord_dms), ('Elev', elev), ('Freq', freq),
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
    freq_table = comms.get('frequencies_table', [])
    if freq_table:
        freq_rows = []
        for row in freq_table[:6]:
            if isinstance(row, dict):
                service = clean(row.get('service', ''))
                freq_val = clean(row.get('freq', ''))
            else:
                service = clean(row[0]) if len(row) > 0 else ''
                freq_val = clean(row[1]) if len(row) > 1 else ''
            freq_rows.append([
                Paragraph(service, styles['AFValue']),
                Paragraph(f"<b>{freq_val}</b>", styles['AFFreq']),
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

    # ── Runways (compact, list of dicts) ──
    runways = rwy_data.get('data', [])
    if runways:
        has_width = any(r.get('width') for r in runways)
        has_circuit = any(r.get('circuit') for r in runways)

        if has_width:
            heads = ['RWY', 'Len', 'Wid', 'Sfc']
            keys = ['rwy', 'length', 'width', 'surface']
            widths = [0.12, 0.22, 0.16, 0.28]
            if has_circuit:
                heads.append('Cct')
                keys.append('circuit')
                widths.append(0.22)
        else:
            heads = ['RWY', 'Surface']
            keys = ['rwy', 'surface']
            widths = [0.3, 0.7]
        widths = [CONTENT_WIDTH * w for w in widths]

        rwy_rows = [[Paragraph(h, styles['AFRwyHead']) for h in heads]]
        for rwy in runways:
            cells = [clean(rwy.get(k, '') or '')[:18] for k in keys]
            rwy_rows.append([Paragraph(c, styles['AFRwyCell']) for c in cells])

        rt = Table(rwy_rows, colWidths=widths)
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
    for w in airfield.get('warnings', [])[:2]:
        w_text = w.get('text', w) if isinstance(w, dict) else w
        elements.append(Paragraph(f"[!] {clean(w_text)[:120]}", styles['AFWarning']))

    # ── NOTAMs (count only for A5) ──
    notam_items = airfield.get('notams', {}).get('items', []) if isinstance(airfield.get('notams'), dict) else []
    if notam_items:
        elements.append(Paragraph(
            f"[NOTAM] {len(notam_items)} active — see online version",
            styles['AFWarning']))

    # ── Key notes (max 3, short) ──
    for note in airfield.get('notes', [])[:3]:
        n_text = note.get('text', note) if isinstance(note, dict) else note
        elements.append(Paragraph(f"- {clean(n_text)[:120]}", styles['AFNote']))

    # ── Contact ──
    contact = airfield.get('contact', {})
    if isinstance(contact, dict):
        contact_parts = [v for v in [contact.get('name'), contact.get('phone')] if v]
        contact_str = ', '.join(contact_parts)
    else:
        contact_str = str(contact) if contact else ''
    if contact_str:
        elements.append(Paragraph(
            f"<b>Contact:</b> {clean(contact_str)[:100]}", styles['AFNote']))

    # ── Source footer ──
    import re as _re
    collected_dates = []
    for section in ['basic_info', 'operations', 'communications', 'runways']:
        src = airfield.get(section, {}).get('source', {})
        if src.get('collected'):
            collected_dates.append(src['collected'])
    earliest = min(collected_dates) if collected_dates else ''
    is_fa = bool(_re.search(r'\bFA[A-Z]{2}\b', icao))
    if is_fa and earliest:
        elements.append(Paragraph(
            f"Source: SACAA AIP ({earliest})", styles['AFNote']))
    elif not is_fa:
        elements.append(Paragraph(
            "Sources: Multiple — see online version", styles['AFNote']))

    elements.append(Spacer(1, 3 * mm))
    return KeepTogether(elements)


def build_cover(styles, count, meta=None):
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
    scan_date = (meta or {}).get('last_full_scan', '')
    elements.append(Paragraph(f"Data collected: {scan_date}" if scan_date else "See online version for dates", info))
    # List source names from registry
    registry = (meta or {}).get('source_registry', {})
    source_names = [v.get('name', k) for k, v in registry.items()]
    if source_names:
        elements.append(Paragraph(f"Sources: {', '.join(source_names)}", info))
    elements.append(PageBreak())
    return elements


def generate_pdf(airfields, output_path, meta=None):
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
    story.extend(build_cover(styles, len(airfields), meta=meta))

    current_group = ''
    for airfield in airfields:
        group = airfield.get('group', '')
        if group and group != current_group:
            current_group = group
            story.append(Paragraph(clean(group), styles['AFGroup']))
        story.append(build_airfield_block(airfield, styles, meta=meta))

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    print(f"PDF generated: {output_path}")
    print(f"Total airfields: {len(airfields)}")


if __name__ == '__main__':
    print("SA Airfield Directory - Compact PDF Generator")
    print("=" * 50)

    print("\nLoading airfield data from JSON...")
    with open(AIRFIELDS_JSON, 'r', encoding='utf-8') as _f:
        _data = json.load(_f)
    meta, airfields = _data['meta'], _data['airfields']
    print(f"  Found {len(airfields)} airfields")

    print("\nGenerating compact PDF...")
    generate_pdf(airfields, OUTPUT_PDF, meta=meta)

    file_size = os.path.getsize(OUTPUT_PDF)
    print(f"\nDone! {OUTPUT_PDF}")
    print(f"File size: {file_size / 1024:.0f} KB")
