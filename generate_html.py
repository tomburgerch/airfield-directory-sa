#!/usr/bin/env python3
"""
Generate a searchable HTML version of the South African Airfield Directory.
"""

import os
import re
import base64
from html import escape

from parse_markdown import parse_airfields
from pdf_styles import EMOJI_MAP

MD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'AIRFIELD_DIRECTORY.md')
OUTPUT_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Airfield_Directory.html')
DIAGRAMS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diagrams')


def clean_html(text):
    """Clean emoji for HTML display — keep text readable."""
    for emoji, replacement in EMOJI_MAP.items():
        text = text.replace(emoji, replacement)
    return text.strip()


def find_diagram_path(airfield):
    """Find diagram image for an airfield."""
    from diagrams_util import find_diagram
    return find_diagram(airfield)


def embed_image(path, max_width=500):
    """Return an <img> tag with base64-embedded image, or external reference."""
    if not path or not os.path.exists(path):
        return ''
    ext = os.path.splitext(path)[1].lower()
    mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg'}.get(ext.lstrip('.'), 'image/png')
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('ascii')
    return f'<img src="data:{mime};base64,{data}" style="max-width:{max_width}px; height:auto;" alt="Aerodrome diagram">'


CSS = """
:root {
    --navy: #1a365d;
    --blue: #2b6cb0;
    --red: #c53030;
    --dark-red: #9b2c2c;
    --dark-gray: #2d3748;
    --light-gray: #f7fafc;
    --border: #e2e8f0;
    --text: #2d3748;
    --text-muted: #718096;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    color: var(--text);
    background: #f0f4f8;
    line-height: 1.5;
}
.container { max-width: 900px; margin: 0 auto; padding: 16px; }

/* ── Header / Nav ── */
.site-header {
    background: var(--navy);
    color: white;
    padding: 20px 0;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.site-header .container { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.site-header h1 { font-size: 18px; flex-shrink: 0; }
.site-header h1 span { font-weight: 400; font-size: 13px; opacity: 0.8; }
#search-box {
    flex: 1; min-width: 200px;
    padding: 8px 12px; border: none; border-radius: 6px;
    font-size: 14px; background: rgba(255,255,255,0.15);
    color: white;
}
#search-box::placeholder { color: rgba(255,255,255,0.6); }
#search-box:focus { outline: none; background: rgba(255,255,255,0.25); }

/* ── Disclaimer ── */
.disclaimer {
    background: var(--red);
    color: white;
    padding: 14px 18px;
    border-radius: 8px;
    margin: 16px 0;
    font-size: 13px;
    line-height: 1.6;
}
.disclaimer strong { font-size: 14px; }
.disclaimer p { margin-top: 6px; }

/* ── TOC ── */
.toc {
    background: white;
    border-radius: 8px;
    padding: 16px;
    margin: 16px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.toc h2 { font-size: 16px; color: var(--navy); margin-bottom: 8px; cursor: pointer; }
.toc-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 4px 16px;
}
.toc-item a {
    color: var(--navy);
    text-decoration: none;
    font-size: 13px;
    display: block;
    padding: 3px 6px;
    border-radius: 4px;
}
.toc-item a:hover { background: var(--light-gray); }
.toc-item .code { color: var(--text-muted); font-size: 11px; margin-left: 4px; }
.toc-group { font-weight: 700; font-size: 12px; color: var(--blue); margin-top: 8px; grid-column: 1 / -1; }

/* ── Airfield card ── */
.airfield-card {
    background: white;
    border-radius: 8px;
    margin: 12px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    overflow: hidden;
}
.airfield-header {
    background: var(--navy);
    color: white;
    padding: 10px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.airfield-header.closed { background: var(--dark-red); }
.airfield-header.military { background: var(--dark-gray); }
.airfield-header h3 { font-size: 15px; margin: 0; }
.airfield-header .num { font-size: 12px; opacity: 0.8; }
.airfield-code {
    font-size: 12px; color: var(--text-muted);
    padding: 4px 14px;
    border-bottom: 1px solid var(--border);
}
.closed-banner {
    background: var(--red);
    color: white;
    text-align: center;
    padding: 6px;
    font-weight: 700;
    font-size: 13px;
}
.airfield-body { padding: 12px 14px; }

/* ── Info grid ── */
.info-grid {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 2px 8px;
    font-size: 13px;
    margin-bottom: 10px;
}
.info-grid .label { font-weight: 600; color: var(--text-muted); }
.info-grid .value { }
.info-grid .value.freq { color: var(--blue); font-weight: 700; }
.info-grid .value.elev { font-weight: 700; }

/* ── Tables ── */
.section-title {
    font-size: 13px; font-weight: 700; color: var(--blue);
    margin: 10px 0 4px 0; text-transform: uppercase;
}
table.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-bottom: 8px;
}
table.data-table th {
    background: var(--blue);
    color: white;
    padding: 5px 8px;
    text-align: center;
    font-size: 11px;
}
table.data-table td {
    padding: 4px 8px;
    border-bottom: 1px solid var(--border);
    text-align: center;
}
table.data-table tr:nth-child(even) { background: var(--light-gray); }
table.freq-table td:last-child { color: var(--blue); font-weight: 700; }

/* ── Diagram ── */
.diagram-container {
    text-align: center;
    margin: 10px 0;
}
.diagram-container img {
    max-width: 100%;
    height: auto;
    border: 1px solid var(--border);
    border-radius: 4px;
}
.diagram-caption {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
}

/* ── Warnings / notes ── */
.warning {
    color: var(--red);
    font-weight: 700;
    font-size: 13px;
    margin: 3px 0;
}
.note {
    font-size: 13px;
    color: var(--text);
    margin: 2px 0;
    padding-left: 12px;
}
.contact {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 6px;
    border-top: 1px solid var(--border);
    padding-top: 6px;
}

/* ── Back to top ── */
.back-to-top {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: var(--navy);
    color: white;
    border: none;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    font-size: 18px;
    cursor: pointer;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    display: none;
}
.group-divider {
    font-size: 14px;
    font-weight: 700;
    color: var(--navy);
    text-align: center;
    margin: 20px 0 8px 0;
    padding: 6px;
    background: var(--light-gray);
    border-radius: 6px;
}

/* ── Responsive ── */
@media (max-width: 600px) {
    .info-grid { grid-template-columns: 100px 1fr; font-size: 12px; }
    .site-header h1 { font-size: 15px; }
    .toc-grid { grid-template-columns: 1fr; }
}
@media print {
    .site-header { position: static; }
    .airfield-card { page-break-inside: avoid; }
    .back-to-top { display: none !important; }
    #search-box { display: none; }
}
"""

