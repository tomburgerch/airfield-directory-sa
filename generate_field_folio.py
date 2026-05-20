#!/usr/bin/env python3
"""
Field Folio: compact A5 booklet of SA airfields for the flight folio.

Output: two PDFs.

  Field_Folio_A5.pdf            — 12 A5 pages, sequential. Print as-is on
                                   A5, or use printer "booklet" mode.
  Field_Folio_Booklet_A4.pdf    — 3 A4 landscape sheets, pre-imposed for
                                   saddle-stitch. Duplex print on long
                                   edge, stack, fold once down the middle.

Coverage: Western Cape, Eastern Cape, KwaZulu-Natal.
One row per airfield. Symbols documented on the cover page.
"""

import json
import os
import re
from typing import Optional

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4, A5, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'airfields.json')
OUT_A5 = os.path.join(BASE_DIR, 'Field_Folio_A5.pdf')
OUT_BOOKLET = os.path.join(BASE_DIR, 'Field_Folio_Booklet_A4.pdf')

# Fonts -----------------------------------------------------------------
# Use Helvetica + Courier (built-in) so the script has no font dependencies.
SERIF = 'Helvetica'
SERIF_BOLD = 'Helvetica-Bold'
MONO = 'Courier'
MONO_BOLD = 'Courier-Bold'

# Colors ----------------------------------------------------------------
NAVY = HexColor('#1a365d')
ACCENT = HexColor('#9b2c2c')
INK = HexColor('#1a202c')
MUTED = HexColor('#718096')
BAND = HexColor('#edf2f7')
RULE = HexColor('#cbd5e0')

# Page geometry ---------------------------------------------------------
A5_W, A5_H = A5                       # 148.5 × 210 mm portrait
A4_W, A4_H = landscape(A4)            # 297 × 210 mm

PAGE_MARGIN_X = 5 * mm
PAGE_MARGIN_TOP = 6 * mm
PAGE_MARGIN_BOTTOM = 6 * mm

# Row layout (within an A5 page) ----------------------------------------
ROW_HEIGHT = 4.6 * mm
ROW_FONT = 7.2
HEADER_FONT = 9
SECTION_FONT = 11

# Column x-offsets relative to A5 left margin (mm).
# Total content width = 148.5 - 2*5 = 138.5 mm.
COLS = [
    ('icao',  0.0,   14.0, 'l'),
    ('name',  14.0,  46.0, 'l'),
    ('elev',  60.0,  10.0, 'r'),
    ('freq',  71.0,  17.0, 'l'),
    ('rwy',   89.0,  39.0, 'l'),
    ('flags', 129.0, 9.0,  'l'),
]


# ── Data extraction ───────────────────────────────────────────────────

EMOJI_RE = re.compile(
    r'[☀-➿⬀-⯿'
    r'\U0001f300-\U0001faff\U0001f000-\U0001f9ff]'
)

def strip(s: str) -> str:
    if not s:
        return ''
    s = EMOJI_RE.sub('', s)
    # Remove leftover lonely separator dashes / question marks
    s = re.sub(r'\s+[—–-]\s*$', '', s)
    s = re.sub(r'\s+\(\?\)\s*$', '', s)
    return s.strip()

def elev_ft(af) -> str:
    raw = strip((af.get('basic_info') or {}).get('elevation') or '')
    m = re.search(r'([\d,]+)\s*ft', raw)
    if m:
        return m.group(1).replace(',', '')
    m = re.search(r'~?(\d+)', raw)
    return m.group(1) if m else '—'

def freq(af) -> str:
    raw = strip((af.get('communications') or {}).get('primary_freq') or '')
    if not raw:
        return '—'
    m = re.search(r'(\d{2,3}\.\d{1,3})', raw)
    return m.group(1) if m else raw[:8]

def name_short(af) -> str:
    n = af.get('name', '')
    # Detect closed/military markers (check original before stripping)
    suffix = ''
    if re.search(r'CLOSED', n, re.I):
        suffix = ' [X]'
    elif re.search(r'MILITARY|AIR FORCE|NAVAL', n, re.I):
        suffix = ' [M]'
    # Strip "(FAXX)" anywhere — we show ICAO separately
    n = re.sub(r'\s*\([A-Z0-9-]{3,8}\)\s*', ' ', n)
    # Strip annotations after em-dash
    n = re.sub(r'\s*[—–]\s*.*$', '', n)
    # Strip "/ ex-..." parentheticals
    n = re.sub(r'\s*/\s*ex-.*$', '', n, flags=re.I)
    n = n.strip()
    # Strip "AIRPORT" / "AIRFIELD" / "INTERNATIONAL" anywhere — loop until stable
    for _ in range(4):
        prev = n
        n = re.sub(r'\s+(AIRPORT|AIRFIELD|AIRSTRIP|INTERNATIONAL)\b', ' ', n)
        n = re.sub(r'\s+', ' ', n).strip()
        if n == prev:
            break
    n = strip(n)
    return (n + suffix).strip()

