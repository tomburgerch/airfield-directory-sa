#!/usr/bin/env python3
"""
Generate a printable A5 PDF airfield directory from AIRFIELD_DIRECTORY.md
One page per airfield with key information and diagrams where available.
"""

import re
import os
import sys
import requests
from io import BytesIO

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import (
    HexColor, black, white, grey, lightgrey, red, darkred,
    darkgreen, darkblue, orange
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether, Flowable
)
from reportlab.platypus.flowables import AnchorFlowable
from reportlab.pdfgen import canvas
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate, Frame
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage


# ── Constants ──────────────────────────────────────────────────────
A5_WIDTH, A5_HEIGHT = A5  # 148mm x 210mm
MARGIN = 8 * mm
CONTENT_WIDTH = A5_WIDTH - 2 * MARGIN
CONTENT_HEIGHT = A5_HEIGHT - 2 * MARGIN

# Colors
COLOR_HEADER_BG = HexColor('#1a365d')  # Dark navy
COLOR_HEADER_FG = white
COLOR_ACCENT = HexColor('#2b6cb0')     # Blue accent
COLOR_WARNING = HexColor('#c53030')    # Red for warnings
COLOR_CLOSED = HexColor('#9b2c2c')     # Dark red for closed
COLOR_MILITARY = HexColor('#2d3748')   # Dark gray for military
COLOR_ROW_ALT = HexColor('#f7fafc')    # Light gray for alternating rows
COLOR_BORDER = HexColor('#e2e8f0')     # Light border

DIAGRAMS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diagrams')
MD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'AIRFIELD_DIRECTORY.md')
OUTPUT_PDF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Airfield_Directory_A5.pdf')


# ── Styles ──────────────────────────────────────────────────────────
def get_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'FieldName', parent=styles['Normal'],
        fontSize=11, leading=13, textColor=white,
        fontName='Helvetica-Bold', alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        'FieldCode', parent=styles['Normal'],
        fontSize=8, leading=10, textColor=HexColor('#bee3f8'),
        fontName='Helvetica', alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        'SectionTitle', parent=styles['Normal'],
        fontSize=7.5, leading=9, textColor=COLOR_ACCENT,
        fontName='Helvetica-Bold', spaceBefore=3, spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        'FieldValue', parent=styles['Normal'],
        fontSize=6.5, leading=8, textColor=black,
        fontName='Helvetica',
    ))
    styles.add(ParagraphStyle(
        'FieldLabel', parent=styles['Normal'],
        fontSize=6.5, leading=8, textColor=HexColor('#4a5568'),
        fontName='Helvetica-Bold',
    ))
    styles.add(ParagraphStyle(
        'SmallNote', parent=styles['Normal'],
        fontSize=5.5, leading=7, textColor=HexColor('#718096'),
        fontName='Helvetica',
    ))
    styles.add(ParagraphStyle(
        'FreqValue', parent=styles['Normal'],
        fontSize=7.5, leading=9, textColor=COLOR_ACCENT,
        fontName='Helvetica-Bold',
    ))
    styles.add(ParagraphStyle(
        'Warning', parent=styles['Normal'],
        fontSize=6, leading=7.5, textColor=COLOR_WARNING,
        fontName='Helvetica-Bold',
    ))
    styles.add(ParagraphStyle(
        'StatusClosed', parent=styles['Normal'],
        fontSize=8, leading=10, textColor=white,
        fontName='Helvetica-Bold', alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'GroupTitle', parent=styles['Normal'],
        fontSize=9, leading=11, textColor=COLOR_HEADER_BG,
        fontName='Helvetica-Bold', alignment=TA_CENTER,
        spaceBefore=6, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        'PageNum', parent=styles['Normal'],
        fontSize=6, leading=7, textColor=HexColor('#a0aec0'),
        fontName='Helvetica', alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'RunwayHeader', parent=styles['Normal'],
        fontSize=6, leading=7, textColor=white,
        fontName='Helvetica-Bold', alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'RunwayCell', parent=styles['Normal'],
        fontSize=6, leading=7, textColor=black,
        fontName='Helvetica', alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'TOCTitle', parent=styles['Normal'],
        fontSize=11, leading=14, textColor=COLOR_HEADER_BG,
        fontName='Helvetica-Bold', alignment=TA_CENTER,
        spaceBefore=2, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        'TOCGroupHeader', parent=styles['Normal'],
        fontSize=7, leading=9, textColor=COLOR_ACCENT,
        fontName='Helvetica-Bold', spaceBefore=3, spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        'TOCEntry', parent=styles['Normal'],
        fontSize=6.5, leading=8.5, textColor=black,
        fontName='Helvetica',
    ))
    styles.add(ParagraphStyle(
        'TOCEntryCode', parent=styles['Normal'],
        fontSize=5.5, leading=8.5, textColor=HexColor('#718096'),
        fontName='Helvetica',
    ))
    styles.add(ParagraphStyle(
        'TOCPageNum', parent=styles['Normal'],
        fontSize=6.5, leading=8.5, textColor=COLOR_ACCENT,
        fontName='Helvetica-Bold', alignment=TA_RIGHT,
    ))

    return styles