JAVASCRIPT = """
document.addEventListener('DOMContentLoaded', function() {
    const searchBox = document.getElementById('search-box');
    const cards = document.querySelectorAll('.airfield-card');
    const groups = document.querySelectorAll('.group-divider');
    const tocItems = document.querySelectorAll('.toc-item');
    const backBtn = document.querySelector('.back-to-top');

    searchBox.addEventListener('input', function() {
        const q = this.value.toLowerCase().trim();
        cards.forEach(card => {
            const text = card.dataset.search || card.textContent.toLowerCase();
            card.style.display = text.includes(q) ? '' : 'none';
        });
        groups.forEach(g => {
            if (q) g.style.display = 'none';
            else g.style.display = '';
        });
        tocItems.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(q) ? '' : 'none';
        });
    });

    window.addEventListener('scroll', function() {
        backBtn.style.display = window.scrollY > 400 ? 'block' : 'none';
    });
    backBtn.addEventListener('click', function() {
        window.scrollTo({top: 0, behavior: 'smooth'});
    });
});
"""


def build_airfield_card(airfield, embed_diagrams=False):
    """Build HTML for a single airfield card."""
    f = airfield['fields']
    name = clean_html(airfield['name'])
    is_closed = '[X]' in name or 'CLOSED' in name.upper()
    is_military = 'Military' in f.get('Access', '') or 'MIL' in clean_html(f.get('Access', '')).upper()

    code = f.get('ICAO', f.get('ICAO / Code', f.get('Code', '')))
    code_clean = clean_html(code)
    access = clean_html(f.get('Access', ''))

    header_class = 'closed' if is_closed else ('military' if is_military else '')
    search_text = f"{name} {code_clean} {access}".lower()

    html = f'<div class="airfield-card" id="af-{airfield["number"]}" data-search="{escape(search_text)}">\n'
    html += f'  <div class="airfield-header {header_class}">\n'
    html += f'    <h3>{escape(name)}</h3>\n'
    html += f'    <span class="num">#{airfield["number"]}</span>\n'
    html += f'  </div>\n'

    if code_clean or access:
        parts = [p for p in [code_clean, access] if p]
        html += f'  <div class="airfield-code">{escape(" | ".join(parts))}</div>\n'

    if is_closed:
        html += '  <div class="closed-banner">CLOSED - DO NOT PLAN OPERATIONS</div>\n'

    html += '  <div class="airfield-body">\n'

    # Info grid
    info_fields = [
        ('Coordinates', 'Coordinates', ''),
        ('Elevation', 'Elevation', 'elev'),
        ('Frequency', 'Frequencies', 'freq'),
        ('Joining Alt', 'Joining Alt', ''),
        ('Circuit Alt', 'Circuit Alt', ''),
        ('Night Ops', 'Night Ops', ''),
        ('Fuel', 'Fuel', ''),
        ('Hours', 'Hours', ''),
    ]
    grid_items = []
    for label, key, cls in info_fields:
        val = clean_html(f.get(key, f.get(label, '')))
        if not val and key == 'Frequencies':
            val = clean_html(f.get('Frequency', ''))
        if not val and key == 'Circuit Alt':
            val = clean_html(f.get('Circuit', f.get('Pattern Alt', '')))
        if val:
            cls_attr = f' class="value {cls}"' if cls else ' class="value"'
            grid_items.append(f'    <div class="label">{escape(label)}</div><div{cls_attr}>{escape(val)}</div>\n')

    if grid_items:
        html += '    <div class="info-grid">\n' + ''.join(grid_items) + '    </div>\n'

    # Frequencies table
    if airfield['frequencies_table']:
        html += '    <div class="section-title">Frequencies</div>\n'
        html += '    <table class="data-table freq-table"><tr><th>Service</th><th>Frequency</th></tr>\n'
        for row in airfield['frequencies_table'][:8]:
            html += f'      <tr><td>{escape(clean_html(row[0]))}</td><td>{escape(clean_html(row[1]))}</td></tr>\n'
        html += '    </table>\n'

    # Runways table
    if airfield['runways']:
        max_cols = max(len(r) for r in airfield['runways'])
        if max_cols >= 6:
            headers = ['RWY', 'Length', 'Width', 'Surface', 'Str', 'Circuit']
        elif max_cols >= 5:
            headers = ['RWY', 'Length', 'Width', 'Surface', 'Circuit']
        else:
            headers = ['RWY', 'Surface']
        headers = headers[:max_cols]

        html += '    <div class="section-title">Runways</div>\n'
        html += '    <table class="data-table"><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr>\n'
        for row in airfield['runways']:
            cleaned = [clean_html(c) for c in row]
            while len(cleaned) < max_cols:
                cleaned.append('')
            html += '      <tr>' + ''.join(f'<td>{escape(c)}</td>' for c in cleaned[:max_cols]) + '</tr>\n'
        html += '    </table>\n'

    # Diagram
    diagram_path = find_diagram_path(airfield)
    if diagram_path and os.path.exists(diagram_path):
        if embed_diagrams:
            img_tag = embed_image(diagram_path, max_width=600)
        else:
            rel_path = os.path.relpath(diagram_path, os.path.dirname(OUTPUT_HTML))
            img_tag = f'<img src="{rel_path}" style="max-width:600px; height:auto;" alt="Aerodrome diagram">'
        if img_tag:
            html += f'    <div class="diagram-container">{img_tag}<div class="diagram-caption">Aerodrome diagram — verify currency against official AIP</div></div>\n'

    # Warnings
    for w in airfield['warnings'][:5]:
        html += f'    <div class="warning">[!] {escape(clean_html(w))}</div>\n'

    # Notes
    if airfield['notes']:
        html += '    <div class="section-title">Notes</div>\n'
        for note in airfield['notes'][:8]:
            html += f'    <div class="note">- {escape(clean_html(note))}</div>\n'

    # Contact
    if airfield['contact']:
        html += f'    <div class="contact"><strong>Contact:</strong> {escape(clean_html(airfield["contact"]))}</div>\n'

    html += '  </div>\n</div>\n'
    return html