def icao_short(af) -> str:
    ic = af.get('icao', '')
    return ic if ic and not ic.startswith('ZA-') else ''

def surface_code(s: str) -> str:
    s = strip(s or '').lower()
    if 'asphalt' in s or 'tar' in s or 'paved' in s:
        return 'T'
    if 'concrete' in s:
        return 'C'
    if 'gravel' in s or 'compacted' in s:
        return 'V'
    if 'grass' in s or 'turf' in s:
        return 'G'
    if 'sand' in s or 'dirt' in s:
        return 'D'
    return '?'

def length_m(s: str) -> Optional[int]:
    s = strip(s or '')
    if not s:
        return None
    m = re.search(r'([\d,]+)\s*m', s)
    if not m:
        return None
    try:
        return int(m.group(1).replace(',', ''))
    except ValueError:
        return None

def width_m(s: str) -> Optional[int]:
    s = strip(s or '')
    m = re.search(r'(\d+)\s*m', s)
    return int(m.group(1)) if m else None

def _pair_key(rwy: str):
    """Return a canonical key for a runway so opposing ends collapse to one entry.
    '05' and '23' → ('05','23'). '05/23' → ('05','23'). Side suffix L/R stripped."""
    rwy = rwy.replace(' ', '').upper().rstrip('LRC')
    if '/' in rwy:
        a, b = rwy.split('/', 1)
        a = a.rstrip('LRC'); b = b.rstrip('LRC')
    elif rwy.isdigit():
        try:
            n = int(rwy)
            b_n = (n + 18) if n <= 18 else (n - 18)
            a, b = f'{n:02d}', f'{b_n:02d}'
        except ValueError:
            return (rwy,)
    else:
        return (rwy,)
    return tuple(sorted([a, b]))

_RWY_NAME_RE = re.compile(r'^\d{1,2}[LRC]?(/\d{1,2}[LRC]?)?$')

def runway_text(af) -> str:
    data = (af.get('runways') or {}).get('data') or []
    seen = {}
    order = []
    for r in data:
        rwy_raw = strip(r.get('rwy') or '').upper().replace(' ', '')
        if not rwy_raw or rwy_raw == '?':
            continue
        # Drop non-runway rows (e.g. "Service", "Durban Tower" leaking in)
        if not _RWY_NAME_RE.match(rwy_raw):
            continue
        key = _pair_key(rwy_raw)
        if key in seen:
            continue
        sc = surface_code(r.get('surface') or '')
        L = length_m(r.get('length') or '')
        W = width_m(r.get('width') or '')
        # Render as "05/23"
        if len(key) == 2:
            display = f'{key[0]}/{key[1]}'
        else:
            display = rwy_raw
        if L and W:
            seg = f'{display} {sc}{L}x{W}'
        elif L:
            seg = f'{display} {sc}{L}'
        else:
            seg = f'{display} {sc}?'
        seen[key] = seg
        order.append(seg)
    if not order:
        return '—'
    # Truncate by character budget so we don't crash into the FLG column.
    MAX = 38
    out = []
    for seg in order:
        candidate = (' '.join(out + [seg])) if out else seg
        if len(candidate) > MAX:
            out.append('+')
            break
        out.append(seg)
    return ' '.join(out)

def flags(af) -> str:
    """Compact flag string: L=lighting/night, F=fuel, T=tower/controlled."""
    out = []
    ops = af.get('operations') or {}
    if ops.get('night_ops'):
        out.append('L')
    fuel = strip(ops.get('fuel') or '')
    if fuel and fuel != '—':
        out.append('F')
    comms = af.get('communications') or {}
    # If primary freq looks like a TWR or APP, mark T
    raw_freq = (comms.get('primary_freq') or '') + ' ' + (af.get('name') or '')
    if re.search(r'\b(TWR|TOWER|INTERNATIONAL)\b', raw_freq, re.I):
        out.append('T')
    return ''.join(out)