# ── Markdown Parser ─────────────────────────────────────────────────
def parse_airfields(md_path):
    """Parse the markdown file and extract airfield data."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by airfield headers (### N. NAME)
    airfield_pattern = r'^### (\d+)\. (.+?)$'
    sections = re.split(r'^### \d+\.', content, flags=re.MULTILINE)
    headers = re.findall(airfield_pattern, content, re.MULTILINE)

    airfields = []
    current_group = ""

    # Also extract group headings
    group_pattern = r'^## (GROUP \d+:.+?)$'
    group_positions = [(m.start(), m.group(1)) for m in re.finditer(group_pattern, content, re.MULTILINE)]

    for i, (num, name) in enumerate(headers):
        section = sections[i + 1] if i + 1 < len(sections) else ""
        # Find first line to get full name
        first_line = section.split('\n')[0].strip()
        full_name = first_line.lstrip('. ').strip()

        airfield = parse_single_airfield(num, full_name, section)

        # Find which group this airfield belongs to
        header_pos = content.find(f'### {num}. ')
        for gpos, gname in reversed(group_positions):
            if gpos < header_pos:
                airfield['group'] = gname
                break

        airfields.append(airfield)

    return airfields


def parse_single_airfield(num, name, section):
    """Parse a single airfield section."""
    data = {
        'number': int(num),
        'name': name,
        'group': '',
        'fields': {},
        'runways': [],
        'notes': [],
        'frequencies_table': [],
        'contact': '',
        'warnings': [],
    }

    lines = section.split('\n')

    # Extract table fields (| **Key** | Value |)
    field_pattern = r'\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|'
    for line in lines:
        m = re.match(field_pattern, line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            # Clean up markdown formatting
            val = re.sub(r'\*\*(.+?)\*\*', r'\1', val)
            val = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', val)  # links
            data['fields'][key] = val

    # Extract runway table rows
    rwy_section = False
    rwy_headers_found = False
    for line in lines:
        if '**Runways' in line:
            rwy_section = True
            continue
        if rwy_section and re.match(r'\|\s*RWY\s*\|', line):
            rwy_headers_found = True
            continue
        if rwy_section and rwy_headers_found and re.match(r'\|\s*-', line):
            continue  # separator
        if rwy_section and rwy_headers_found and line.startswith('|'):
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if cols and cols[0] and not cols[0].startswith('-'):
                data['runways'].append(cols)
        elif rwy_section and rwy_headers_found and not line.startswith('|') and line.strip():
            if '**Notes' in line or '**Contact' in line or line.startswith('---'):
                rwy_section = False

    # Extract frequencies table
    freq_section = False
    for line in lines:
        if '**Frequencies:**' in line or '**Frequencies**' in line:
            freq_section = True
            continue
        if freq_section and re.match(r'\|\s*Service\s*\|', line):
            continue
        if freq_section and re.match(r'\|\s*-', line):
            continue
        if freq_section and line.startswith('|'):
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if len(cols) >= 2 and cols[0]:
                data['frequencies_table'].append(cols)
        elif freq_section and not line.startswith('|') and line.strip():
            freq_section = False

    # Extract notes
    note_section = False
    for line in lines:
        if line.strip().startswith('**Notes:**') or line.strip().startswith('**Notes**'):
            note_section = True
            continue
        if note_section and line.strip().startswith('- '):
            note = line.strip()[2:]
            # Clean markdown
            note = re.sub(r'\*\*(.+?)\*\*', r'\1', note)
            note = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', note)
            # Check for warnings
            if note.startswith(('WARNING', 'CAUTION')) or '⚠️' in note or '⛔' in note:
                data['warnings'].append(note)
            else:
                data['notes'].append(note)
        elif note_section and line.strip().startswith('---'):
            note_section = False

    # Extract contact
    for line in lines:
        if line.strip().startswith('**Contact:**'):
            data['contact'] = line.strip().replace('**Contact:**', '').strip()
            data['contact'] = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', data['contact'])

    return data


# ── Helper: clean emoji for PDF ─────────────────────────────────────
def clean_text(text):
    """Remove or replace emoji that can't render in standard PDF fonts."""
    replacements = {
        '⬅️': '[L]', '➡️': '[R]', '🌙': '[NIGHT]', '🚫': '[NO]',
        '🔒': '[PRIV]', '✈️': '[PUB]', '🪖': '[MIL]', '⛽': '[FUEL]',
        '❓': '(?)', '📅': '[DATE]', '⚠️': '[!]', '⛔': '[X]',
        '🏠': '', '🛩️': '', '🔴': '', '🟢': '', '🟡': '',
    }
    for emoji, replacement in replacements.items():
        text = text.replace(emoji, replacement)
    return text


