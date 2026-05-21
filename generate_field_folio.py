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
HOME_TINT = HexColor('#fff5f5')   # soft accent wash for home base rows

# Page geometry ---------------------------------------------------------
A5_W, A5_H = A5                       # 148.5 × 210 mm portrait
A4_W, A4_H = landscape(A4)            # 297 × 210 mm

PAGE_MARGIN_X = 5 * mm
PAGE_MARGIN_TOP = 6 * mm
PAGE_MARGIN_BOTTOM = 6 * mm

# Row layout (within an A5 page) ----------------------------------------
ROW_HEIGHT = 3.8 * mm
ROW_FONT = 6.9
HEADER_FONT = 9
SECTION_FONT = 11
MAX_ROWS_PER_PAGE = 48

# Column x-offsets relative to A5 left margin (mm).
# Total content width = 148.5 - 2*5 = 138.5 mm.
# FREQ sits directly after NAME so the reader's eye carries from one to the other.
CX_ICAO = 0.0
CX_NAME = 12.5
CX_FREQ = 56.0
CX_ELEV_R = 81.0    # right-aligned
CX_RWY = 83.0
CX_FLG_R = 138.5    # right-aligned


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
    # Strip "(FAXX)" / "(ZA-xxxx)" anywhere — ICAO lives in its own column
    n = re.sub(r'\s*\([A-Z0-9-]{3,8}\)\s*', ' ', n)
    # Strip "(near X)" / "(at X)" parentheticals — context, not part of name
    n = re.sub(r'\s*\((?:near|at|by|outside)\s+[^)]+\)', '', n, flags=re.I)
    # Strip annotations after em-dash
    n = re.sub(r'\s*[—–]\s*.*$', '', n)
    # Strip "/ ex-..." parentheticals
    n = re.sub(r'\s*/\s*ex-.*$', '', n, flags=re.I)
    n = n.strip()
    # Strip noise words anywhere — loop until stable
    for _ in range(4):
        prev = n
        n = re.sub(
            r'\s+(AIRPORT|AIRFIELD|AIRSTRIP|INTERNATIONAL|'
            r'GAME RESERVE|WILDLIFE RESERVE|NATURE RESERVE|GAME LODGE|'
            r'PRIVATE GAME RESERVE)\b',
            ' ', n, flags=re.I,
        )
        n = re.sub(r'\s+', ' ', n).strip()
        if n == prev:
            break
    n = strip(n)
    return (n + suffix).strip()

_REAL_ICAO_RE = re.compile(r'^FA[A-Z0-9]{2,3}$')

def icao_short(af) -> str:
    """Return a real ICAO code (FA-series). Placeholder codes (ZA-…, FA0526, …)
    are dropped — those mean 'no real ICAO assigned'."""
    ic = (af.get('icao') or '').strip().upper()
    return ic if _REAL_ICAO_RE.match(ic) else ''

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

def _circuit_tag(s: str) -> str:
    """'Right' / 'Left' / 'Left ?' → 'RH' / 'LH' / ''."""
    s = strip(s or '').lower()
    if 'right' in s:
        return 'RH'
    if 'left' in s:
        return 'LH'
    return ''


def runway_text(af, with_circuit: bool = False) -> str:
    data = (af.get('runways') or {}).get('data') or []
    seen = {}
    order = []
    circuits = {}  # key → circuit string like "02-RH 20-LH"
    pair_ends = {}  # pair-key → {end_label: circuit_tag}
    for r in data:
        rwy_raw = strip(r.get('rwy') or '').upper().replace(' ', '')
        if not rwy_raw or rwy_raw == '?':
            continue
        if not _RWY_NAME_RE.match(rwy_raw):
            continue
        key = _pair_key(rwy_raw)
        # Track per-end circuit even when pair already seen
        c = _circuit_tag(r.get('strength') or '')
        if c:
            # rwy_raw may be the single end (e.g. "02") or pair ("02/20")
            ends = rwy_raw.split('/') if '/' in rwy_raw else [rwy_raw]
            for e in ends:
                e = e.rstrip('LRC')
                pair_ends.setdefault(key, {})[e] = c
        if key in seen:
            continue
        sc = surface_code(r.get('surface') or '')
        L = length_m(r.get('length') or '')
        W = width_m(r.get('width') or '')
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
        order.append((key, seg))
    if not order:
        return '—'
    # Optionally suffix circuit info (home-base rows).
    rendered = []
    for key, seg in order:
        if with_circuit and key in pair_ends:
            tags = ' '.join(f'{e}{c}' for e, c in sorted(pair_ends[key].items()))
            if tags:
                seg = f'{seg} {tags}'
        rendered.append(seg)
    # Truncate by character budget so we don't crash into the FLG column.
    MAX = 44 if with_circuit else 38
    out = []
    for seg in rendered:
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