# ── Filtering / sorting ───────────────────────────────────────────────

def useful(af) -> bool:
    """Keep airfields that contribute at least one piece of decision-relevant data
    beyond just an elevation guess."""
    rwys = (af.get('runways') or {}).get('data') or []
    has_freq = bool(strip((af.get('communications') or {}).get('primary_freq') or ''))
    has_real_rwy = any(
        length_m(r.get('length') or '') or surface_code(r.get('surface') or '') in ('T', 'G', 'V', 'C', 'D')
        for r in rwys
    )
    return has_freq or has_real_rwy

def priority(af) -> tuple:
    """Sort: ICAO airfields first (more likely to be real/active),
    then unknowns. Within group, by name."""
    has_icao = 0 if icao_short(af) else 1
    has_freq = 0 if (strip((af.get('communications') or {}).get('primary_freq') or '')) else 1
    return (has_icao, has_freq, name_short(af))


# ── Rendering primitives ──────────────────────────────────────────────

def draw_text(c, x_mm, y_mm, text, font=SERIF, size=8, color=INK, align='l'):
    c.setFont(font, size)
    c.setFillColor(color)
    tw = c.stringWidth(text, font, size)
    if align == 'r':
        x_mm_eff = x_mm - tw / mm
    elif align == 'c':
        x_mm_eff = x_mm - (tw / mm) / 2
    else:
        x_mm_eff = x_mm
    c.drawString(x_mm_eff * mm, y_mm * mm, text)

def draw_a5_page(c, origin_x_mm, origin_y_mm, page_spec):
    """Render one A5 page's content onto canvas at the given origin (mm).

    page_spec is a dict: {
        'page_no': int,
        'kind': 'cover' | 'freqs' | 'fields' | 'notes',
        ...
    }
    """
    # Page outline (light box so the fold is visually clear when proofing)
    # Drawn as a subtle 0.2pt border just for trim reference.
    c.setStrokeColor(RULE)
    c.setLineWidth(0.2)
    c.rect(origin_x_mm * mm, origin_y_mm * mm, A5_W, A5_H, fill=0, stroke=0)

    def x(mm_off):  # within this A5
        return origin_x_mm + PAGE_MARGIN_X / mm + mm_off
    def y_top(mm_off):
        return origin_y_mm + (A5_H / mm) - PAGE_MARGIN_TOP / mm - mm_off

    kind = page_spec['kind']
    pno = page_spec['page_no']

    if kind == 'cover':
        render_cover(c, x, y_top, page_spec)
    elif kind == 'freqs':
        render_freqs(c, x, y_top, page_spec)
    elif kind == 'fields':
        render_fields(c, x, y_top, page_spec)
    elif kind == 'notes':
        render_notes(c, x, y_top, page_spec)

    # Footer page number, centered
    cx = origin_x_mm + (A5_W / mm) / 2
    draw_text(c, cx, origin_y_mm + 3, f'— {pno} —', font=SERIF, size=7, color=MUTED, align='c')


def find_field(data, predicate):
    for a in data['airfields']:
        if predicate(a):
            return a
    return None

