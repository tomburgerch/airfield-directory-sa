#!/usr/bin/env python3
"""
Generate a printable A5 PDF airfield directory from AIRFIELD_DIRECTORY.md
One page per airfield with key information and diagrams where available.
"""

import os
import re

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, Flowable
)
from reportlab.platypus.flowables import AnchorFlowable
from PIL import Image as PILImage

from parse_markdown import parse_airfields
from pdf_styles import (
    get_styles, clean_text,
    A5_WIDTH, A5_HEIGHT, MARGIN, CONTENT_WIDTH, CONTENT_HEIGHT,
    COLOR_HEADER_BG, COLOR_ACCENT, COLOR_WARNING, COLOR_CLOSED,
    COLOR_MILITARY, COLOR_ROW_ALT, COLOR_BORDER,
)
from diagrams_util import find_diagram, download_sacaa_diagrams, extract_diagram_images

MD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'AIRFIELD_DIRECTORY.md')
OUTPUT_PDF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Airfield_Directory_A5.pdf')


# ── PDF Page Background ──────────────────────────────────────────────
def draw_page_background(canvas_obj, doc):
    """Draw page number footer."""
    canvas_obj.saveState()
    canvas_obj.setFont('Helvetica', 5.5)
    canvas_obj.setFillColor(HexColor('#a0aec0'))
    canvas_obj.drawCentredString(
        A5_WIDTH / 2, 5 * mm,
        f"South African Airfield Directory — Page {doc.page}"
    )
    canvas_obj.restoreState()


class PageTracker(Flowable):
    """Invisible flowable that records which page it lands on."""
    def __init__(self, key, tracker_dict):
        Flowable.__init__(self)
        self.key = key
        self.tracker_dict = tracker_dict
        self.width = 0
        self.height = 0

    def draw(self):
        self.tracker_dict[self.key] = self.canv.getPageNumber()


# ── Airfield Page Builder ─────────────────────────────────────────────
def build_airfield_page(airfield, styles):
    """Build the flowable content for one airfield page."""
    elements = []
    f = airfield['fields']

    is_closed = '[X]' in clean_text(airfield['name']) or 'CLOSED' in airfield['name'].upper()
    is_military = '[MIL]' in clean_text(f.get('Access', '')) or 'MILITARY' in f.get('Access', '').upper()

    # ── Header bar ──
    header_bg = COLOR_CLOSED if is_closed else (COLOR_MILITARY if is_military else COLOR_HEADER_BG)
    name_clean = clean_text(airfield['name'])
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
    coords = clean_text(f.get('Coordinates', ''))
    elevation = clean_text(f.get('Elevation', ''))
    freq = clean_text(f.get('Frequencies', f.get('Frequency', '')))
    joining = clean_text(f.get('Joining Alt', ''))
    circuit_alt = clean_text(f.get('Circuit Alt', f.get('Circuit', f.get('Pattern Alt', ''))))
    night = clean_text(f.get('Night Ops', ''))
    fuel = clean_text(f.get('Fuel', ''))
    hours = clean_text(f.get('Hours', ''))

    info_rows = []
    for label, value in [('Coordinates', coords), ('Elevation', elevation),
                          ('Frequency', freq), ('Joining Alt', joining),
                          ('Circuit Alt', circuit_alt), ('Night Ops', night),
                          ('Fuel', fuel), ('Hours', hours)]:
        if value:
            info_rows.append((label, value))

    if info_rows:
        table_data = []
        for label, value in info_rows:
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

    # ── Frequencies Table ──
    if airfield['frequencies_table']:
        elements.append(Spacer(1, 1.5 * mm))
        elements.append(Paragraph("FREQUENCIES", styles['SectionTitle']))

        freq_data = []
        for row in airfield['frequencies_table'][:8]:
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

        rwy_data = [[Paragraph(h, styles['RunwayHeader']) for h in headers[:max_cols]]]
        for row in airfield['runways']:
            cleaned = [clean_text(c) for c in row]
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
        for i in range(1, len(rwy_data)):
            if i % 2 == 0:
                rwy_style.append(('BACKGROUND', (0, i), (-1, i), COLOR_ROW_ALT))
        rwy_table.setStyle(TableStyle(rwy_style))
        elements.append(rwy_table)

    # ── Diagram ──
    diagram_path = find_diagram(airfield)
    if diagram_path and os.path.exists(diagram_path):
        elements.append(Spacer(1, 2 * mm))
        try:
            img = PILImage.open(diagram_path)
            img_w, img_h = img.size
            aspect = img_h / img_w

            max_w = CONTENT_WIDTH * 0.95
            max_h = 70 * mm
            display_w = max_w
            display_h = display_w * aspect
            if display_h > max_h:
                display_h = max_h
                display_w = display_h / aspect

            elements.append(Image(diagram_path, width=display_w, height=display_h))
            elements.append(Paragraph("Aerodrome diagram (verify currency)",
                ParagraphStyle('DiagCaption', parent=styles['SmallNote'],
                              alignment=TA_CENTER, fontSize=5)))
        except Exception:
            pass

    # ── Warnings ──
    if airfield['warnings']:
        elements.append(Spacer(1, 1 * mm))
        for w in airfield['warnings'][:3]:
            w_clean = clean_text(w)[:200]
            elements.append(Paragraph(f"[!] {w_clean}", styles['Warning']))

    # ── Notes ──
    if airfield['notes']:
        elements.append(Spacer(1, 1 * mm))
        elements.append(Paragraph("NOTES", styles['SectionTitle']))
        for note in airfield['notes'][:6]:
            note_clean = clean_text(note)[:200]
            elements.append(Paragraph(f"- {note_clean}", styles['SmallNote']))

    # ── Contact ──
    if airfield['contact']:
        elements.append(Spacer(1, 1 * mm))
        contact_clean = clean_text(airfield['contact'])[:160]
        elements.append(Paragraph(f"<b>Contact:</b> {contact_clean}", styles['SmallNote']))

    return elements