# ── PDF Page Template ────────────────────────────────────────────────
class AirfieldPageTemplate(PageTemplate):
    def __init__(self, id, frames, **kwargs):
        PageTemplate.__init__(self, id, frames, **kwargs)


def draw_page_background(canvas_obj, doc):
    """Draw page number footer."""
    canvas_obj.saveState()
    canvas_obj.setFont('Helvetica', 5.5)
    canvas_obj.setFillColor(HexColor('#a0aec0'))
    canvas_obj.drawCentredString(
        A5_WIDTH / 2, 5 * mm,
        f"Western Cape VFR Airfield Directory — Page {doc.page}"
    )
    canvas_obj.restoreState()


# ── Build PDF ────────────────────────────────────────────────────────
def build_airfield_page(airfield, styles):
    """Build the flowable content for one airfield page."""
    elements = []
    f = airfield['fields']

    is_closed = '[X]' in clean_text(airfield['name']) or 'CLOSED' in airfield['name'].upper()
    is_military = '[MIL]' in clean_text(f.get('Access', '')) or 'MILITARY' in f.get('Access', '').upper()

    # ── Header bar ──
    header_bg = COLOR_CLOSED if is_closed else (COLOR_MILITARY if is_military else COLOR_HEADER_BG)

    # Name and code in header
    name_clean = clean_text(airfield['name'])
    # Shorten very long names
    if len(name_clean) > 45:
        name_clean = name_clean[:42] + '...'

    code = f.get('ICAO', f.get('ICAO / Code', f.get('Code', '')))
    code_clean = clean_text(code)

    header_data = [[
        Paragraph(f"<b>{name_clean}</b>", styles['FieldName']),
        Paragraph(f"#{airfield['number']}",
                  ParagraphStyle('NumStyle', parent=styles['FieldCode'], alignment=TA_RIGHT))
    ]]

    header_table = Table(header_data, colWidths=[CONTENT_WIDTH * 0.8, CONTENT_WIDTH * 0.2])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), header_bg),
        ('TEXTCOLOR', (0, 0), (-1, -1), white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (0, 0), 4),
        ('RIGHTPADDING', (-1, -1), (-1, -1), 4),
    ]))
    elements.append(header_table)

    # Code line under header
    if code_clean:
        status_parts = [code_clean]
        access = clean_text(f.get('Access', ''))
        if access:
            status_parts.append(access[:50])
        elements.append(Paragraph(
            ' | '.join(status_parts),
            ParagraphStyle('CodeLine', parent=styles['SmallNote'],
                          textColor=HexColor('#4a5568'), spaceBefore=1, spaceAfter=2)
        ))

    # ── Closed banner ──
    if is_closed:
        closed_data = [[Paragraph("CLOSED - DO NOT PLAN OPERATIONS", styles['StatusClosed'])]]
        closed_table = Table(closed_data, colWidths=[CONTENT_WIDTH])
        closed_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_WARNING),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(closed_table)
        elements.append(Spacer(1, 2 * mm))

    # ── Key Info Grid ──
    # Build a 2-column layout with the most important info
    coords = clean_text(f.get('Coordinates', ''))
    elevation = clean_text(f.get('Elevation', ''))
    freq = clean_text(f.get('Frequencies', f.get('Frequency', '')))
    joining = clean_text(f.get('Joining Alt', ''))
    circuit_alt = clean_text(f.get('Circuit Alt', f.get('Circuit', f.get('Pattern Alt', ''))))
    night = clean_text(f.get('Night Ops', ''))
    fuel = clean_text(f.get('Fuel', ''))
    hours = clean_text(f.get('Hours', ''))

    info_rows = []

    if coords:
        info_rows.append(('Coordinates', coords))
    if elevation:
        info_rows.append(('Elevation', elevation))
    if freq:
        info_rows.append(('Frequency', freq))
    if joining:
        info_rows.append(('Joining Alt', joining))
    if circuit_alt:
        info_rows.append(('Circuit Alt', circuit_alt))
    if night:
        info_rows.append(('Night Ops', night))
    if fuel:
        info_rows.append(('Fuel', fuel))
    if hours:
        info_rows.append(('Hours', hours))

    if info_rows:
        # Make a compact info table
        table_data = []
        for label, value in info_rows:
            # Highlight frequency in bold blue
            if label == 'Frequency' and value:
                val_para = Paragraph(f"<b>{value}</b>",
                    ParagraphStyle('FreqInline', parent=styles['FieldValue'],
                                  textColor=COLOR_ACCENT, fontName='Helvetica-Bold', fontSize=7))
            elif label == 'Elevation' and value:
                val_para = Paragraph(f"<b>{value}</b>",
                    ParagraphStyle('ElevInline', parent=styles['FieldValue'],
                                  fontName='Helvetica-Bold', fontSize=7))
            else:
                val_para = Paragraph(value[:80] if len(value) > 80 else value, styles['FieldValue'])

            table_data.append([
                Paragraph(f"<b>{label}</b>", styles['FieldLabel']),
                val_para
            ])

        info_table = Table(table_data, colWidths=[CONTENT_WIDTH * 0.22, CONTENT_WIDTH * 0.78])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (0, -1), 2),
            ('LEFTPADDING', (1, 0), (1, -1), 4),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [white, COLOR_ROW_ALT]),
        ]))
        elements.append(info_table)

    # ── Frequencies Table (for airports like FACT with multiple freqs) ──
    if airfield['frequencies_table']:
        elements.append(Spacer(1, 1.5 * mm))
        elements.append(Paragraph("FREQUENCIES", styles['SectionTitle']))

        freq_data = []
        for row in airfield['frequencies_table'][:8]:  # Limit to 8 rows
            freq_data.append([
                Paragraph(clean_text(row[0]), styles['FieldValue']),
                Paragraph(f"<b>{clean_text(row[1])}</b>",
                    ParagraphStyle('FT', parent=styles['FieldValue'],
                                  textColor=COLOR_ACCENT, fontName='Helvetica-Bold'))
            ])

        if freq_data:
            freq_table = Table(freq_data, colWidths=[CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.5])
            freq_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 0.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [white, COLOR_ROW_ALT]),
                ('LINEBELOW', (0, 0), (-1, -1), 0.25, COLOR_BORDER),
            ]))
            elements.append(freq_table)

    # ── Runway Table ──
    if airfield['runways']:
        elements.append(Spacer(1, 1.5 * mm))
        elements.append(Paragraph("RUNWAYS", styles['SectionTitle']))

        # Determine columns based on data
        max_cols = max(len(r) for r in airfield['runways'])
        if max_cols >= 6:
            headers = ['RWY', 'Length', 'Width', 'Surface', 'Str', 'Circuit']
            col_widths = [0.1, 0.22, 0.13, 0.22, 0.13, 0.2]
        elif max_cols >= 5:
            headers = ['RWY', 'Length', 'Width', 'Surface', 'Circuit']
            col_widths = [0.12, 0.25, 0.15, 0.25, 0.23]
        else:
            headers = ['RWY', 'Surface']
            col_widths = [0.3, 0.7]

        col_widths = [CONTENT_WIDTH * w for w in col_widths[:max_cols]]

        rwy_data = []
        # Header row
        rwy_data.append([Paragraph(h, styles['RunwayHeader']) for h in headers[:max_cols]])

        for row in airfield['runways']:
            cleaned = [clean_text(c) for c in row]
            # Pad row to match columns
            while len(cleaned) < max_cols:
                cleaned.append('')
            rwy_data.append([Paragraph(c[:20], styles['RunwayCell']) for c in cleaned[:max_cols]])

        rwy_table = Table(rwy_data, colWidths=col_widths)
        rwy_style = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_ACCENT),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ('GRID', (0, 0), (-1, -1), 0.25, COLOR_BORDER),
            ('FONTSIZE', (0, 0), (-1, -1), 6),
        ]
        # Alternating row colors
        for i in range(1, len(rwy_data)):
            if i % 2 == 0:
                rwy_style.append(('BACKGROUND', (0, i), (-1, i), COLOR_ROW_ALT))

        rwy_table.setStyle(TableStyle(rwy_style))
        elements.append(rwy_table)

    # ── Diagram (if available) ──
    diagram_path = find_diagram(airfield)
    if diagram_path and os.path.exists(diagram_path):
        elements.append(Spacer(1, 2 * mm))
        try:
            img = PILImage.open(diagram_path)
            img_w, img_h = img.size
            aspect = img_h / img_w

            # Max diagram size
            max_w = CONTENT_WIDTH * 0.95
            max_h = 50 * mm  # Larger diagrams for better readability

            display_w = max_w
            display_h = display_w * aspect
            if display_h > max_h:
                display_h = max_h
                display_w = display_h / aspect

            img_element = Image(diagram_path, width=display_w, height=display_h)
            elements.append(img_element)
            elements.append(Paragraph("Aerodrome diagram (verify currency)",
                ParagraphStyle('DiagCaption', parent=styles['SmallNote'],
                              alignment=TA_CENTER, fontSize=5)))
        except Exception as e:
            pass

    # ── Warnings ──
    if airfield['warnings']:
        elements.append(Spacer(1, 1 * mm))
        for w in airfield['warnings'][:3]:
            w_clean = clean_text(w)[:120]
            elements.append(Paragraph(f"[!] {w_clean}", styles['Warning']))

    # ── Notes ──
    if airfield['notes']:
        elements.append(Spacer(1, 1 * mm))
        elements.append(Paragraph("NOTES", styles['SectionTitle']))
        # Show most important notes, limited by space
        for note in airfield['notes'][:6]:
            note_clean = clean_text(note)[:120]
            elements.append(Paragraph(f"- {note_clean}", styles['SmallNote']))

    # ── Contact ──
    if airfield['contact']:
        elements.append(Spacer(1, 1 * mm))
        contact_clean = clean_text(airfield['contact'])[:100]
        elements.append(Paragraph(f"<b>Contact:</b> {contact_clean}", styles['SmallNote']))

    return elements