def is_closed(af) -> bool:
    name = af.get('name', '') or ''
    return bool(re.search(r'CLOSED|PERMANENTLY\s+CLOSED|⛔', name, re.I))


def useful(af) -> bool:
    """Keep airfields a pilot might reasonably need to know about: real data,
    OR a real ICAO code (even with sparse data — military bases, sleepy strips).
    Skip explicitly closed fields and entries flagged as status-uncertain."""
    if is_closed(af):
        return False
    name = af.get('name', '') or ''
    if re.search(r'STATUS\s+UNCERTAIN', name, re.I):
        return False
    rwys = (af.get('runways') or {}).get('data') or []
    has_freq = bool(strip((af.get('communications') or {}).get('primary_freq') or ''))
    has_real_rwy = any(
        length_m(r.get('length') or '') or surface_code(r.get('surface') or '') in ('T', 'G', 'V', 'C', 'D')
        for r in rwys
    )
    if has_freq or has_real_rwy:
        return True
    # Real FA-series ICAO → keep even without runway/freq data (the existence
    # alone is useful: military bases, controlled aerodromes with no public
    # numbers, currently-dormant strips with assigned codes).
    return bool(icao_short(af))

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

_COORD_DEC_RE = re.compile(r'^(-?\d+\.\d+)$')


def coord_brief(af) -> str:
    """Return 'S33°45.7' E18°32.9'' or '' if no usable coords."""
    coords = (af.get('basic_info') or {}).get('coordinates') or {}
    lat = coords.get('lat')
    lon = coords.get('lon')
    if lat is None or lon is None:
        return ''
    try:
        lat = float(lat); lon = float(lon)
    except (TypeError, ValueError):
        return ''
    def dm(v, pos, neg):
        h = pos if v >= 0 else neg
        v = abs(v)
        d = int(v)
        m = (v - d) * 60
        return f'{h}{d:02d}°{m:04.1f}′'
    return f'{dm(lat, "N", "S")} {dm(lon, "E", "W")}'


def fuel_brief(af) -> str:
    """Compact fuel summary: '100LL+MoGas · MSFA +27 21 569 3726' (best-effort)."""
    raw = strip(((af.get('operations') or {}).get('fuel')) or '')
    if not raw:
        return ''
    grades = []
    if re.search(r'100LL|AVGAS', raw, re.I):
        grades.append('100LL')
    if re.search(r'95\s*ULP|MoGas|UL91|UL94', raw, re.I):
        grades.append('MoGas')
    if re.search(r'Jet\s*A', raw, re.I):
        grades.append('JetA')
    phone = ''
    m = re.search(r'(\+?27[\s\d]{8,})', raw)
    if m:
        phone = re.sub(r'\s+', ' ', m.group(1)).strip()
    parts = []
    if grades:
        parts.append('+'.join(grades))
    elif raw:
        parts.append(raw[:30])
    if phone:
        parts.append(phone)
    return ' · '.join(parts)