def generate_html(airfields, output_path, embed_diagrams=False):
    """Generate a complete searchable HTML file."""
    html = '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
    html += '<meta charset="UTF-8">\n'
    html += '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    html += '<title>South African Airfield Directory</title>\n'
    html += f'<style>{CSS}</style>\n'
    html += '</head>\n<body>\n'

    # Header
    html += '<header class="site-header">\n<div class="container">\n'
    html += '<h1>SA Airfield Directory <span>VFR Reference</span></h1>\n'
    html += '<input type="text" id="search-box" placeholder="Search airfields, codes, frequencies...">\n'
    html += '</div>\n</header>\n'
    html += '<div class="container">\n'

    # Disclaimer
    html += '<div class="disclaimer">\n'
    html += '<strong>IMPORTANT DISCLAIMER</strong>\n'
    html += '<p>This directory is a <strong>supplementary reference only</strong> and does '
    html += '<strong>NOT replace</strong> official aviation publications. '
    html += 'Pilots must always consult the current <strong>SACAA AIP</strong>, active '
    html += '<strong>NOTAMs</strong>, and official aerodrome charts before flight. '
    html += 'Contact airfield operators to verify access, fuel, hours, and runway status.</p>\n'
    html += '<p>Data marked (?) is unverified. No warranty is given for accuracy or completeness. '
    html += 'Use entirely at your own risk.</p>\n'
    html += '</div>\n'

    # TOC
    html += '<div class="toc">\n<h2>Airfield Index</h2>\n<div class="toc-grid">\n'
    current_group = ''
    for af in airfields:
        group = af.get('group', '')
        if group and group != current_group:
            current_group = group
            html += f'<div class="toc-group">{escape(clean_html(group))}</div>\n'
        name = clean_html(af['name'])
        code = af['fields'].get('ICAO', af['fields'].get('ICAO / Code', af['fields'].get('Code', '')))
        code_clean = clean_html(code).split('(')[0].split(';')[0].strip()[:12]
        html += f'<div class="toc-item"><a href="#af-{af["number"]}">{escape(name)}'
        if code_clean:
            html += f' <span class="code">{escape(code_clean)}</span>'
        html += '</a></div>\n'
    html += '</div>\n</div>\n'

    # Airfield cards
    current_group = ''
    for af in airfields:
        group = af.get('group', '')
        if group and group != current_group:
            current_group = group
            html += f'<div class="group-divider">{escape(clean_html(group))}</div>\n'
        html += build_airfield_card(af, embed_diagrams=embed_diagrams)

    html += '</div>\n'  # container
    html += '<button class="back-to-top" title="Back to top">&#8593;</button>\n'
    html += f'<script>{JAVASCRIPT}</script>\n'
    html += '</body>\n</html>\n'

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"HTML generated: {output_path}")
    print(f"Total airfields: {len(airfields)}")


if __name__ == '__main__':
    print("=" * 50)
    print("SA Airfield Directory - HTML Generator")
    print("=" * 50)

    print("\nParsing airfield directory...")
    airfields = parse_airfields(MD_FILE)
    print(f"  Found {len(airfields)} airfields")

    print("\nGenerating HTML (with linked diagrams)...")
    generate_html(airfields, OUTPUT_HTML, embed_diagrams=False)

    file_size = os.path.getsize(OUTPUT_HTML)
    print(f"File size: {file_size / 1024:.1f} KB")