def find_diagram(airfield):
    """Find a diagram file for this airfield."""
    f = airfield['fields']
    icao = f.get('ICAO', f.get('ICAO / Code', f.get('Code', '')))

    candidates = []

    # Extract all FA-prefix ICAO codes from the field value
    all_codes = []
    if icao:
        fa_codes = re.findall(r'\b(FA[A-Z]{2,4})\b', icao.upper())
        all_codes.extend(fa_codes)
        # Also try first word if it looks like a code
        first_word = re.sub(r'[^A-Z0-9-]', '', icao.upper().split()[0])
        if first_word and len(first_word) >= 4:
            all_codes.append(first_word)

    # Try extracting ICAO from the name (e.g. "STELLENBOSCH (FASH)")
    name_codes = re.findall(r'\b(FA[A-Z]{2,4})\b', airfield['name'].upper())
    all_codes.extend(name_codes)

    # Build candidate filenames with multiple suffix patterns
    for code in all_codes:
        candidates.extend([
            f'{code}.png', f'{code}.jpg',
            f'{code}_AD01.png', f'{code}_AD02.png',
            f'{code}_chart.png',
        ])

    # Try by name slug
    name_slug = re.sub(r'[^a-z0-9]', '_', airfield['name'].lower().split('(')[0].strip())
    candidates.extend([f'{name_slug}.png', f'{name_slug}.jpg'])

    for c in candidates:
        path = os.path.join(DIAGRAMS_DIR, c)
        if os.path.exists(path):
            return path

    return None