def _draw_home_block(c, x, y_top, yy, label, af):
    """Render a multi-line HOME BASE entry on the cover. Returns the new yy."""
    nm = name_short(af) or '?'
    ic = icao_short(af) or '★'
    line1 = f'{label:<5} {ic:<5} {nm}'
    draw_text(c, x(0), y_top(yy), line1, font=MONO_BOLD, size=8.5, color=ACCENT)
    draw_text(c, x(75), y_top(yy), freq(af), font=MONO_BOLD, size=8.5, color=ACCENT)
    draw_text(c, x(95), y_top(yy), f'el {elev_ft(af)} ft', font=MONO, size=8, color=INK)
    yy += 4.0
    rwy = runway_text(af, with_circuit=True)
    draw_text(c, x(11), y_top(yy), rwy, font=MONO, size=7.5, color=INK)
    yy += 3.8
    cb = coord_brief(af)
    fb = fuel_brief(af)
    if cb:
        draw_text(c, x(11), y_top(yy), cb, font=MONO, size=7.2, color=MUTED)
    if fb:
        draw_text(c, x(70), y_top(yy), fb, font=MONO, size=7.2, color=MUTED)
    yy += 4.0
    return yy


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
        ('125.500',  'Cape Town Information (FIS)'),
        ('126.300',  'Johannesburg Information (FIS)'),
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

    # Row format — mirror the new column order (FREQ adjacent to NAME).
    draw_text(c, x(0), y_top(yy), 'ROW FORMAT', font=SERIF_BOLD, size=9.5, color=NAVY)
    yy += 5.5
    draw_text(c, x(0), y_top(yy), 'ICAO  NAME           FREQ    ELEV  RWYS                  FLAGS',
              font=MONO_BOLD, size=7.2, color=MUTED)
    yy += 4
    draw_text(c, x(0), y_top(yy), 'FAVG  VIRGINIA       120.6     20  05/23 T1067x18        LFT',
              font=MONO, size=7.2, color=INK)
    yy += 4
    draw_text(c, x(0), y_top(yy), 'Length × width in metres. ELEV in ft AMSL.',
              font=SERIF, size=7.5, color=MUTED)
    yy += 4
    draw_text(c, x(0), y_top(yy), 'Home base rows marked ★ with inline circuit direction.',
              font=SERIF, size=7.5, color=MUTED)

    # ── HOME BASE block — full operating detail ─────────────────
    yy += 7
    draw_text(c, x(0), y_top(yy), 'HOME BASE', font=SERIF_BOLD, size=9.5, color=ACCENT)
    yy += 6
    homes = []
    if data:
        homes = [
            ('Now',  spec.get('home_now')
                     or find_field(data, lambda a: 'MORNINGSTAR' in a.get('name','').upper())),
            ('Next', spec.get('home_next')
                     or find_field(data, lambda a: a.get('icao') == 'FAVG')),
        ]
    for label, af in homes:
        if not af:
            continue
        yy = _draw_home_block(c, x, y_top, yy, label, af)
        yy += 2

_ICAO_IN_LABEL_RE = re.compile(r'\(([A-Z]{4})\)')
_SERVICE_TYPE_RE = re.compile(
    r'\b(TWR|TOWER|APP|APPROACH|GND|GROUND|ATIS|ATIR|CLR|CLEARANCE|'
    r'AFIS|FIS|INFORMATION|RADAR|DIRECTOR|APRON|MIL)\b',
    re.I,
)


def _service_flag(label: str) -> str:
    """Return a 1–3 char service tag for the FLG column: TWR/APP/ATI/etc."""
    m = _SERVICE_TYPE_RE.search(label or '')
    if not m:
        return ''
    raw = m.group(1).upper()
    return {
        'TWR': 'T', 'TOWER': 'T',
        'APP': 'A', 'APPROACH': 'A',
        'GND': 'G', 'GROUND': 'G',
        'ATIS': 'I', 'ATIR': 'I',
        'CLR': 'C', 'CLEARANCE': 'C',
        'AFIS': 'F', 'FIS': 'F', 'INFORMATION': 'F',
        'RADAR': 'R', 'DIRECTOR': 'R',
        'APRON': 'P',
        'MIL': 'M',
    }.get(raw, '')


