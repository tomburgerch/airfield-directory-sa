#!/usr/bin/env python3
"""
Generate individual 1-page A4 PDF info sheets for each airfield.

Designed for pilots to download and print before flights.
Includes all key data plus aerodrome diagram if available.
"""

import os
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, Image, HRFlowable,
)

from pdf_styles import EMOJI_MAP, clean_text
from source_utils import resolve_source, is_official_source, get_source_url

# ── Page dimensions ──
A4_WIDTH, A4_HEIGHT = A4
MARGIN = 12 * mm
CONTENT_WIDTH = A4_WIDTH - 2 * MARGIN

# ── Colors ──
NAVY = HexColor('#1a365d')
BLUE = HexColor('#2b6cb0')
RED = HexColor('#c53030')
GRAY = HexColor('#4a5568')
LIGHT_GRAY = HexColor('#f7fafc')
BORDER = HexColor('#e2e8f0')
DARK_RED = HexColor('#9b2c2c')
DARK_GRAY = HexColor('#2d3748')
GREEN = HexColor('#276749')
TEXT_MUTED = HexColor('#a0aec0')


def clean(text):
    return clean_text(text).strip()


def get_styles():
    styles = getSampleStyleSheet()
    defs = [
        ('AFName', {'fontSize': 14, 'leading': 17, 'textColor': white,
                     'fontName': 'Helvetica-Bold'}),
        ('AFCode', {'fontSize': 10, 'leading': 12, 'textColor': HexColor('#bee3f8'),
                     'fontName': 'Helvetica', 'alignment': TA_RIGHT}),
        ('AFLabel', {'fontSize': 8, 'leading': 10, 'textColor': GRAY,
                      'fontName': 'Helvetica-Bold'}),
        ('AFValue', {'fontSize': 8, 'leading': 10, 'fontName': 'Helvetica'}),
        ('AFFreq', {'fontSize': 9, 'leading': 11, 'textColor': BLUE,
                     'fontName': 'Helvetica-Bold'}),
        ('AFRwyHead', {'fontSize': 7.5, 'leading': 9, 'textColor': white,
                        'fontName': 'Helvetica-Bold', 'alignment': TA_CENTER}),
        ('AFRwyCell', {'fontSize': 7.5, 'leading': 9, 'fontName': 'Helvetica',
                        'alignment': TA_CENTER}),
        ('AFWarning', {'fontSize': 8, 'leading': 10, 'textColor': RED,
                        'fontName': 'Helvetica-Bold'}),
        ('AFNote', {'fontSize': 7, 'leading': 9, 'textColor': GRAY,
                     'fontName': 'Helvetica'}),
        ('AFSection', {'fontSize': 8, 'leading': 10, 'textColor': BLUE,
                        'fontName': 'Helvetica-Bold', 'spaceBefore': 4, 'spaceAfter': 1}),
        ('Disclaimer', {'fontSize': 5.5, 'leading': 7, 'textColor': HexColor('#a0aec0'),
                         'fontName': 'Helvetica', 'alignment': TA_CENTER}),
    ]
    for name, kwargs in defs:
        styles.add(ParagraphStyle(name, parent=styles['Normal'], **kwargs))
    return styles


def get_icao_code(airfield):
    """Extract primary ICAO code from airfield dict (JSON schema)."""
    return airfield.get('icao', '')


def pdf_filename(airfield):
    """Generate a PDF filename for an airfield."""
    num = airfield['number']
    icao = get_icao_code(airfield)
    if icao:
        return f'{num}_{icao}.pdf'
    slug = re.sub(r'[^a-z0-9]+', '_', airfield['name'].lower().split('(')[0].strip())[:30]
    return f'{num}_{slug}.pdf'