def build_cover_page(styles, airfield_count=69):
    """Build the cover page."""
    elements = []
    elements.append(Spacer(1, 20 * mm))

    # Title
    title_style = ParagraphStyle(
        'CoverTitle', parent=styles['Normal'],
        fontSize=16, leading=20, textColor=COLOR_HEADER_BG,
        fontName='Helvetica-Bold', alignment=TA_CENTER,
    )
    elements.append(Paragraph("Western Cape", title_style))
    elements.append(Paragraph("Airfield Directory", title_style))
    elements.append(Spacer(1, 5 * mm))

    subtitle_style = ParagraphStyle(
        'CoverSubtitle', parent=styles['Normal'],
        fontSize=10, leading=14, textColor=HexColor('#4a5568'),
        fontName='Helvetica', alignment=TA_CENTER,
    )
    elements.append(Paragraph("For VFR Pilots Flying from", subtitle_style))
    elements.append(Paragraph("Morningstar (ZA-0120)",
        ParagraphStyle('CoverField', parent=subtitle_style,
                      fontName='Helvetica-Bold', fontSize=12)))

    elements.append(Spacer(1, 10 * mm))

    # Info box
    info_style = ParagraphStyle(
        'CoverInfo', parent=styles['Normal'],
        fontSize=7, leading=9, textColor=HexColor('#718096'),
        fontName='Helvetica', alignment=TA_CENTER,
    )
    elements.append(Paragraph(f"{airfield_count} Airfields | 8 Geographic Groups", info_style))
    elements.append(Paragraph("One page per airfield for quick reference", info_style))
    elements.append(Spacer(1, 15 * mm))

    # Disclaimer
    disc_style = ParagraphStyle(
        'CoverDisclaimer', parent=styles['Normal'],
        fontSize=5.5, leading=7, textColor=COLOR_WARNING,
        fontName='Helvetica', alignment=TA_CENTER,
    )
    elements.append(Paragraph(
        "[!] NOT FOR NAVIGATION - VERIFY ALL DATA AGAINST CURRENT SACAA AIP AND NOTAMs",
        disc_style))
    elements.append(Paragraph(
        "Data marked (?) could not be independently verified. Always contact airfield operators.",
        disc_style))

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph("Last Updated: 2026-03-09", info_style))
    elements.append(Paragraph("Compiled from SACAA AIP, OpenAIP, AirportGuide, AvCom forums", info_style))

    elements.append(PageBreak())
    return elements