def render_cover(c, x, y_top, spec):
    data = spec.get('data')
    # Big title
    draw_text(c, x(0), y_top(8), 'FIELD FOLIO', font=SERIF_BOLD, size=18, color=NAVY)
    draw_text(c, x(0), y_top(15), 'SA airfields — Western Cape · Eastern Cape · KZN',
              font=SERIF, size=8.5, color=MUTED)
    draw_text(c, x(0), y_top(20), 'Compiled 2026-05-20  ·  Offline reference only',
              font=SERIF, size=7, color=MUTED)

    # Horizontal rule
    c.setStrokeColor(NAVY); c.setLineWidth(0.6)
    c.line(x(0) * mm, y_top(23) * mm, (x(0) + 138.5) * mm, y_top(23) * mm)

    # Emergency block
    draw_text(c, x(0), y_top(30), 'EMERGENCY', font=SERIF_BOLD, size=9.5, color=ACCENT)
    em = [
        ('121.500',  'Civil emergency (VHF guard)'),
        ('243.000',  'Military emergency'),
        ('123.450',  'Air-to-air'),
        ('124.800',  'GAP common (uncontrolled SA)'),
        ('126.900',  'Cape Town information / FIS'),
        ('082 911',  'ER24'),
        ('10177',    'Ambulance (mobile)'),
        ('0800 11 12 13', 'AMD SAR'),
    ]
    yy = 36
    for f, label in em:
        draw_text(c, x(0), y_top(yy), f, font=MONO_BOLD, size=8.5, color=INK)
        draw_text(c, x(30), y_top(yy), label, font=SERIF, size=8, color=INK)
        yy += 4.5

    # Symbols legend
    yy = 78
    draw_text(c, x(0), y_top(yy), 'SYMBOLS', font=SERIF_BOLD, size=9.5, color=NAVY)
    yy += 6
    legend = [
        ('T',  'Tar / asphalt / paved'),
        ('G',  'Grass'),
        ('V',  'Gravel / compacted'),
        ('C',  'Concrete'),
        ('?',  'Surface unknown'),
        ('L',  'Lighting / night ops'),
        ('F',  'Fuel available'),
        ('T*', 'Tower / controlled'),
    ]
    # 2-column legend
    half = (len(legend) + 1) // 2
    for i, (sym, desc) in enumerate(legend):
        col = i // half
        row = i % half
        xx = 0 if col == 0 else 70
        draw_text(c, x(xx), y_top(yy + row * 4.5), sym, font=MONO_BOLD, size=8.5, color=ACCENT)
        draw_text(c, x(xx + 8), y_top(yy + row * 4.5), desc, font=SERIF, size=8, color=INK)
    yy += half * 4.5 + 3

    # Row format
    draw_text(c, x(0), y_top(yy), 'ROW FORMAT', font=SERIF_BOLD, size=9.5, color=NAVY)
    yy += 5.5
    draw_text(c, x(0), y_top(yy), 'ICAO  NAME            ELEV  FREQ    RWYS                FLAGS',
              font=MONO_BOLD, size=7.2, color=MUTED)
    yy += 4
    draw_text(c, x(0), y_top(yy), 'FAVG  VIRGINIA          20  120.6   05/23 T1067x18      LFT',
              font=MONO, size=7.2, color=INK)
    yy += 4
    draw_text(c, x(0), y_top(yy), 'Length × width in metres. ELEV in ft AMSL.',
              font=SERIF, size=7.5, color=MUTED)
    yy += 4
    draw_text(c, x(0), y_top(yy), 'Up to 3 runway pairs shown; "+" indicates more.',
              font=SERIF, size=7.5, color=MUTED)

    # ── HOME BASE block ────────────────────────────────────────
    yy += 8
    draw_text(c, x(0), y_top(yy), 'HOME BASE', font=SERIF_BOLD, size=9.5, color=ACCENT)
    yy += 5.5
    if data:
        homes = [
            ('Now',  find_field(data, lambda a: 'MORNINGSTAR' in a.get('name','').upper())),
            ('Next', find_field(data, lambda a: a.get('icao') == 'FAVG')),
        ]
        for label, af in homes:
            if not af:
                continue
            nm = name_short(af) or '?'
            ic = icao_short(af) or '—'
            row = (
                f'{label:<5} {ic:<6} {nm[:18]:<18}  '
                f'el {elev_ft(af):>5} ft   {freq(af):<8}'
            )
            draw_text(c, x(0), y_top(yy), row, font=MONO, size=8, color=INK)
            yy += 3.8
            rwy = runway_text(af)
            draw_text(c, x(12), y_top(yy), rwy, font=MONO, size=7.5, color=MUTED)
            yy += 4.5

def render_freqs(c, x, y_top, spec):
    title = spec['title']
    rows = spec['rows']
    subtitle = spec.get('subtitle', '')

    draw_text(c, x(0), y_top(8), title, font=SERIF_BOLD, size=13, color=NAVY)
    if subtitle:
        draw_text(c, x(0), y_top(13.5), subtitle, font=SERIF, size=8, color=MUTED)

    c.setStrokeColor(NAVY); c.setLineWidth(0.5)
    c.line(x(0) * mm, y_top(16) * mm, (x(0) + 138.5) * mm, y_top(16) * mm)

    yy = 20
    for label, freq_val in rows:
        if yy > (A5_H / mm) - 12:
            break
        label = strip(label)
        freq_val = strip(freq_val)
        draw_text(c, x(0), y_top(yy), label, font=SERIF, size=8.2, color=INK)
        draw_text(c, x(138.5), y_top(yy), freq_val, font=MONO_BOLD, size=8.5, color=ACCENT, align='r')
        yy += 4.6