def render_freqs(c, x, y_top, spec):
    """Render a frequency table in the SAME field-table layout as render_fields
    so the booklet has one visual rhythm across all pages."""
    title = spec['title']
    rows = spec['rows']
    subtitle = spec.get('subtitle', '')

    draw_text(c, x(0), y_top(8), title, font=SERIF_BOLD, size=12, color=NAVY)
    draw_text(c, x(138.5), y_top(8), subtitle,
              font=SERIF, size=8, color=MUTED, align='r')
    c.setStrokeColor(NAVY); c.setLineWidth(0.4)
    c.line(x(0) * mm, y_top(11) * mm, (x(0) + 138.5) * mm, y_top(11) * mm)

    # Column headers — same column origins as render_fields. ICAO column shows
    # the parent airport code (if any); NAME shows the service label; FREQ is
    # the freq; ELEV/RWYS reused for type & notes; FLG for service tag.
    yh = 15
    draw_text(c, x(CX_ICAO),   y_top(yh), 'ICAO',  font=MONO_BOLD, size=6.8, color=MUTED)
    draw_text(c, x(CX_NAME),   y_top(yh), 'SERVICE', font=MONO_BOLD, size=6.8, color=MUTED)
    draw_text(c, x(CX_FREQ),   y_top(yh), 'FREQ',  font=MONO_BOLD, size=6.8, color=MUTED)
    draw_text(c, x(CX_RWY),    y_top(yh), 'NOTES', font=MONO_BOLD, size=6.8, color=MUTED)
    draw_text(c, x(CX_FLG_R),  y_top(yh), 'TYP',   font=MONO_BOLD, size=6.8, color=MUTED, align='r')
    c.setStrokeColor(RULE); c.setLineWidth(0.25)
    c.line(x(0) * mm, y_top(yh + 1.5) * mm, (x(0) + 138.5) * mm, y_top(yh + 1.5) * mm)

    yy = 19
    band = False
    for raw_label, raw_freq in rows:
        if yy > (A5_H / mm) - 8:
            break
        label = strip(raw_label or '')
        freq_val = strip(raw_freq or '')

        # Highlight FIS rows with the home tint so they pop.
        is_fis = bool(re.search(r'\bFIS|INFORMATION\b', label, re.I))
        if is_fis:
            c.setFillColor(HOME_TINT)
            c.rect(x(-1) * mm, (y_top(yy) - 0.8) * mm, 140.5 * mm, ROW_HEIGHT, fill=1, stroke=0)
        elif band:
            c.setFillColor(BAND)
            c.rect(x(-1) * mm, (y_top(yy) - 0.8) * mm, 140.5 * mm, ROW_HEIGHT, fill=1, stroke=0)
        band = not band

        # Pull ICAO out of "Stellenbosch (FASH)" if present.
        icao = ''
        m = _ICAO_IN_LABEL_RE.search(label)
        if m:
            icao = m.group(1)
            label = _ICAO_IN_LABEL_RE.sub('', label).strip()

        # Drop the service-type word at end of label so NAME is clean.
        notes = ''
        sm = _SERVICE_TYPE_RE.search(label)
        if sm:
            # Keep service in label for clarity but suppress from NOTES.
            notes = ''

        if len(label) > 28:
            label = label[:27] + '…'

        label_color = ACCENT if is_fis else INK
        label_font = SERIF_BOLD if is_fis else SERIF

        draw_text(c, x(CX_ICAO),   y_top(yy), icao or '—',
                  font=MONO_BOLD, size=ROW_FONT, color=NAVY)
        draw_text(c, x(CX_NAME),   y_top(yy), label,
                  font=label_font, size=ROW_FONT + 0.3, color=label_color)
        draw_text(c, x(CX_FREQ),   y_top(yy), freq_val,
                  font=MONO_BOLD, size=ROW_FONT, color=ACCENT)
        draw_text(c, x(CX_RWY),    y_top(yy), notes,
                  font=MONO, size=ROW_FONT, color=MUTED)
        draw_text(c, x(CX_FLG_R),  y_top(yy), _service_flag(raw_label),
                  font=MONO_BOLD, size=ROW_FONT, color=NAVY, align='r')
        yy += ROW_HEIGHT / mm