# ── Cover Page ────────────────────────────────────────────────────────
def build_cover_page(styles, airfield_count=69):
    """Build the cover page with prominent disclaimer."""
    elements = []
    elements.append(Spacer(1, 15 * mm))

    title_style = ParagraphStyle(
        'CoverTitle', parent=styles['Normal'],
        fontSize=18, leading=22, textColor=COLOR_HEADER_BG,
        fontName='Helvetica-Bold', alignment=TA_CENTER,
    )
    elements.append(Paragraph("South African", title_style))
    elements.append(Paragraph("Airfield Directory", title_style))
    elements.append(Spacer(1, 4 * mm))

    subtitle_style = ParagraphStyle(
        'CoverSubtitle', parent=styles['Normal'],
        fontSize=10, leading=14, textColor=HexColor('#4a5568'),
        fontName='Helvetica', alignment=TA_CENTER,
    )
    elements.append(Paragraph("VFR Pilot Quick Reference", subtitle_style))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        f"<b>{airfield_count} Airfields</b> across all provinces",
        ParagraphStyle('CoverStats', parent=subtitle_style,
                      fontName='Helvetica', fontSize=9)))
    elements.append(Paragraph("One page per airfield — coordinates, frequencies, runways, diagrams",
        ParagraphStyle('CoverDesc', parent=subtitle_style, fontSize=7, textColor=HexColor('#718096'))))
    elements.append(Spacer(1, 10 * mm))

    # ── Prominent disclaimer box ──
    disc_title = ParagraphStyle(
        'DiscTitle', parent=styles['Normal'],
        fontSize=9, leading=11, textColor=white,
        fontName='Helvetica-Bold', alignment=TA_CENTER,
    )
    disc_body = ParagraphStyle(
        'DiscBody', parent=styles['Normal'],
        fontSize=7, leading=9.5, textColor=white,
        fontName='Helvetica', alignment=TA_CENTER,
    )
    disc_rows = [
        [Paragraph("<b>IMPORTANT DISCLAIMER</b>", disc_title)],
        [Paragraph(
            "This directory is a <b>supplementary reference only</b> and does "
            "<b>NOT replace</b> official aviation publications.",
            disc_body)],
        [Paragraph(
            "Pilots must always consult the current <b>SACAA AIP</b>, active "
            "<b>NOTAMs</b>, and official aerodrome charts before flight. "
            "Contact airfield operators to verify access, fuel, hours, and "
            "runway status.",
            disc_body)],
        [Paragraph(
            "Data marked (?) is unverified. No warranty is given for accuracy "
            "or completeness. Use entirely at your own risk.",
            disc_body)],
    ]
    disc_table = Table(disc_rows, colWidths=[CONTENT_WIDTH * 0.92])
    disc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_WARNING),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (0, 0), 5),
        ('TOPPADDING', (0, 1), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, -1), (0, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROUNDEDCORNERS', [3, 3, 3, 3]),
    ]))
    elements.append(disc_table)

    elements.append(Spacer(1, 10 * mm))

    info_style = ParagraphStyle(
        'CoverInfo', parent=styles['Normal'],
        fontSize=7, leading=9, textColor=HexColor('#718096'),
        fontName='Helvetica', alignment=TA_CENTER,
    )
    elements.append(Paragraph("Last Updated: 2026-03-11", info_style))
    elements.append(Paragraph("Sources: SACAA AIP (Jan 2026), OpenAIP, AirportGuide, AvCom forums", info_style))
    elements.append(PageBreak())
    return elements


