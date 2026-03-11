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

MD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'AIRFIELD_DIRECTORY.md')
OUTPUT_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Airfield_Directory.html')
DIAGRAMS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diagrams')
FAVICON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'favicon.svg')


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


def parse_dms_coord(coord_str):
    """Parse DMS coordinate string like 'S33°45'44" E18°32'55"' to (lat, lon) decimal."""
    if not coord_str:
        return None, None
    # Remove approximate markers and notes
    coord_str = coord_str.replace('~', '').split('(')[0].strip()
    # Match hemisphere + degrees + optional minutes + optional seconds
    pattern = r'([NS])\s*(\d+)[°]\s*(\d+)?[\'′]?\s*(\d+(?:\.\d+)?)?[\"″]?\s*([EW])\s*(\d+)[°]\s*(\d+)?[\'′]?\s*(\d+(?:\.\d+)?)?[\"″]?'
    m = re.search(pattern, coord_str)
    if not m:
        return None, None
    lat_h, lat_d, lat_m, lat_s = m.group(1), float(m.group(2)), float(m.group(3) or 0), float(m.group(4) or 0)
    lon_h, lon_d, lon_m, lon_s = m.group(5), float(m.group(6)), float(m.group(7) or 0), float(m.group(8) or 0)
    lat = lat_d + lat_m / 60 + lat_s / 3600
    lon = lon_d + lon_m / 60 + lon_s / 3600
    if lat_h == 'S':
        lat = -lat
    if lon_h == 'W':
        lon = -lon
    return round(lat, 6), round(lon, 6)


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
    --green: #276749;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    color: var(--text);
    background: #f0f4f8;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
}
.container { max-width: 900px; margin: 0 auto; padding: 16px; }

/* ── Header / Nav ── */
.site-header {
    background: var(--navy);
    color: white;
    padding: 12px 0;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.site-header .container { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.site-header h1 { font-size: 18px; flex-shrink: 0; }
.site-header h1 span { font-weight: 400; font-size: 13px; opacity: 0.8; display: block; }
.search-wrapper {
    flex: 1; min-width: 200px; position: relative;
}
#search-box {
    width: 100%;
    padding: 9px 36px 9px 14px; border: none; border-radius: 6px;
    font-size: 14px; background: rgba(255,255,255,0.15);
    color: white;
    transition: background 0.2s;
}
#search-box::placeholder { color: rgba(255,255,255,0.6); }
#search-box:focus { outline: none; background: rgba(255,255,255,0.25); }
#clear-search {
    position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
    background: none; border: none; color: rgba(255,255,255,0.5);
    font-size: 18px; cursor: pointer; display: none; padding: 4px;
}
#clear-search:hover { color: white; }
#search-count {
    font-size: 11px; color: rgba(255,255,255,0.7);
    margin-top: 2px; min-height: 16px;
}

/* ── Toolbar ── */
.toolbar {
    background: var(--blue);
    padding: 6px 0;
}
.toolbar .container {
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 6px;
}
.toolbar-links { display: flex; gap: 6px; flex-wrap: wrap; }
.toolbar a, .toolbar button {
    color: white;
    text-decoration: none;
    font-size: 13px;
    font-weight: 600;
    padding: 5px 14px;
    border-radius: 4px;
    background: rgba(255,255,255,0.15);
    display: inline-flex; align-items: center; gap: 6px;
    border: none; cursor: pointer;
    transition: background 0.2s;
}
.toolbar a:hover, .toolbar button:hover { background: rgba(255,255,255,0.3); }
.toolbar .updated {
    font-size: 11px; color: rgba(255,255,255,0.75);
    font-weight: 400;
}

/* ── Nearby panel ── */
#nearby-panel {
    display: none;
    background: white;
    border-radius: 8px;
    padding: 16px;
    margin: 16px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    border-left: 4px solid var(--green);
}
#nearby-panel h2 { font-size: 16px; color: var(--green); margin-bottom: 8px; }
#nearby-panel .nearby-list { list-style: none; }
#nearby-panel .nearby-item {
    display: flex; justify-content: space-between; align-items: center;
    padding: 6px 8px; border-radius: 4px;
}
#nearby-panel .nearby-item:hover { background: var(--light-gray); }
#nearby-panel .nearby-item a { color: var(--navy); text-decoration: none; font-weight: 600; font-size: 14px; }
#nearby-panel .nearby-dist { color: var(--text-muted); font-size: 13px; white-space: nowrap; }
#nearby-panel .nearby-status { font-size: 13px; color: var(--text-muted); padding: 8px; }

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
.toc h2 { font-size: 16px; color: var(--navy); margin-bottom: 8px; cursor: pointer; user-select: none; }
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
    transition: background 0.15s;
}
.toc-item a:hover { background: var(--light-gray); }
.toc-item .code { color: var(--text-muted); font-size: 11px; margin-left: 4px; }
.toc-group { font-weight: 700; font-size: 12px; color: var(--blue); margin-top: 8px; grid-column: 1 / -1; }