def find_diagram_image(airfield, temp_dir=None):
    """Find diagram for this airfield, converting PDF to PNG if needed."""
    from diagrams_util import DIAGRAMS_DIR

    icao = get_icao_code(airfield)

    # Check diagram field in JSON
    diagram_info = airfield.get('diagram', {})
    if diagram_info and diagram_info.get('file'):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), diagram_info['file'])
        if os.path.exists(path) and path.lower().endswith(('.png', '.jpg', '.jpeg')):
            return path

    # Try standard PNG/JPG lookup by ICAO
    if icao:
        for ext in ['.png', '.jpg']:
            path = os.path.join(DIAGRAMS_DIR, f'{icao}{ext}')
            if os.path.exists(path):
                return path
        # Also search by name codes
        name_codes = re.findall(r'\b(FA[A-Z]{2,4})\b', airfield['name'].upper())
        for code in name_codes:
            for ext in ['.png', '.jpg']:
                path = os.path.join(DIAGRAMS_DIR, f'{code}{ext}')
                if os.path.exists(path):
                    return path

    # Try PDF diagram and convert
    if not icao:
        return None

    pdf_candidates = [
        f'{icao}.pdf', f'{icao}_AD01.pdf', f'{icao}_AD02.pdf',
        f'{icao}_AD04.pdf', f'{icao}_chart.pdf',
    ]
    pdf_path = None
    for c in pdf_candidates:
        p = os.path.join(DIAGRAMS_DIR, c)
        if os.path.exists(p):
            pdf_path = p
            break

    if not pdf_path:
        return None

    try:
        import fitz
        doc = fitz.open(pdf_path)
        page = doc[-1]
        mat = fitz.Matrix(3.0, 3.0)
        pix = page.get_pixmap(matrix=mat)
        if temp_dir:
            png_path = os.path.join(temp_dir, f'{icao}_diagram.png')
        else:
            png_path = os.path.join(DIAGRAMS_DIR, f'{icao}_temp.png')
        pix.save(png_path)
        doc.close()
        return png_path
    except ImportError:
        return None
    except Exception:
        return None