def render_fields(c, x, y_top, spec):
    title = spec['title']
    fields = spec['fields']

    draw_text(c, x(0), y_top(8), title, font=SERIF_BOLD, size=12, color=NAVY)
    draw_text(c, x(138.5), y_top(8), spec.get('subtitle', ''),
              font=SERIF, size=8, color=MUTED, align='r')
    c.setStrokeColor(NAVY); c.setLineWidth(0.4)
    c.line(x(0) * mm, y_top(11) * mm, (x(0) + 138.5) * mm, y_top(11) * mm)

    # Column headers
    yh = 15
    draw_text(c, x(0),    y_top(yh), 'ICAO',  font=MONO_BOLD, size=6.8, color=MUTED)
    draw_text(c, x(14),   y_top(yh), 'NAME',  font=MONO_BOLD, size=6.8, color=MUTED)
    draw_text(c, x(70),   y_top(yh), 'ELEV',  font=MONO_BOLD, size=6.8, color=MUTED, align='r')
    draw_text(c, x(71),   y_top(yh), 'FREQ',  font=MONO_BOLD, size=6.8, color=MUTED)
    draw_text(c, x(89),   y_top(yh), 'RWYS',  font=MONO_BOLD, size=6.8, color=MUTED)
    draw_text(c, x(138),  y_top(yh), 'FLG',   font=MONO_BOLD, size=6.8, color=MUTED, align='r')
    c.setStrokeColor(RULE); c.setLineWidth(0.25)
    c.line(x(0) * mm, y_top(yh + 1.5) * mm, (x(0) + 138.5) * mm, y_top(yh + 1.5) * mm)

    yy = 19
    band = False
    for af in fields:
        if yy > (A5_H / mm) - 10:
            break
        # Light alternating band for readability
        if band:
            c.setFillColor(BAND)
            c.rect(x(-1) * mm, (y_top(yy) - 0.8) * mm, 140.5 * mm, ROW_HEIGHT, fill=1, stroke=0)
        band = not band

        ic = icao_short(af)
        nm = name_short(af)
        # Truncate name to fit
        max_chars_name = 30
        if len(nm) > max_chars_name:
            nm = nm[:max_chars_name - 1] + '…'

        draw_text(c, x(0),   y_top(yy), ic or '—',     font=MONO_BOLD, size=ROW_FONT, color=NAVY)
        draw_text(c, x(14),  y_top(yy), nm,            font=SERIF,     size=ROW_FONT + 0.3, color=INK)
        draw_text(c, x(70),  y_top(yy), elev_ft(af),   font=MONO,      size=ROW_FONT, color=INK,  align='r')
        draw_text(c, x(71),  y_top(yy), freq(af),      font=MONO_BOLD, size=ROW_FONT, color=ACCENT)
        draw_text(c, x(89),  y_top(yy), runway_text(af), font=MONO,    size=ROW_FONT, color=INK)
        draw_text(c, x(138), y_top(yy), flags(af),     font=MONO_BOLD, size=ROW_FONT, color=NAVY, align='r')
        yy += ROW_HEIGHT / mm


def render_notes(c, x, y_top, spec):
    draw_text(c, x(0), y_top(8), 'NOTES', font=SERIF_BOLD, size=13, color=NAVY)
    c.setStrokeColor(NAVY); c.setLineWidth(0.5)
    c.line(x(0) * mm, y_top(11) * mm, (x(0) + 138.5) * mm, y_top(11) * mm)

    # Faint ruled lines for hand notes
    c.setStrokeColor(RULE); c.setLineWidth(0.2)
    yy = 18
    while yy < (A5_H / mm) - 12:
        c.line(x(0) * mm, y_top(yy) * mm, (x(0) + 138.5) * mm, y_top(yy) * mm)
        yy += 6


# ── Build the page list ───────────────────────────────────────────────