def build_freq_reference_page(styles):
    """Build a frequency quick-reference page."""
    elements = []

    # Header
    header_data = [[Paragraph("<b>CAPE TOWN AREA FREQUENCIES</b>", styles['FieldName'])]]
    header_table = Table(header_data, colWidths=[CONTENT_WIDTH])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_HEADER_BG),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 2 * mm))

    freqs = [
        ('Cape Town ATIS', '127.000'),
        ('Cape Town Tower', '118.100'),
        ('Cape Town Approach', '119.700'),
        ('Cape Town Director', '124.350'),
        ('Cape Town Ground', '121.900'),
        ('Cape Town Clearance', '122.100'),
        ('Emergency', '121.500'),
        ('', ''),
        ('Morningstar', '126.800'),
        ('Stellenbosch (FASH)', '119.300'),
        ('Cape Winelands (FAWN)', '131.100'),
        ('Delta 200 (FADX)', '124.400'),
        ('Malmesbury (FAMY)', '131.500'),
        ('Diemerskraal', '124.200'),
        ('Worcester (FAWC)', '124.800'),
        ('Saldanha (FASD)', '122.700'),
        ('', ''),
        ('Langebaan MIL APP', '122.500'),
        ('Langebaan MIL TWR', '120.800'),
        ('George TWR', '118.900'),
        ('George APP', '128.200'),
        ('George ATIS', '126.225'),
        ('Oudtshoorn AFIS', '131.100'),
        ('Beaufort West AFIS', '125.600'),
    ]

    freq_data = []
    for service, freq in freqs:
        if not service:
            freq_data.append([Paragraph('', styles['SmallNote']), Paragraph('', styles['SmallNote'])])
        else:
            freq_data.append([
                Paragraph(service, styles['FieldValue']),
                Paragraph(f"<b>{freq}</b>",
                    ParagraphStyle('FRef', parent=styles['FieldValue'],
                                  textColor=COLOR_ACCENT, fontName='Helvetica-Bold', fontSize=7.5))
            ])

    freq_table = Table(freq_data, colWidths=[CONTENT_WIDTH * 0.55, CONTENT_WIDTH * 0.45])
    freq_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [white, COLOR_ROW_ALT]),
        ('LINEBELOW', (0, 0), (-1, -1), 0.25, COLOR_BORDER),
    ]))
    elements.append(freq_table)

    elements.append(PageBreak())
    return elements


class PageTracker(Flowable):
    """Invisible flowable that records which page it lands on."""
    def __init__(self, key, tracker_dict):
        Flowable.__init__(self)
        self.key = key
        self.tracker_dict = tracker_dict
        self.width = 0
        self.height = 0

    def draw(self):
        page = self.canv.getPageNumber()
        self.tracker_dict[self.key] = page


def build_toc_pages(airfields, page_map, styles):
    """Build clickable table of contents pages."""
    elements = []

    # Header
    header_data = [[Paragraph("<b>AIRFIELD INDEX</b>", styles['FieldName'])]]
    header_table = Table(header_data, colWidths=[CONTENT_WIDTH])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_HEADER_BG),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 2 * mm))

    current_group = ''
    toc_rows = []

    for airfield in airfields:
        group = airfield.get('group', '')
        if group and group != current_group:
            current_group = group
            # Flush current rows as a table
            if toc_rows:
                elements.append(_make_toc_table(toc_rows, styles))
                toc_rows = []
            # Group header
            group_clean = clean_text(group)
            elements.append(Paragraph(f"<b>{group_clean}</b>", styles['TOCGroupHeader']))

        num = airfield['number']
        name_clean = clean_text(airfield['name'])
        if len(name_clean) > 38:
            name_clean = name_clean[:35] + '...'

        f = airfield['fields']
        code = f.get('ICAO', f.get('ICAO / Code', f.get('Code', '')))
        code_clean = clean_text(code).split('(')[0].split(';')[0].strip()[:12]

        anchor_name = f"airfield_{num}"
        page_num = page_map.get(anchor_name, '?')

        # Clickable link to the airfield page
        link_text = f'<a href="#{anchor_name}" color="#1a365d">{name_clean}</a>'
        page_text = f'<a href="#{anchor_name}" color="#2b6cb0"><b>{page_num}</b></a>'

        toc_rows.append((link_text, code_clean, page_text))

    # Flush remaining rows
    if toc_rows:
        elements.append(_make_toc_table(toc_rows, styles))

    elements.append(PageBreak())
    return elements


