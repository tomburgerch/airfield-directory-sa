#!/usr/bin/env python3
"""
Generate a searchable HTML version of the South African Airfield Directory.
"""

import os
import re
import base64
from datetime import datetime, timezone
from html import escape

from parse_markdown import parse_airfields
from pdf_styles import EMOJI_MAP
from shared import MD_FILE, OUTPUT_HTML, DIAGRAMS_DIR, FAVICON_FILE, parse_dms_coord, get_icao
from html_assets import CSS, JAVASCRIPT
from tower_data import TOWER_PHONES


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


def extract_links(raw_value):
    """Extract markdown links from a raw field value, return list of (label, url)."""
    if not raw_value:
        return []
    return re.findall(r'\[([^\]]+)\]\(([^)]+)\)', raw_value)


def build_airfield_card(airfield, embed_diagrams=False):
    """Build HTML for a single airfield card."""
    f = airfield['fields']
    name = clean_html(airfield['name'])
    is_closed = '[X]' in name or 'CLOSED' in name.upper()
    is_military = 'Military' in f.get('Access', '') or 'MIL' in clean_html(f.get('Access', '')).upper()

    code = get_icao(airfield)
    code_clean = clean_html(code)
    access = clean_html(f.get('Access', ''))

    header_class = 'closed' if is_closed else ('military' if is_military else '')
    search_text = f"{name} {code_clean} {access}".lower()

    # Parse coordinates for geolocation
    coord_str = f.get('Coordinates', '')
    lat, lon = parse_dms_coord(coord_str)
    coord_attrs = f' data-lat="{lat}" data-lon="{lon}"' if lat is not None else ''

    # Filter data attributes
    fuel_raw = clean_html(f.get('Fuel', '')).upper()
    has_fuel = '1' if fuel_raw and 'NO' not in fuel_raw.split()[0:1] and 'NONE' not in fuel_raw and fuel_raw not in ('', '-', 'N/A', '?', '(?)') else '0'

    night_raw = clean_html(f.get('Night Ops', '')).upper()
    has_night = '1' if night_raw and 'NO' not in night_raw.split()[0:2] and night_raw not in ('', '-', 'N/A', 'NONE') else '0'

    # Surface: extract from runways
    surfaces = set()
    for rwy in airfield.get('runways', []):
        if len(rwy) >= 4:
            s = clean_html(rwy[3]).upper()
            if 'ASPHALT' in s or 'TAR' in s or 'PAVED' in s or 'TARMAC' in s or 'CONCRETE' in s:
                surfaces.add('paved')
            elif 'GRASS' in s or 'TURF' in s:
                surfaces.add('grass')
            else:
                surfaces.add('other')
    surface_attr = ','.join(sorted(surfaces)) if surfaces else 'unknown'

    # Access type
    access_upper = access.upper()
    if is_closed:
        access_type = 'closed'
    elif is_military:
        access_type = 'military'
    elif 'PPR' in access_upper:
        access_type = 'ppr'
    elif 'PUBLIC' in access_upper or 'OPEN' in access_upper:
        access_type = 'public'
    else:
        access_type = 'other'

    # Towered: check for TWR or Tower in frequencies
    freq_val = clean_html(f.get('Frequencies', f.get('Frequency', ''))).upper()
    has_tower = 'TWR' in freq_val or 'TOWER' in freq_val
    if not has_tower:
        for frow in airfield.get('frequencies_table', []):
            row_text = ' '.join(clean_html(c) for c in frow).upper()
            if 'TWR' in row_text or 'TOWER' in row_text:
                has_tower = True
                break
    towered_attr = '1' if has_tower else '0'

    # Official: has a proper FA?? ICAO code (not ZA-xxxx or blank)
    has_icao = bool(re.search(r'\bFA[A-Z]{2}\b', code_clean))
    official_attr = '1' if has_icao else '0'

    filter_attrs = f' data-fuel="{has_fuel}" data-night="{has_night}" data-surface="{surface_attr}" data-access="{access_type}" data-towered="{towered_attr}" data-official="{official_attr}"'

    html = f'<div class="airfield-card" id="af-{airfield["number"]}" data-search="{escape(search_text)}"{coord_attrs}{filter_attrs}>\n'
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

    # Tower phone for towered fields
    icao_code = code_clean.split('(')[0].split(';')[0].split('/')[0].strip()[:4]
    tower_phone = TOWER_PHONES.get(icao_code, '')
    if tower_phone and has_tower:
        phone_link = f'<a href="tel:{tower_phone}" style="color:var(--green);font-weight:700;text-decoration:none">{escape(tower_phone)}</a>'
        grid_items.append(f'    <div class="label">Tower Tel</div><div class="value">{phone_link}</div>\n')

    if grid_items:
        html += '    <div class="info-grid">\n' + ''.join(grid_items) + '    </div>\n'

    # Website / flying club links
    raw = airfield.get('fields_raw', {})
    web_links = []
    for key in ('Website', 'Websites', 'AIP Link', 'Operator AIP'):
        web_links.extend(extract_links(raw.get(key, '')))
    if web_links:
        html += '    <div class="web-links">\n'
        for label, url in web_links:
            html += f'      <a href="{escape(url)}" target="_blank" rel="noopener">{escape(clean_html(label))}</a>\n'
        html += '    </div>\n'

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

    # Warnings
    for w in airfield['warnings'][:5]:
        html += f'    <div class="warning">[!] {escape(clean_html(w))}</div>\n'

    # Notes
    if airfield['notes']:
        html += '    <div class="section-title">Notes</div>\n'
        for note in airfield['notes'][:8]:
            html += f'    <div class="note">- {escape(clean_html(note))}</div>\n'

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

    # Contact
    if airfield['contact']:
        html += f'    <div class="contact"><strong>Contact:</strong> {escape(clean_html(airfield["contact"]))}</div>\n'

    html += '  </div>\n</div>\n'
    return html