def build_pages(data):
    afs = [a for a in data['airfields'] if useful(a)]

    by_group = {}
    for a in afs:
        by_group.setdefault(a['group'], []).append(a)
    for g in by_group:
        by_group[g].sort(key=priority)

    # Frequency tables from meta
    freq_tables = {t['name']: t for t in data['meta']['frequency_tables']}

    pages = []

    # Page 1: cover (pass full data so cover can pull HOME BASE entries)
    pages.append({'kind': 'cover', 'data': data})

    # Page 2: Cape Town freqs
    ct = freq_tables.get('CAPE TOWN AREA', {'rows': []})
    pages.append({
        'kind': 'freqs',
        'title': 'CAPE TOWN AREA',
        'subtitle': 'Tower, approach, ATIS, surrounding stations',
        'rows': ct['rows'],
    })

    # WC field pages — 25 per page
    wc = by_group.get('WESTERN CAPE', [])
    pages.extend(paginate_fields(wc, 'WESTERN CAPE', 25))

    # Eastern Cape & KZN freqs
    eckzn = freq_tables.get('EASTERN CAPE & KZN', {'rows': []})
    pages.append({
        'kind': 'freqs',
        'title': 'EASTERN CAPE / KZN AREA',
        'subtitle': 'Tower, approach, ATIS, surrounding stations',
        'rows': eckzn['rows'],
    })

    # EC field pages
    ec = by_group.get('EASTERN CAPE', [])
    pages.extend(paginate_fields(ec, 'EASTERN CAPE', 25))

    # KZN field pages
    kzn = by_group.get('KWAZULU-NATAL', [])
    pages.extend(paginate_fields(kzn, 'KWAZULU-NATAL', 25))

    # Pad to multiple of 4 for booklet imposition
    while len(pages) % 4 != 0:
        pages.append({'kind': 'notes'})

    # Assign page numbers
    for i, p in enumerate(pages, start=1):
        p['page_no'] = i
    return pages


def paginate_fields(fields, group_name, per_page):
    total_pages = (len(fields) + per_page - 1) // per_page
    out = []
    for pi in range(total_pages):
        chunk = fields[pi * per_page:(pi + 1) * per_page]
        out.append({
            'kind': 'fields',
            'title': group_name,
            'subtitle': f'page {pi + 1}/{total_pages}' if total_pages > 1 else '',
            'fields': chunk,
        })
    return out


# ── Output: sequential A5 PDF ─────────────────────────────────────────

def write_a5_sequential(pages, path):
    c = canvas.Canvas(path, pagesize=A5)
    for p in pages:
        draw_a5_page(c, 0, 0, p)
        c.showPage()
    c.save()


# ── Output: imposed A4 landscape booklet ──────────────────────────────

def saddle_stitch_order(n_pages):
    """Yield (front_left, front_right, back_left, back_right) for each
    sheet in printing order (outermost sheet first)."""
    assert n_pages % 4 == 0
    sheets = n_pages // 4
    for s in range(sheets):
        front_left = n_pages - 2 * s
        front_right = 2 * s + 1
        back_left = 2 * s + 2
        back_right = n_pages - 2 * s - 1
        yield front_left, front_right, back_left, back_right


def write_booklet(pages, path):
    c = canvas.Canvas(path, pagesize=landscape(A4))
    n = len(pages)
    pages_by_no = {p['page_no']: p for p in pages}
    half_w = A4_W / 2 / mm  # 148.5 mm

    for fl, fr, bl, br in saddle_stitch_order(n):
        # Front side: [fl | fr]
        draw_a5_page(c, 0, 0, pages_by_no[fl])
        draw_a5_page(c, half_w, 0, pages_by_no[fr])
        # Fold guide
        c.setStrokeColor(RULE); c.setDash(1, 2); c.setLineWidth(0.3)
        c.line(half_w * mm, 0, half_w * mm, A4_H)
        c.setDash()
        c.showPage()
        # Back side: [bl | br]
        draw_a5_page(c, 0, 0, pages_by_no[bl])
        draw_a5_page(c, half_w, 0, pages_by_no[br])
        c.setStrokeColor(RULE); c.setDash(1, 2); c.setLineWidth(0.3)
        c.line(half_w * mm, 0, half_w * mm, A4_H)
        c.setDash()
        c.showPage()

    c.save()


def main():
    data = json.load(open(DATA_FILE))
    pages = build_pages(data)
    print(f'Built {len(pages)} A5 pages '
          f'({len(pages) // 4} A4 sheets after imposition)')
    write_a5_sequential(pages, OUT_A5)
    write_booklet(pages, OUT_BOOKLET)
    print(f'Wrote:')
    print(f'  {OUT_A5}')
    print(f'  {OUT_BOOKLET}')


if __name__ == '__main__':
    main()