def _make_toc_table(rows, styles):
    """Create a table of TOC entries."""
    table_data = []
    for link_text, code, page_text in rows:
        table_data.append([
            Paragraph(link_text, styles['TOCEntry']),
            Paragraph(code, styles['TOCEntryCode']),
            Paragraph(page_text, styles['TOCPageNum']),
        ])

    toc_table = Table(table_data,
                      colWidths=[CONTENT_WIDTH * 0.68, CONTENT_WIDTH * 0.18, CONTENT_WIDTH * 0.14])
    style_cmds = [
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0.8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0.8),
        ('LEFTPADDING', (0, 0), (0, -1), 2),
        ('LEFTPADDING', (1, 0), (1, -1), 2),
        ('RIGHTPADDING', (-1, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, -1), 0.15, COLOR_BORDER),
    ]
    for i in range(len(table_data)):
        if i % 2 == 1:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), COLOR_ROW_ALT))
    toc_table.setStyle(TableStyle(style_cmds))
    return toc_table


def build_story(airfields, styles, page_map, include_toc=False):
    """Build the full story (list of flowables) for the PDF."""
    story = []

    # Cover page
    story.extend(build_cover_page(styles, airfield_count=len(airfields)))

    # TOC pages (only on second pass when we have page numbers)
    if include_toc:
        story.extend(build_toc_pages(airfields, page_map, styles))

    # Frequency reference page
    story.extend(build_freq_reference_page(styles))

    # Airfield pages
    current_group = ''
    for airfield in airfields:
        # Group separator
        group = airfield.get('group', '')
        if group and group != current_group:
            current_group = group
            story.append(Paragraph(clean_text(group), styles['GroupTitle']))
            story.append(Spacer(1, 1 * mm))

        # Anchor for this airfield (for TOC linking)
        anchor_name = f"airfield_{airfield['number']}"
        story.append(AnchorFlowable(anchor_name))
        story.append(PageTracker(anchor_name, page_map))

        # Build airfield page
        page_elements = build_airfield_page(airfield, styles)
        story.extend(page_elements)
        story.append(PageBreak())

    return story