def render_fields(c, x, y_top, spec):
    title = spec['title']
    fields = spec['fields']

    draw_text(c, x(0), y_top(8), title, font=SERIF_BOLD, size=12, color=NAVY)
    draw_text(c, x(138.5), y_top(8), spec.get('subtitle', ''),
              font=SERIF, size=8, color=MUTED, align='r')
    c.setStrokeColor(NAVY); c.setLineWidth(0.4)
    c.line(x(0) * mm, y_top(11) * mm, (x(0) + 138.5) * mm, y_top(11) * mm)

    # Column headers — FREQ sits right after NAME so the eye carries across.
    yh = 15
    draw_text(c, x(CX_ICAO),   y_top(yh), 'ICAO', font=MONO_BOLD, size=6.8, color=MUTED)
    draw_text(c, x(CX_NAME),   y_top(yh), 'NAME', font=MONO_BOLD, size=6.8, color=MUTED)
    draw_text(c, x(CX_FREQ),   y_top(yh), 'FREQ', font=MONO_BOLD, size=6.8, color=MUTED)
    draw_text(c, x(CX_ELEV_R), y_top(yh), 'ELEV', font=MONO_BOLD, size=6.8, color=MUTED, align='r')
    draw_text(c, x(CX_RWY),    y_top(yh), 'RWYS', font=MONO_BOLD, size=6.8, color=MUTED)
    draw_text(c, x(CX_FLG_R),  y_top(yh), 'FLG',  font=MONO_BOLD, size=6.8, color=MUTED, align='r')
    c.setStrokeColor(RULE); c.setLineWidth(0.25)
    c.line(x(0) * mm, y_top(yh + 1.5) * mm, (x(0) + 138.5) * mm, y_top(yh + 1.5) * mm)

    yy = 19
    band = False
    for af in fields:
        if yy > (A5_H / mm) - 10:
            break
        is_home = bool(af.get('_home'))

        # Row background: accent wash for home base; alternating band for others.
        if is_home:
            c.setFillColor(HOME_TINT)
            c.rect(x(-1) * mm, (y_top(yy) - 0.8) * mm, 140.5 * mm, ROW_HEIGHT, fill=1, stroke=0)
        elif band:
            c.setFillColor(BAND)
            c.rect(x(-1) * mm, (y_top(yy) - 0.8) * mm, 140.5 * mm, ROW_HEIGHT, fill=1, stroke=0)
        band = not band

        ic = icao_short(af)
        nm = name_short(af)
        # Truncate name to fit NAME column (~43 mm; Helvetica avg ~1.65 mm / char at 7.5pt).
        # For "/" alternative-name pairs, drop the second half before hard truncation.
        if len(nm) > 25 and ' / ' in nm:
            nm = nm.split(' / ', 1)[0]
        max_chars_name = 25
        if len(nm) > max_chars_name:
            nm = nm[:max_chars_name - 1] + '…'

        # Home rows: ★ for ICAO, bold accent name, circuit info inline.
        icao_glyph = ic if ic else ('★' if is_home else '—')
        icao_color = ACCENT if is_home else NAVY
        name_font = SERIF_BOLD if is_home else SERIF

        draw_text(c, x(CX_ICAO),   y_top(yy), icao_glyph,
                  font=MONO_BOLD, size=ROW_FONT, color=icao_color)
        draw_text(c, x(CX_NAME),   y_top(yy), nm,
                  font=name_font, size=ROW_FONT + 0.3, color=INK)
        draw_text(c, x(CX_FREQ),   y_top(yy), freq(af),
                  font=MONO_BOLD, size=ROW_FONT, color=ACCENT)
        draw_text(c, x(CX_ELEV_R), y_top(yy), elev_ft(af),
                  font=MONO, size=ROW_FONT, color=INK, align='r')
        draw_text(c, x(CX_RWY),    y_top(yy), runway_text(af, with_circuit=is_home),
                  font=MONO, size=ROW_FONT, color=INK)
        draw_text(c, x(CX_FLG_R),  y_top(yy), flags(af),
                  font=MONO_BOLD, size=ROW_FONT, color=NAVY, align='r')
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