# ── How to Use / Legend Page ─────────────────────────────────────────
def build_legend_page(styles):
    """Build a How to Use page with legend and reading guide."""
    elements = []

    header_data = [[Paragraph("<b>HOW TO USE THIS DIRECTORY</b>", styles['FieldName'])]]
    header_table = Table(header_data, colWidths=[CONTENT_WIDTH])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_HEADER_BG),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 3 * mm))

    body = ParagraphStyle('LegendBody', parent=styles['Normal'],
                          fontSize=7, leading=9.5, fontName='Helvetica')
    body_bold = ParagraphStyle('LegendBold', parent=body, fontName='Helvetica-Bold')
    label = ParagraphStyle('LegendLabel', parent=body,
                           fontName='Helvetica-Bold', textColor=HexColor('#4a5568'))
    section = ParagraphStyle('LegendSection', parent=styles['SectionTitle'], fontSize=8)

    elements.append(Paragraph("EACH AIRFIELD PAGE INCLUDES", section))
    items = [
        ("Header bar", "Airfield name and sequence number. Navy = public, dark gray = military, red = closed."),
        ("Key info grid", "Coordinates, elevation, primary frequency (bold blue), joining/circuit altitudes, access, fuel, hours."),
        ("Frequencies table", "All known frequencies for the airfield in blue."),
        ("Runways table", "Designation, length, width, surface, PCN strength, and circuit direction."),
        ("Diagram", "Aerodrome chart where available — always verify currency against official AIP."),
        ("Warnings", "Critical safety information shown in red."),
        ("Notes", "Operational notes, PPR requirements, noise-sensitive areas, etc."),
    ]
    for lbl, desc in items:
        row = [[Paragraph(f"<b>{lbl}</b>", label), Paragraph(desc, body)]]
        t = Table(row, colWidths=[CONTENT_WIDTH * 0.22, CONTENT_WIDTH * 0.78])
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(t)

    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph("SYMBOLS &amp; ABBREVIATIONS", section))
    legend_items = [
        ("(?)", "Data could not be independently verified"),
        ("[!]", "Warning — safety-critical information"),
        ("[X]", "Airfield is CLOSED — do not plan operations"),
        ("[L] / [R]", "Left / Right circuit direction"),
        ("PPR", "Prior Permission Required — contact before arriving"),
        ("AFIS", "Aerodrome Flight Information Service"),
        ("FAXXX", "ICAO code (SA civil aerodromes use FA prefix)"),
        ("ZA-XXXX", "Unlicensed airfield identifier"),
    ]
    legend_data = []
    for sym, meaning in legend_items:
        legend_data.append([
            Paragraph(f"<b>{sym}</b>", ParagraphStyle('Sym', parent=body,
                      fontName='Helvetica-Bold', textColor=COLOR_ACCENT)),
            Paragraph(meaning, body),
        ])
    legend_table = Table(legend_data, colWidths=[CONTENT_WIDTH * 0.18, CONTENT_WIDTH * 0.82])
    legend_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [white, COLOR_ROW_ALT]),
    ]))
    elements.append(legend_table)

    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph("QUICK NAVIGATION", section))
    elements.append(Paragraph(
        "Use the <b>Airfield Index</b> (next pages) to jump directly to any airfield. "
        "All entries are clickable in the PDF. Airfields are grouped by geographic region.",
        body))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "The <b>Cape Town Area Frequencies</b> page provides a quick-reference "
        "for the most commonly used frequencies in the Western Cape.",
        body))

    elements.append(PageBreak())
    return elements