def generate_pdf(airfields, output_path):
    """Generate the complete A5 PDF with clickable TOC (two-pass build)."""
    styles = get_styles()
    page_map = {}

    # ── Pass 1: Build without TOC to capture page numbers ──
    print("  Pass 1: Calculating page numbers...")
    tmp_path = output_path + '.tmp'
    doc1 = SimpleDocTemplate(
        tmp_path, pagesize=A5,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=10 * mm,
    )
    story1 = build_story(airfields, styles, page_map, include_toc=False)
    doc1.build(story1, onFirstPage=draw_page_background, onLaterPages=draw_page_background)

    # Estimate TOC page count (affects page offsets)
    n_airfields = len(airfields)
    # ~30 entries per TOC page at current font size
    toc_pages = max(1, (n_airfields + 29) // 30)
    # Adjust page numbers by the TOC pages being inserted
    adjusted_map = {k: v + toc_pages for k, v in page_map.items()}

    # ── Pass 2: Build with TOC using adjusted page numbers ──
    print(f"  Pass 2: Building PDF with {toc_pages}-page TOC...")
    page_map2 = {}
    doc2 = SimpleDocTemplate(
        output_path, pagesize=A5,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=10 * mm,
        title="Western Cape Airfield Directory",
        author="Compiled from SACAA AIP & public sources",
    )
    story2 = build_story(airfields, styles, page_map2, include_toc=False)

    # Now build with TOC using adjusted page numbers
    story_final = []
    story_final.extend(build_cover_page(styles, airfield_count=len(airfields)))
    story_final.extend(build_toc_pages(airfields, adjusted_map, styles))
    story_final.extend(build_freq_reference_page(styles))

    current_group = ''
    for airfield in airfields:
        group = airfield.get('group', '')
        if group and group != current_group:
            current_group = group
            story_final.append(Paragraph(clean_text(group), styles['GroupTitle']))
            story_final.append(Spacer(1, 1 * mm))

        anchor_name = f"airfield_{airfield['number']}"
        story_final.append(AnchorFlowable(anchor_name))

        page_elements = build_airfield_page(airfield, styles)
        story_final.extend(page_elements)
        story_final.append(PageBreak())

    doc2.build(story_final, onFirstPage=draw_page_background, onLaterPages=draw_page_background)

    # Clean up temp file
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    print(f"PDF generated: {output_path}")
    print(f"Total airfields: {len(airfields)}")


# ── Download diagrams ────────────────────────────────────────────────
def download_sacaa_diagrams():
    """Try to download aerodrome diagrams from SACAA AIP PDFs."""
    # ICAO codes for fields that have SACAA AIP entries
    icao_codes = [
        'FASH', 'FACT', 'FASD', 'FALW', 'FAVR', 'FACI', 'FACW',
        'FAWC', 'FADS', 'FACE', 'FARS', 'FAAS', 'FACG', 'FAOB',
        'FASX', 'FAGG', 'FAMO', 'FAOH', 'FARD', 'FACY', 'FAPG',
        'FABW', 'FAPC', 'FAKA', 'FAAF',
    ]

    base_url = 'https://caasanwebsitestorage.blob.core.windows.net/aerodrone-and-helicompter-directory/'

    downloaded = 0
    for code in icao_codes:
        pdf_path = os.path.join(DIAGRAMS_DIR, f'{code}.pdf')
        if os.path.exists(pdf_path):
            continue

        url = f'{base_url}{code}AD2.pdf'
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(pdf_path, 'wb') as f:
                    f.write(resp.content)
                downloaded += 1
                print(f"  Downloaded: {code}AD2.pdf ({len(resp.content)} bytes)")
        except Exception as e:
            pass

    print(f"Downloaded {downloaded} SACAA AIP PDFs")


def extract_diagram_images():
    """Extract aerodrome diagram pages from SACAA PDFs as images."""
    try:
        import subprocess
        # Check if pdftoppm is available
        result = subprocess.run(['which', 'pdftoppm'], capture_output=True)
        has_pdftoppm = result.returncode == 0
    except:
        has_pdftoppm = False

    if not has_pdftoppm:
        print("pdftoppm not available - trying Python-based extraction")
        try:
            from pypdf import PdfReader
            for pdf_file in os.listdir(DIAGRAMS_DIR):
                if not pdf_file.endswith('.pdf'):
                    continue
                icao = pdf_file.replace('.pdf', '')
                png_path = os.path.join(DIAGRAMS_DIR, f'{icao}.png')
                if os.path.exists(png_path):
                    continue
                # Can't easily convert PDF pages to images without poppler
                # Skip for now
        except:
            pass
        return

    import subprocess
    for pdf_file in os.listdir(DIAGRAMS_DIR):
        if not pdf_file.endswith('.pdf'):
            continue
        icao = pdf_file.replace('.pdf', '')
        png_path = os.path.join(DIAGRAMS_DIR, f'{icao}.png')
        if os.path.exists(png_path):
            continue

        pdf_path = os.path.join(DIAGRAMS_DIR, pdf_file)
        try:
            # Extract last page (usually the diagram) at 200dpi
            # First get page count
            result = subprocess.run(
                ['pdfinfo', pdf_path],
                capture_output=True, text=True, timeout=10
            )
            pages = 1
            for line in result.stdout.split('\n'):
                if line.startswith('Pages:'):
                    pages = int(line.split(':')[1].strip())

            # Extract last page as image
            subprocess.run([
                'pdftoppm', '-png', '-r', '200',
                '-f', str(pages), '-l', str(pages),
                '-singlefile',
                pdf_path,
                os.path.join(DIAGRAMS_DIR, icao)
            ], timeout=30, capture_output=True)

            if os.path.exists(png_path):
                print(f"  Extracted diagram: {icao}.png")
        except Exception as e:
            pass


# ── Main ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 50)
    print("Western Cape Airfield Directory - A5 PDF Generator")
    print("=" * 50)

    # Step 1: Download SACAA diagrams
    print("\n[1/4] Downloading SACAA AIP diagrams...")
    os.makedirs(DIAGRAMS_DIR, exist_ok=True)
    download_sacaa_diagrams()

    # Step 2: Extract diagram images from PDFs
    print("\n[2/4] Extracting diagram images...")
    extract_diagram_images()

    # Step 3: Parse markdown
    print("\n[3/4] Parsing airfield directory...")
    airfields = parse_airfields(MD_FILE)
    print(f"  Found {len(airfields)} airfields")

    # Step 4: Generate PDF
    print("\n[4/4] Generating A5 PDF...")
    generate_pdf(airfields, OUTPUT_PDF)

    print(f"\nDone! Output: {OUTPUT_PDF}")
    file_size = os.path.getsize(OUTPUT_PDF)
    print(f"File size: {file_size / 1024:.1f} KB")