def _pin_home(group, name_match, icao_match=None):
    """Move the home-base airfield to position 0 and mark it with `_home`."""
    for i, a in enumerate(group):
        nm = (a.get('name') or '').upper()
        ic = (a.get('icao') or '').upper()
        if name_match.upper() in nm or (icao_match and ic == icao_match.upper()):
            a['_home'] = True
            group.insert(0, group.pop(i))
            return a
    return None


def build_pages(data):
    afs = [a for a in data['airfields'] if useful(a)]

    by_group = {}
    for a in afs:
        by_group.setdefault(a['group'], []).append(a)
    for g in by_group:
        by_group[g].sort(key=priority)

    # Pin home-base airfields to the top of their regions.
    wc = by_group.get('WESTERN CAPE', [])
    ec = by_group.get('EASTERN CAPE', [])
    kzn = by_group.get('KWAZULU-NATAL', [])
    fs = by_group.get('FREE STATE', [])
    nc = by_group.get('NORTHERN CAPE', [])
    gp = by_group.get('GAUTENG', [])
    home_now = _pin_home(wc, 'MORNINGSTAR')
    home_next = _pin_home(kzn, 'VIRGINIA', icao_match='FAVG')

    # Frequency tables from meta — patch in national FIS rows up top so they
    # appear in every region.
    freq_tables = {t['name']: dict(t) for t in data['meta']['frequency_tables']}

    NATIONAL_FIS = [
        ['Cape Town FIS',               '125.500'],
        ['Joburg FIS',                  '126.300'],
        ['Emergency / Guard',           '121.500'],
        ['GAP common (uncontrolled)',   '124.800'],
        ['Air-to-air',                  '123.450'],
    ]
    def _fkey(v):
        try:
            return f'{float(strip(v) or 0):.3f}'
        except (ValueError, TypeError):
            return strip(v or '')

    for tname, t in freq_tables.items():
        # Dedupe by canonical frequency value, then prepend missing FIS rows.
        # Also drop existing rows whose freq matches one we're prepending —
        # the FIS labels take priority over generic "Information" entries.
        prepend_keys = {_fkey(r[1]) for r in NATIONAL_FIS}
        kept = [r for r in t.get('rows', []) if _fkey(r[1]) not in prepend_keys]
        t['rows'] = list(NATIONAL_FIS) + kept

    pages = []

    # Page 1: cover (cover pulls home-base detail from data)
    pages.append({'kind': 'cover', 'data': data,
                  'home_now': home_now, 'home_next': home_next})

    def freq_page(table_key, title, subtitle='Tower, approach, ATIS, FIS, surrounding stations'):
        return {
            'kind': 'freqs',
            'title': title,
            'subtitle': subtitle,
            'rows': freq_tables.get(table_key, {'rows': []}).get('rows', []),
        }

    pages.append(freq_page('CAPE TOWN AREA', 'CAPE TOWN AREA'))
    pages.extend(paginate_fields(wc, 'WESTERN CAPE', MAX_ROWS_PER_PAGE))

    pages.append(freq_page('EASTERN CAPE & KZN', 'EASTERN CAPE / KZN AREA'))
    pages.extend(paginate_fields(ec, 'EASTERN CAPE', MAX_ROWS_PER_PAGE))
    pages.extend(paginate_fields(kzn, 'KWAZULU-NATAL', MAX_ROWS_PER_PAGE))

    # Inland coverage — useful for cross-country / ferry runs.
    pages.append(freq_page('FREE STATE', 'FREE STATE AREA'))
    pages.extend(paginate_fields(fs, 'FREE STATE', MAX_ROWS_PER_PAGE))
    pages.extend(paginate_fields(nc, 'NORTHERN CAPE', MAX_ROWS_PER_PAGE))

    pages.append(freq_page('GAUTENG & INLAND', 'GAUTENG / INLAND AREA'))
    pages.extend(paginate_fields(gp, 'GAUTENG', MAX_ROWS_PER_PAGE))

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