def generate_html(airfields, output_path, embed_diagrams=False, download_links=None):
    """Generate a complete searchable HTML file.

    Args:
        airfields: List of parsed airfield dicts.
        output_path: Where to write the HTML file.
        embed_diagrams: If True, base64-encode diagram images into the HTML.
        download_links: Optional list of dicts with 'label', 'href' keys for download bar.
    """
    build_date = datetime.now(timezone.utc).strftime('%d %b %Y')

    html = '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
    html += '<meta charset="UTF-8">\n'
    html += '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    html += '<title>Wagyu Wings — SA Airfield Directory</title>\n'

    # Favicon links
    html += '<link rel="icon" type="image/png" href="favicon.png">\n'
    html += '<link rel="icon" type="image/x-icon" href="favicon.ico">\n'
    html += '<link rel="apple-touch-icon" href="apple-touch-icon.png">\n'
    html += f'<style>{CSS}</style>\n'
    html += '</head>\n<body>\n'

    # Unified header: logo + search + actions + filters
    html += '<header class="site-header">\n'
    html += '<div class="header-top">\n'
    html += '<h1><a href="https://wagyuwings.com" style="color:#FFD700;text-decoration:none">Wagyu Wings</a> <span>SA Airfield Directory</span></h1>\n'
    html += '<div class="search-wrapper">\n'
    html += '<input type="text" id="search-box" placeholder="Search airfields, codes, frequencies... (press /)">\n'
    html += '<button id="clear-search" title="Clear search">&times;</button>\n'
    html += '</div>\n'
    html += '<div class="header-actions">\n'
    if download_links:
        html += '  <span class="dl-dropdown">\n'
        html += '    <button class="dl-trigger">Download &#9662;</button>\n'
        html += '    <span class="dl-menu">\n'
        for link in download_links:
            dl_attr = f' download="{escape(link["href"].split("/")[-1])}"'
            html += f'      <a href="{escape(link["href"])}"{dl_attr}>{escape(link["label"])}</a>\n'
        html += '    </span>\n'
        html += '  </span>\n'
    html += '  <button id="nearby-btn" style="display:none;">Find Nearest</button>\n'
    html += '  <span class="contact-tip">Contact<span class="contact-tooltip"><span class="contact-tooltip-inner">Bug report or feedback?<br><a href="mailto:info@cedricwaldburger.com">info@cedricwaldburger.com</a></span></span></span>\n'
    html += '</div>\n'
    html += '</div>\n'

    # Second row: filters + counts + date
    html += '<div class="header-bottom" id="filter-bar">\n'
    html += '<span class="filter-label">Filter:</span>\n'
    html += '<button class="filter-btn" data-filter="fuel">Fuel</button>\n'
    html += '<button class="filter-btn" data-filter="night">Night Ops</button>\n'
    html += '<button class="filter-btn" data-filter="towered">Towered</button>\n'
    html += '<span class="filter-sep"></span>\n'
    html += '<button class="filter-btn" data-filter="surface-paved">Paved</button>\n'
    html += '<button class="filter-btn" data-filter="surface-grass">Grass</button>\n'
    html += '<span class="filter-sep"></span>\n'
    html += '<button class="filter-btn" data-filter="access-public">Public</button>\n'
    html += '<button class="filter-btn" data-filter="access-ppr">PPR</button>\n'
    html += '<span class="filter-sep"></span>\n'
    html += '<button class="filter-btn" data-filter="official">ICAO Listed</button>\n'
    html += '<span id="filter-count"></span>\n'
    html += '<span id="search-count"></span>\n'
    html += f'<span class="updated">Updated {build_date}</span>\n'
    html += '</div>\n'
    html += '</header>\n'

    html += '<div class="container">\n'

    # Nearby airfields panel (hidden until activated)
    html += '<div id="nearby-panel">\n'
    html += '<h2>Nearest Airfields</h2>\n'
    html += '<div id="nearby-status" class="nearby-status"></div>\n'
    html += '<ul id="nearby-list" class="nearby-list"></ul>\n'
    html += '</div>\n'

    # Build per-province airfield lists for TOC
    province_order = []
    province_airfields = {}
    for af in airfields:
        group = af.get('group', '')
        if group not in province_airfields:
            province_order.append(group)
            province_airfields[group] = []
        province_airfields[group].append(af)

    # TOC
    html += '<div class="toc">\n<h2>Airfield Index</h2>\n<div class="toc-grid">\n'
    for province in province_order:
        if province:
            html += f'<div class="toc-group">{escape(clean_html(province))}</div>\n'
        for af in province_airfields[province]:
            name = clean_html(af['name'])
            code = get_icao(af)
            code_clean = clean_html(code).split('(')[0].split(';')[0].strip()[:12]
            html += f'<div class="toc-item"><a href="#af-{af["number"]}">{escape(name)}'
            if code_clean:
                html += f' <span class="code">{escape(code_clean)}</span>'
            html += '</a></div>\n'
    html += '</div>\n</div>\n'

    # Airfield cards (show province divider only on first occurrence)
    seen_provinces = set()
    for af in airfields:
        group = af.get('group', '')
        if group and group not in seen_provinces:
            seen_provinces.add(group)
            html += f'<div class="group-divider">{escape(clean_html(group))}</div>\n'
        html += build_airfield_card(af, embed_diagrams=embed_diagrams)

    html += '<div id="no-results">No airfields match your search.</div>\n'
    html += '</div>\n'  # container

    # Disclaimer (collapsed, tooltip on hover)
    html += '<div class="container"><div class="disclaimer">\n'
    html += '<span class="disc-label">DISCLAIMER — Supplementary reference only. Hover for details.</span>\n'
    html += '<div class="disc-full"><div class="disc-full-inner">\n'
    html += '<strong>IMPORTANT DISCLAIMER</strong>\n'
    html += '<p>This directory is a <strong>supplementary reference only</strong> and does '
    html += '<strong>NOT replace</strong> official aviation publications. '
    html += 'Pilots must always consult the current <strong>SACAA AIP</strong>, active '
    html += '<strong>NOTAMs</strong>, and official aerodrome charts before flight. '
    html += 'Contact airfield operators to verify access, fuel, hours, and runway status.</p>\n'
    html += '<p>Data marked (?) is unverified. No warranty is given for accuracy or completeness. '
    html += 'Use entirely at your own risk.</p>\n'
    html += '</div></div>\n</div></div>\n'

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