/* ── Airfield card ── */
.airfield-card {
    background: white;
    border-radius: 8px;
    margin: 14px 0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    overflow: hidden;
    transition: box-shadow 0.2s;
}
.airfield-card:target {
    box-shadow: 0 0 0 3px var(--blue), 0 2px 8px rgba(0,0,0,0.12);
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
    gap: 3px 10px;
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
    width: 44px;
    height: 44px;
    font-size: 20px;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    display: none;
    transition: opacity 0.2s;
}
.back-to-top:hover { opacity: 0.85; }
.group-divider {
    font-size: 14px;
    font-weight: 700;
    color: var(--navy);
    text-align: center;
    margin: 24px 0 8px 0;
    padding: 8px;
    background: var(--light-gray);
    border-radius: 6px;
}

/* ── No results ── */
#no-results {
    display: none;
    text-align: center;
    padding: 40px 20px;
    color: var(--text-muted);
    font-size: 16px;
}

/* ── Responsive ── */
@media (max-width: 600px) {
    .info-grid { grid-template-columns: 100px 1fr; font-size: 12px; }
    .site-header h1 { font-size: 15px; }
    .site-header h1 span { font-size: 11px; }
    .toc-grid { grid-template-columns: 1fr; }
    .toolbar .container { justify-content: center; }
}
@media print {
    .site-header { position: static; }
    .airfield-card { page-break-inside: avoid; }
    .back-to-top { display: none !important; }
    #search-box, #clear-search, #search-count { display: none; }
    .toolbar { display: none; }
    #nearby-panel { display: none !important; }
}
"""

JAVASCRIPT = """
document.addEventListener('DOMContentLoaded', function() {
    var searchBox = document.getElementById('search-box');
    var clearBtn = document.getElementById('clear-search');
    var searchCount = document.getElementById('search-count');
    var cards = document.querySelectorAll('.airfield-card');
    var groups = document.querySelectorAll('.group-divider');
    var tocItems = document.querySelectorAll('.toc-item');
    var backBtn = document.querySelector('.back-to-top');
    var noResults = document.getElementById('no-results');
    var totalCount = cards.length;

    function doSearch() {
        var q = searchBox.value.toLowerCase().trim();
        clearBtn.style.display = q ? 'block' : 'none';
        var visible = 0;
        cards.forEach(function(card) {
            var text = card.dataset.search || card.textContent.toLowerCase();
            var show = !q || text.indexOf(q) !== -1;
            card.style.display = show ? '' : 'none';
            if (show) visible++;
        });
        groups.forEach(function(g) {
            g.style.display = q ? 'none' : '';
        });
        tocItems.forEach(function(item) {
            var text = item.textContent.toLowerCase();
            item.style.display = (!q || text.indexOf(q) !== -1) ? '' : 'none';
        });
        if (q) {
            searchCount.textContent = visible + ' of ' + totalCount + ' airfields';
            noResults.style.display = visible === 0 ? 'block' : 'none';
        } else {
            searchCount.textContent = '';
            noResults.style.display = 'none';
        }
    }

    searchBox.addEventListener('input', doSearch);
    clearBtn.addEventListener('click', function() {
        searchBox.value = '';
        doSearch();
        searchBox.focus();
    });

    window.addEventListener('scroll', function() {
        backBtn.style.display = window.scrollY > 400 ? 'block' : 'none';
    });
    backBtn.addEventListener('click', function() {
        window.scrollTo({top: 0, behavior: 'smooth'});
    });

    // Keyboard shortcut: press / to focus search
    document.addEventListener('keydown', function(e) {
        if (e.key === '/' && document.activeElement !== searchBox) {
            e.preventDefault();
            searchBox.focus();
            searchBox.select();
        }
        if (e.key === 'Escape' && document.activeElement === searchBox) {
            searchBox.value = '';
            doSearch();
            searchBox.blur();
        }
    });

    // --- Geolocation: find nearest airfields ---
    var nearbyBtn = document.getElementById('nearby-btn');
    var nearbyPanel = document.getElementById('nearby-panel');
    var nearbyStatus = document.getElementById('nearby-status');
    var nearbyList = document.getElementById('nearby-list');

    if (nearbyBtn && navigator.geolocation) {
        nearbyBtn.style.display = 'inline-flex';
        nearbyBtn.addEventListener('click', function() {
            nearbyPanel.style.display = 'block';
            nearbyStatus.textContent = 'Getting your location...';
            nearbyList.innerHTML = '';
            navigator.geolocation.getCurrentPosition(function(pos) {
                var userLat = pos.coords.latitude;
                var userLon = pos.coords.longitude;
                showNearest(userLat, userLon);
            }, function(err) {
                nearbyStatus.textContent = 'Location unavailable: ' + err.message;
            }, {enableHighAccuracy: true, timeout: 10000});
        });
    }

    function haversine(lat1, lon1, lat2, lon2) {
        var R = 6371; // km
        var dLat = (lat2 - lat1) * Math.PI / 180;
        var dLon = (lon2 - lon1) * Math.PI / 180;
        var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                Math.sin(dLon/2) * Math.sin(dLon/2);
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    function showNearest(userLat, userLon) {
        var airfieldsWithDist = [];
        cards.forEach(function(card) {
            var lat = parseFloat(card.dataset.lat);
            var lon = parseFloat(card.dataset.lon);
            if (!isNaN(lat) && !isNaN(lon)) {
                var dist = haversine(userLat, userLon, lat, lon);
                var nm = dist * 0.539957; // km to NM
                var name = card.querySelector('h3').textContent;
                var id = card.id;
                airfieldsWithDist.push({name: name, dist: dist, nm: nm, id: id});
            }
        });
        airfieldsWithDist.sort(function(a, b) { return a.dist - b.dist; });
        var top = airfieldsWithDist.slice(0, 10);
        if (top.length === 0) {
            nearbyStatus.textContent = 'No airfields with coordinates found.';
            return;
        }
        nearbyStatus.textContent = '';
        var html = '';
        top.forEach(function(af) {
            html += '<li class="nearby-item">';
            html += '<a href="#' + af.id + '">' + af.name + '</a>';
            html += '<span class="nearby-dist">' + af.nm.toFixed(0) + ' NM (' + af.dist.toFixed(0) + ' km)</span>';
            html += '</li>';
        });
        nearbyList.innerHTML = html;
    }
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

    # Parse coordinates for geolocation
    coord_str = f.get('Coordinates', '')
    lat, lon = parse_dms_coord(coord_str)
    coord_attrs = f' data-lat="{lat}" data-lon="{lon}"' if lat is not None else ''

    html = f'<div class="airfield-card" id="af-{airfield["number"]}" data-search="{escape(search_text)}"{coord_attrs}>\n'
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
    html += '<title>South African Airfield Directory</title>\n'

    # Embed favicon as inline SVG data URI
    favicon_link = ''
    if os.path.exists(FAVICON_FILE):
        with open(FAVICON_FILE, 'r', encoding='utf-8') as fav:
            svg_data = fav.read().replace('\n', ' ').replace('"', "'")
        favicon_link = f'<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,{svg_data}">\n'
    html += favicon_link
    html += f'<style>{CSS}</style>\n'
    html += '</head>\n<body>\n'

    # Header with search
    html += '<header class="site-header">\n<div class="container">\n'
    html += '<h1>SA Airfield Directory <span>VFR Reference</span></h1>\n'
    html += '<div class="search-wrapper">\n'
    html += '<input type="text" id="search-box" placeholder="Search airfields, codes, frequencies... (press /)">\n'
    html += '<button id="clear-search" title="Clear search">&times;</button>\n'
    html += '</div>\n'
    html += '<div id="search-count"></div>\n'
    html += '</div>\n</header>\n'

    # Toolbar (downloads + nearby + updated date)
    html += '<div class="toolbar">\n<div class="container">\n'
    html += '<div class="toolbar-links">\n'
    if download_links:
        for link in download_links:
            dl_attr = f' download="{escape(link["href"].split("/")[-1])}"' if link.get('download', True) else ''
            html += f'  <a href="{escape(link["href"])}"{dl_attr}>{escape(link["label"])}</a>\n'
    html += '  <button id="nearby-btn" style="display:none;">Find Nearest</button>\n'
    html += '</div>\n'
    html += f'<span class="updated">Updated {build_date}</span>\n'
    html += '</div>\n</div>\n'

    html += '<div class="container">\n'

    # Nearby airfields panel (hidden until activated)
    html += '<div id="nearby-panel">\n'
    html += '<h2>Nearest Airfields</h2>\n'
    html += '<div id="nearby-status" class="nearby-status"></div>\n'
    html += '<ul id="nearby-list" class="nearby-list"></ul>\n'
    html += '</div>\n'

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

    html += '<div id="no-results">No airfields match your search.</div>\n'
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
