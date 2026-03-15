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

# ── Tower phone lookup ──
TOWER_PHONES = {
    'FAOR': '+27 11 921 6262', 'FACT': '+27 21 937 1122',
    'FALE': '+27 32 436 5001', 'FALA': '+27 11 701 3278',
    'FAGC': '+27 11 805 3166', 'FAWB': '+27 12 543 1402',
    'FAGM': '+27 11 827 8884', 'FABL': '+27 51 433 1452',
    'FAPE': '+27 41 513 5851', 'FAEL': '+27 43 736 6161',
    'FAGG': '+27 44 803 7732', 'FAKM': '+27 53 851 1012',
    'FAUP': '+27 54 337 7900', 'FAKN': '+27 13 753 7519',
    'FAPP': '+27 15 288 0343', 'FAPM': '+27 33 392 3110',
    'FARB': '+27 35 786 0836', 'FAHS': '+27 15 799 2251',
}


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
    """Extract primary ICAO code from airfield fields."""
    f = airfield['fields']
    raw = f.get('ICAO', f.get('ICAO / Code', f.get('Code', '')))
    if raw:
        codes = re.findall(r'\b(FA[A-Z]{2,4})\b', raw.upper())
        if codes:
            return codes[0]
        return re.sub(r'[^A-Z0-9]', '', raw.upper().split()[0])[:8]
    return ''


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
    from diagrams_util import find_diagram as _find, DIAGRAMS_DIR

    # First try the standard lookup (PNG/JPG)
    path = _find(airfield)
    if path and os.path.exists(path) and path.lower().endswith(('.png', '.jpg', '.jpeg')):
        return path

    # Try PDF diagram — search with same suffixes as find_diagram but for .pdf
    icao = get_icao_code(airfield)
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
        page = doc[-1]  # last page is usually the diagram
        mat = fitz.Matrix(3.0, 3.0)  # ~216 DPI
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


def build_airfield_pdf(airfield, output_path, styles, temp_dir=None):
    """Generate a single-page A4 PDF for one airfield."""
    f = airfield['fields']

    is_closed = 'CLOSED' in airfield['name'].upper() or '[X]' in clean(airfield['name'])
    is_military = 'MILITARY' in f.get('Access', '').upper()

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=10 * mm,
        title=clean(airfield['name']),
    )

    story = []

    # ── Header bar ──
    name = clean(airfield['name'])
    icao = get_icao_code(airfield)
    access = clean(f.get('Access', ''))
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
    coords = clean(f.get('Coordinates', ''))
    elev = clean(f.get('Elevation', ''))
    freq = clean(f.get('Frequencies', f.get('Frequency', '')))
    joining = clean(f.get('Joining Alt', ''))
    circuit = clean(f.get('Circuit Alt', f.get('Circuit', f.get('Pattern Alt', ''))))
    night = clean(f.get('Night Ops', ''))
    fuel = clean(f.get('Fuel', ''))
    hours = clean(f.get('Hours', ''))

    # Tower phone
    tower_phone = TOWER_PHONES.get(icao, '')

    rows = []
    for label, val in [('Coordinates', coords), ('Elevation', elev),
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
    if airfield['frequencies_table']:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph('Frequencies', styles['AFSection']))
        freq_rows = []
        for row in airfield['frequencies_table'][:8]:
            freq_rows.append([
                Paragraph(clean(row[0]), styles['AFValue']),
                Paragraph(f'<b>{clean(row[1])}</b>', styles['AFFreq']),
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

    # ── Runways ──
    if airfield['runways']:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph('Runways', styles['AFSection']))
        max_cols = max(len(r) for r in airfield['runways'])
        if max_cols >= 5:
            heads = ['RWY', 'Length', 'Width', 'Surface', 'Strength', 'Circuit']
            widths = [0.10, 0.18, 0.12, 0.25, 0.15, 0.20]
        elif max_cols >= 3:
            heads = ['RWY', 'Length', 'Surface']
            widths = [0.2, 0.3, 0.5]
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
            rwy_data.append([Paragraph(c[:25], styles['AFRwyCell']) for c in cells[:max_cols]])

        rt = Table(rwy_data, colWidths=widths)
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
    if airfield['warnings']:
        story.append(Spacer(1, 2 * mm))
        for w in airfield['warnings'][:5]:
            story.append(Paragraph(f'[!] {clean(w)[:200]}', styles['AFWarning']))

    # ── Notes ──
    if airfield['notes']:
        story.append(Spacer(1, 2 * mm))
        for note in airfield['notes'][:5]:
            story.append(Paragraph(f'- {clean(note)[:200]}', styles['AFNote']))

    # ── Contact ──
    if airfield['contact']:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            f"<b>Contact:</b> {clean(airfield['contact'])[:150]}", styles['AFNote']))

    # ── Diagram ──
    diagram_path = find_diagram_image(airfield, temp_dir=temp_dir)
    if diagram_path:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph('Aerodrome Diagram', styles['AFSection']))
        try:
            img = Image(diagram_path)
            iw, ih = img.drawWidth, img.drawHeight
            max_w = CONTENT_WIDTH
            max_h = 180 * mm  # leave room for footer
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


def generate_airfield_pdfs(airfields, output_dir):
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
                build_airfield_pdf(airfield, path, styles, temp_dir=temp_dir)
                mapping[airfield['number']] = fname
            except Exception as e:
                print(f"  Warning: Failed to generate PDF for {airfield['name']}: {e}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"  Generated {len(mapping)} individual airfield PDFs")
    return mapping


if __name__ == '__main__':
    from parse_markdown import parse_airfields

    MD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'AIRFIELD_DIRECTORY.md')
    OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public', 'airfield-pdfs')

    print("Generating individual airfield PDFs...")
    airfields = parse_airfields(MD_FILE)
    mapping = generate_airfield_pdfs(airfields, OUT_DIR)
    print(f"Done! {len(mapping)} PDFs in {OUT_DIR}")