def build_airfield_pdf(airfield, output_path, styles, temp_dir=None, meta=None):
    """Generate a single-page A4 PDF for one airfield. Reads JSON-schema data."""
    registry = (meta or {}).get('source_registry', {})

    name = clean(airfield['name'])
    icao = get_icao_code(airfield)
    status = airfield.get('status', 'active')
    is_closed = status == 'closed'
    is_military = status == 'military'

    basic = airfield.get('basic_info', {})
    ops = airfield.get('operations', {})
    comms = airfield.get('communications', {})
    rwy_data = airfield.get('runways', {})

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=10 * mm,
        title=name,
    )

    story = []

    # ── Header bar ──
    access = clean(ops.get('access', '') or '')
    code_line = icao
    if access:
        code_line = f'{icao}  |  {access}' if icao else access

    bg = DARK_RED if is_closed else (DARK_GRAY if is_military else NAVY)
    header = Table(
        [[Paragraph(f'<b>{name}</b>', styles['AFName']),
          Paragraph(code_line, styles['AFCode'])]],
        colWidths=[CONTENT_WIDTH * 0.7, CONTENT_WIDTH * 0.3],
    )
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (0, 0), 6),
        ('RIGHTPADDING', (-1, -1), (-1, -1), 6),
    ]))
    story.append(header)

    if is_closed:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            '<b>CLOSED — DO NOT PLAN OPERATIONS</b>',
            ParagraphStyle('Closed', parent=styles['AFWarning'],
                           alignment=TA_CENTER, fontSize=12)))
        story.append(Spacer(1, 8 * mm))
        _add_disclaimer(story, styles)
        doc.build(story)
        return

    story.append(Spacer(1, 2 * mm))

    # ── Info grid ──
    coords = basic.get('coordinates', {})
    coord_dms = clean(coords.get('dms', ''))
    elev = clean(basic.get('elevation', '') or '')
    freq = clean(comms.get('primary_freq', '') or '')
    joining = clean(ops.get('joining_alt', '') or '')
    circuit = clean(ops.get('circuit_alt', '') or '')
    fuel = clean(ops.get('fuel', '') or '')
    hours = clean(ops.get('hours', '') or '')
    night_val = ops.get('night_ops')
    night = '' if night_val is None or night_val is False else (clean(str(night_val)) if night_val is not True else 'Yes')

    # Tower phone from JSON
    tower_phone = comms.get('tower_phone', '')

    rows = []
    for label, val in [('Coordinates', coord_dms), ('Elevation', elev),
                        ('Frequency', freq), ('Joining Alt', joining),
                        ('Circuit Alt', circuit), ('Access', access),
                        ('Fuel', fuel), ('Night Ops', night), ('Hours', hours)]:
        if val:
            if label == 'Frequency':
                val_para = Paragraph(f'<b>{val[:80]}</b>', styles['AFFreq'])
            else:
                val_para = Paragraph(val[:100], styles['AFValue'])
            rows.append([Paragraph(f'<b>{label}</b>', styles['AFLabel']), val_para])

    if tower_phone:
        rows.append([Paragraph('<b>Tower Phone</b>', styles['AFLabel']),
                     Paragraph(tower_phone, styles['AFValue'])])

    if rows:
        info = Table(rows, colWidths=[CONTENT_WIDTH * 0.18, CONTENT_WIDTH * 0.82])
        info.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (0, -1), 4),
            ('LEFTPADDING', (1, 0), (1, -1), 6),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [white, LIGHT_GRAY]),
        ]))
        story.append(info)

    # ── Frequencies table ──
    freq_table = comms.get('frequencies_table', [])
    if freq_table:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph('Frequencies', styles['AFSection']))
        freq_rows = []
        for row in freq_table[:8]:
            if isinstance(row, dict):
                service = clean(row.get('service', ''))
                freq_val = clean(row.get('freq', ''))
            else:
                service = clean(row[0]) if len(row) > 0 else ''
                freq_val = clean(row[1]) if len(row) > 1 else ''
            freq_rows.append([
                Paragraph(service, styles['AFValue']),
                Paragraph(f'<b>{freq_val}</b>', styles['AFFreq']),
            ])
        if freq_rows:
            ft = Table(freq_rows, colWidths=[CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.5])
            ft.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 0.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('LINEBELOW', (0, 0), (-1, -1), 0.2, BORDER),
            ]))
            story.append(ft)

    # ── Runways (list of dicts) ──
    runways = rwy_data.get('data', [])
    if runways:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph('Runways', styles['AFSection']))

        has_width = any(r.get('width') for r in runways)
        has_strength = any(r.get('strength') for r in runways)
        has_circuit = any(r.get('circuit') for r in runways)

        heads = ['RWY', 'Length']
        keys = ['rwy', 'length']
        widths_pct = [0.10, 0.18]
        if has_width:
            heads.append('Width')
            keys.append('width')
            widths_pct.append(0.12)
        heads.append('Surface')
        keys.append('surface')
        widths_pct.append(0.25)
        if has_strength:
            heads.append('Strength')
            keys.append('strength')
            widths_pct.append(0.15)
        if has_circuit:
            heads.append('Circuit')
            keys.append('circuit')
            widths_pct.append(0.20)
        widths = [CONTENT_WIDTH * w for w in widths_pct]

        rwy_rows = [[Paragraph(h, styles['AFRwyHead']) for h in heads]]
        for rwy in runways:
            cells = [clean(rwy.get(k, '') or '')[:25] for k in keys]
            rwy_rows.append([Paragraph(c, styles['AFRwyCell']) for c in cells])

        rt = Table(rwy_rows, colWidths=widths)
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('GRID', (0, 0), (-1, -1), 0.3, BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ]))
        story.append(rt)

    # ── Warnings ──
    warnings = airfield.get('warnings', [])
    if warnings:
        story.append(Spacer(1, 2 * mm))
        for w in warnings[:5]:
            w_text = w.get('text', w) if isinstance(w, dict) else w
            story.append(Paragraph(f'[!] {clean(w_text)[:200]}', styles['AFWarning']))

    # ── NOTAMs (up to 2 with text for A4) ──
    notam_items = airfield.get('notams', {}).get('items', []) if isinstance(airfield.get('notams'), dict) else []
    if notam_items:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph('NOTAMs', styles['AFSection']))
        for notam in notam_items[:2]:
            expiry = f' (until {notam["expiry"]})' if notam.get('expiry') else ''
            story.append(Paragraph(f'[NOTAM] {clean(notam["text"])[:180]}{expiry}', styles['AFWarning']))
        fetched = airfield.get('notams', {}).get('fetched', '')
        if fetched:
            story.append(Paragraph(
                f'NOTAMs as of {fetched[:10]} — see online version for current NOTAMs',
                ParagraphStyle('NotamDate', parent=styles['AFNote'], fontSize=6, textColor=TEXT_MUTED)))

    # ── Notes ──
    notes = airfield.get('notes', [])
    if notes:
        story.append(Spacer(1, 2 * mm))
        for note in notes[:5]:
            n_text = note.get('text', note) if isinstance(note, dict) else note
            story.append(Paragraph(f'- {clean(n_text)[:200]}', styles['AFNote']))

    # ── Contact ──
    contact = airfield.get('contact', {})
    if isinstance(contact, dict):
        contact_parts = [v for v in [contact.get('name'), contact.get('phone'), contact.get('address')] if v]
        contact_str = ', '.join(contact_parts)
    else:
        contact_str = str(contact) if contact else ''
    if contact_str:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            f"<b>Contact:</b> {clean(contact_str)[:150]}", styles['AFNote']))

    # ── Diagram ──
    diagram_path = find_diagram_image(airfield, temp_dir=temp_dir)
    if diagram_path:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph('Aerodrome Diagram', styles['AFSection']))
        try:
            img = Image(diagram_path)
            iw, ih = img.drawWidth, img.drawHeight
            max_w = CONTENT_WIDTH
            max_h = 180 * mm
            scale = min(max_w / iw, max_h / ih, 1.0)
            img.drawWidth = iw * scale
            img.drawHeight = ih * scale
            story.append(img)
            story.append(Paragraph(
                'Verify currency against official AIP',
                ParagraphStyle('DiagCap', parent=styles['AFNote'],
                               alignment=TA_CENTER, fontSize=6)))
        except Exception:
            pass

    # ── Sources summary ──
    story.append(Spacer(1, 3 * mm))
    source_style = ParagraphStyle('SourceNote', parent=styles['AFNote'],
                                  fontSize=6, textColor=TEXT_MUTED)
    collected_dates = []
    source_names_seen = set()
    for section in ['basic_info', 'operations', 'communications', 'runways']:
        src = airfield.get(section, {}).get('source', {})
        if src.get('collected'):
            collected_dates.append(src['collected'])
        resolved = resolve_source(src, registry)
        sname = resolved.get('name', '')
        if sname:
            source_names_seen.add(sname)

    is_fa = bool(re.search(r'\bFA[A-Z]{2}\b', icao))
    if is_fa and collected_dates:
        earliest = min(collected_dates)
        story.append(Paragraph(f'Data source: SACAA AIP (collected {earliest})', source_style))
    elif source_names_seen:
        story.append(Paragraph(f'Sources: {", ".join(sorted(source_names_seen))}', source_style))

    # ── Disclaimer footer ──
    story.append(Spacer(1, 4 * mm))
    _add_disclaimer(story, styles)

    doc.build(story)