# ── Frequency Reference Page ─────────────────────────────────────────
def build_freq_reference_page(styles):
    """Build a frequency quick-reference page."""
    elements = []

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


# ── Table of Contents ─────────────────────────────────────────────────
def build_toc_pages(airfields, page_map, styles):
    """Build clickable table of contents pages."""
    elements = []

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
            if toc_rows:
                elements.append(_make_toc_table(toc_rows, styles))
                toc_rows = []
            elements.append(Paragraph(f"<b>{clean_text(group)}</b>", styles['TOCGroupHeader']))

        num = airfield['number']
        name_clean = clean_text(airfield['name'])
        if len(name_clean) > 38:
            name_clean = name_clean[:35] + '...'

        f = airfield['fields']
        code = f.get('ICAO', f.get('ICAO / Code', f.get('Code', '')))
        code_clean = clean_text(code).split('(')[0].split(';')[0].strip()[:12]

        anchor_name = f"airfield_{num}"
        page_num = page_map.get(anchor_name, '?')

        link_text = f'<a href="#{anchor_name}" color="#1a365d">{name_clean}</a>'
        page_text = f'<a href="#{anchor_name}" color="#2b6cb0"><b>{page_num}</b></a>'
        toc_rows.append((link_text, code_clean, page_text))

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


# ── PDF Generation ────────────────────────────────────────────────────
def generate_pdf(airfields, output_path):
    """Generate the complete A5 PDF with clickable TOC (two-pass build)."""
    styles = get_styles()
    page_map = {}

    # Pass 1: Build without TOC to capture page numbers
    print("  Pass 1: Calculating page numbers...")
    tmp_path = output_path + '.tmp'
    doc1 = SimpleDocTemplate(
        tmp_path, pagesize=A5,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=10 * mm,
    )

    story1 = []
    story1.extend(build_cover_page(styles, airfield_count=len(airfields)))
    story1.extend(build_legend_page(styles))
    story1.extend(build_freq_reference_page(styles))
    current_group = ''
    for airfield in airfields:
        group = airfield.get('group', '')
        if group and group != current_group:
            current_group = group
            story1.append(Paragraph(clean_text(group), styles['GroupTitle']))
            story1.append(Spacer(1, 1 * mm))
        anchor_name = f"airfield_{airfield['number']}"
        story1.append(AnchorFlowable(anchor_name))
        story1.append(PageTracker(anchor_name, page_map))
        story1.extend(build_airfield_page(airfield, styles))
        story1.append(PageBreak())

    doc1.build(story1, onFirstPage=draw_page_background, onLaterPages=draw_page_background)

    # Estimate TOC pages and adjust
    n_airfields = len(airfields)
    toc_pages = max(1, (n_airfields + 29) // 30)
    adjusted_map = {k: v + toc_pages for k, v in page_map.items()}

    # Pass 2: Build with TOC using adjusted page numbers
    print(f"  Pass 2: Building PDF with {toc_pages}-page TOC...")
    doc2 = SimpleDocTemplate(
        output_path, pagesize=A5,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=10 * mm,
        title="Western Cape Airfield Directory",
        author="Compiled from SACAA AIP & public sources",
    )

    story_final = []
    story_final.extend(build_cover_page(styles, airfield_count=len(airfields)))
    story_final.extend(build_legend_page(styles))
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
        story_final.extend(build_airfield_page(airfield, styles))
        story_final.append(PageBreak())

    doc2.build(story_final, onFirstPage=draw_page_background, onLaterPages=draw_page_background)

    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    print(f"PDF generated: {output_path}")
    print(f"Total airfields: {len(airfields)}")


# ── Main ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 50)
    print("Western Cape Airfield Directory - A5 PDF Generator")
    print("=" * 50)

    print("\n[1/4] Downloading SACAA AIP diagrams...")
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diagrams'), exist_ok=True)
    download_sacaa_diagrams()

    print("\n[2/4] Extracting diagram images...")
    extract_diagram_images()

    print("\n[3/4] Parsing airfield directory...")
    airfields = parse_airfields(MD_FILE)
    print(f"  Found {len(airfields)} airfields")

    print("\n[4/4] Generating A5 PDF...")
    generate_pdf(airfields, OUTPUT_PDF)

    print(f"\nDone! Output: {OUTPUT_PDF}")
    file_size = os.path.getsize(OUTPUT_PDF)
    print(f"File size: {file_size / 1024:.1f} KB")