def _add_disclaimer(story, styles):
    story.append(HRFlowable(width='100%', thickness=0.5,
                             color=HexColor('#e2e8f0'), spaceAfter=2 * mm))
    story.append(Paragraph(
        'SUPPLEMENTARY REFERENCE ONLY — Does NOT replace SACAA AIP, NOTAMs, '
        'or official aerodrome charts. Verify all data before flight. '
        'Use entirely at your own risk. | wagyu.wings',
        styles['Disclaimer']))


def generate_airfield_pdfs(airfields, output_dir, meta=None):
    """Generate individual PDFs for all airfields. Returns {number: filename} mapping."""
    import tempfile
    import shutil

    os.makedirs(output_dir, exist_ok=True)
    styles = get_styles()
    mapping = {}

    temp_dir = tempfile.mkdtemp(prefix='airfield_diagrams_')
    try:
        for airfield in airfields:
            fname = pdf_filename(airfield)
            path = os.path.join(output_dir, fname)
            try:
                build_airfield_pdf(airfield, path, styles, temp_dir=temp_dir, meta=meta)
                mapping[airfield['number']] = fname
            except Exception as e:
                print(f"  Warning: Failed to generate PDF for {airfield['name']}: {e}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"  Generated {len(mapping)} individual airfield PDFs")
    return mapping


if __name__ == '__main__':
    import json
    from shared import AIRFIELDS_JSON

    OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public', 'airfield-pdfs')

    print("Loading airfield data from JSON...")
    with open(AIRFIELDS_JSON, 'r', encoding='utf-8') as _f:
        _data = json.load(_f)
    meta, airfields = _data['meta'], _data['airfields']

    print(f"Generating individual airfield PDFs for {len(airfields)} airfields...")
    mapping = generate_airfield_pdfs(airfields, OUT_DIR, meta=meta)
    print(f"Done! {len(mapping)} PDFs in {OUT_DIR}")
