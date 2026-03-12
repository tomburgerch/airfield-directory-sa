#!/usr/bin/env python3
"""
Generate a searchable HTML version of the South African Airfield Directory.
"""

import os
import re
import base64
from datetime import datetime, timezone
from html import escape

from parse_markdown import parse_airfields, parse_frequency_tables
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


def extract_links(raw_value):
    """Extract markdown links from a raw field value, return list of (label, url)."""
    if not raw_value:
        return []
    return re.findall(r'\[([^\]]+)\]\(([^)]+)\)', raw_value)


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
    --navy: #1a1a1a;
    --blue: #b8860b;
    --red: #c53030;
    --dark-red: #9b2c2c;
    --dark-gray: #2d2d2d;
    --light-gray: #faf9f6;
    --border: #e5e0d5;
    --text: #1a1a1a;
    --text-muted: #6b6560;
    --green: #276749;
    --gold: #d4a017;
    --gold-light: #f5e6b8;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    color: var(--text);
    background: #f5f3ee;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
}
.container { max-width: 900px; margin: 0 auto; padding: 16px; }

/* ── Unified Header ── */
.site-header {
    background: var(--navy);
    color: white;
    padding: 10px 0 8px;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.header-top {
    display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
    max-width: 900px; margin: 0 auto; padding: 0 16px;
}
.site-header h1 { font-size: 16px; flex-shrink: 0; color: #FFD700; line-height: 1.2; }
.site-header h1 span { font-weight: 400; font-size: 11px; color: rgba(255,255,255,0.6); display: block; }
.search-wrapper {
    flex: 1; min-width: 180px; position: relative;
}
#search-box {
    width: 100%;
    padding: 7px 32px 7px 12px; border: none; border-radius: 5px;
    font-size: 13px; background: rgba(255,255,255,0.13);
    color: white;
    transition: background 0.2s;
}
#search-box::placeholder { color: rgba(255,255,255,0.5); }
#search-box:focus { outline: none; background: rgba(255,255,255,0.22); }
#clear-search {
    position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
    background: none; border: none; color: rgba(255,255,255,0.5);
    font-size: 16px; cursor: pointer; display: none; padding: 2px;
}
#clear-search:hover { color: white; }
.header-actions {
    display: flex; gap: 5px; flex-wrap: wrap; align-items: center;
}
.header-actions a, .header-actions button {
    color: white;
    text-decoration: none;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 4px;
    background: rgba(255,255,255,0.12);
    display: inline-flex; align-items: center; gap: 4px;
    border: none; cursor: pointer;
    transition: background 0.2s;
    white-space: nowrap;
}
.header-actions a:hover, .header-actions button:hover { background: rgba(255,255,255,0.25); }
.dl-dropdown { position: relative; display: inline-block; }
.dl-trigger {
    color: white; font-size: 11px; font-weight: 600;
    padding: 4px 10px; border-radius: 4px;
    background: rgba(255,255,255,0.12);
    border: none; cursor: pointer;
    transition: background 0.2s;
}
.dl-trigger:hover { background: rgba(255,255,255,0.25); }
.dl-menu {
    display: none;
    position: absolute;
    top: 100%;
    left: 0;
    z-index: 9999;
    flex-direction: column;
    background: #333;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    overflow: hidden;
    min-width: 160px;
}
.dl-dropdown:hover .dl-menu { display: flex; }
.dl-menu a {
    color: white !important;
    font-size: 12px;
    padding: 8px 14px;
    text-decoration: none;
    font-weight: 500;
    background: none !important;
    border-radius: 0 !important;
    transition: background 0.15s;
}
.dl-menu a:hover { background: rgba(255,255,255,0.1) !important; }
.contact-tip {
    position: relative;
    display: inline-block;
    color: white;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 4px;
    background: rgba(255,255,255,0.12);
    cursor: help;
}
.contact-tip:hover { background: rgba(255,255,255,0.25); }
.contact-tooltip {
    display: none;
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    z-index: 9999;
    padding-top: 4px;
}
.contact-tooltip-inner {
    background: #333;
    color: white;
    padding: 10px 14px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 400;
    white-space: nowrap;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    line-height: 1.6;
}
.contact-tooltip-inner a { color: #FFD700; text-decoration: underline; }
.contact-tip:hover .contact-tooltip { display: block; }
.header-bottom {
    display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
    max-width: 900px; margin: 6px auto 0; padding: 0 16px;
    border-top: 1px solid rgba(255,255,255,0.08);
    padding-top: 7px;
}
.header-bottom .filter-label {
    font-size: 11px;
    font-weight: 700;
    color: rgba(255,255,255,0.5);
    margin-right: 2px;
}
.header-bottom .filter-btn {
    font-size: 11px;
    padding: 3px 9px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.2);
    background: transparent;
    color: rgba(255,255,255,0.75);
    cursor: pointer;
    transition: all 0.15s;
    font-weight: 500;
}
.header-bottom .filter-btn:hover { border-color: #FFD700; color: #FFD700; }
.header-bottom .filter-btn.active {
    background: #FFD700;
    color: var(--navy);
    border-color: #FFD700;
    font-weight: 700;
}
.header-bottom .filter-sep {
    width: 1px;
    height: 16px;
    background: rgba(255,255,255,0.15);
}
#search-count {
    font-size: 10px; color: rgba(255,255,255,0.6);
    margin-left: auto;
}
#filter-count {
    font-size: 10px;
    color: rgba(255,255,255,0.6);
}
.header-bottom .updated {
    font-size: 10px; color: rgba(255,255,255,0.45);
    margin-left: auto;
}

/* ── Sort index (A-Z / Nearest) ── */
#sort-index {
    display: none;
    background: white;
    border-radius: 8px;
    padding: 16px;
    margin: 16px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
#sort-index h2 { font-size: 16px; color: var(--navy); margin-bottom: 8px; cursor: pointer; user-select: none; }
#sort-index .sort-index-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 4px 16px;
}
#sort-index .si-letter { font-weight: 700; font-size: 12px; color: var(--blue); margin-top: 8px; grid-column: 1 / -1; }
#sort-index .si-item a {
    color: var(--navy);
    text-decoration: none;
    font-size: 13px;
    display: block;
    padding: 3px 6px;
    border-radius: 4px;
    transition: background 0.15s;
}
#sort-index .si-item a:hover { background: var(--light-gray); }
#sort-index .si-dist { color: var(--text-muted); font-size: 11px; margin-left: 4px; }

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

/* ── Sort: distance badge on cards ── */
.dist-badge {
    display: none;
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 500;
    margin-left: auto;
    white-space: nowrap;
}
.sort-nearest .dist-badge { display: inline; }

/* ── Disclaimer ── */
.disclaimer {
    background: var(--red);
    color: white;
    padding: 8px 16px;
    border-radius: 8px;
    margin: 24px 0 8px;
    font-size: 12px;
    text-align: center;
    cursor: help;
    position: relative;
}
.disclaimer .disc-label { font-weight: 700; }
.disclaimer .disc-full {
    display: none;
    position: absolute;
    bottom: 100%;
    padding-bottom: 8px;
    left: 50%; transform: translateX(-50%);
    width: min(500px, 90vw);
    z-index: 100;
}
.disclaimer .disc-full-inner {
    background: var(--red);
    color: white;
    padding: 14px 18px;
    border-radius: 8px;
    font-size: 13px;
    line-height: 1.6;
    text-align: left;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25);
}
.disclaimer:hover .disc-full { display: block; }
.disclaimer .disc-full-inner p { margin-top: 6px; }

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
.airfield-header .pdf-dl {
    color: rgba(255,255,255,0.7);
    text-decoration: none;
    font-size: 16px;
    line-height: 1;
    padding: 2px 4px;
    border-radius: 4px;
    transition: color 0.15s, background 0.15s;
}
.airfield-header .pdf-dl:hover { color: white; background: rgba(255,255,255,0.15); }
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
.web-links {
    font-size: 12px;
    margin-bottom: 8px;
    display: flex; flex-wrap: wrap; gap: 4px 14px;
}
.web-links a {
    color: var(--blue);
    text-decoration: none;
    font-weight: 600;
}
.web-links a:hover { text-decoration: underline; }

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

/* (filters are in the unified header) */

/* ── FIR Frequencies Section ── */
.fir-section {
    background: white;
    border-radius: 8px;
    padding: 16px;
    margin: 16px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.fir-section h2 {
    font-size: 16px;
    color: var(--navy);
    margin-bottom: 10px;
    cursor: pointer;
    user-select: none;
}
.fir-section .fir-body { }
.fir-section.collapsed .fir-body { display: none; }
.fir-map {
    width: 100%;
    height: 350px;
    border-radius: 6px;
    border: 1px solid var(--border);
    margin-bottom: 12px;
}
.fir-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 8px;
    border-bottom: 2px solid var(--border);
    padding-bottom: 4px;
}
.fir-tab {
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid var(--border);
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    background: var(--light-gray);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
}
.fir-tab:hover { color: var(--text); background: #eee; }
.fir-tab.active {
    background: white;
    color: var(--navy);
    border-color: var(--blue);
    border-bottom: 2px solid white;
    margin-bottom: -6px;
}
.fir-tab-content { display: none; }
.fir-tab-content.active { display: block; }
.fir-tab-content table.freq-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}
.fir-tab-content table.freq-table th {
    background: var(--blue);
    color: white;
    padding: 5px 10px;
    text-align: left;
    font-size: 11px;
}
.fir-tab-content table.freq-table th:last-child {
    text-align: right;
}
.fir-tab-content table.freq-table td {
    padding: 4px 10px;
    border-bottom: 1px solid var(--border);
}
.fir-tab-content table.freq-table td:last-child {
    color: var(--blue);
    font-weight: 700;
    text-align: right;
}
.fir-tab-content table.freq-table tr:nth-child(even) { background: var(--light-gray); }
.fir-tab-note {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
    font-style: italic;
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
    .site-header h1 { font-size: 14px; }
    .site-header h1 span { font-size: 10px; }
    .toc-grid { grid-template-columns: 1fr; }
    #sort-index .sort-index-grid { grid-template-columns: 1fr; }
    .header-top { gap: 8px; }
    .header-actions { gap: 3px; }
    .header-bottom { gap: 4px; }
    .header-bottom .updated { display: none; }
    .fir-map { height: 250px; }
    .fir-tab { font-size: 11px; padding: 4px 8px; }
}
@media print {
    .site-header { position: static; }
    .airfield-card { page-break-inside: avoid; }
    .back-to-top { display: none !important; }
    #search-box, #clear-search, #search-count { display: none; }
    .header-actions, .header-bottom { display: none; }
    #nearby-panel { display: none !important; }
    #sort-index { display: none !important; }
    .fir-section { display: none !important; }
    .pdf-dl { display: none !important; }
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
    var filterBtns = document.querySelectorAll('.filter-btn[data-filter]');
    var filterCount = document.getElementById('filter-count');
    var tocSection = document.querySelector('.toc');
    var firSectionEl = document.getElementById('fir-section');
    var filterBar = document.getElementById('filter-bar');
    var totalCount = cards.length;
    var activeFilters = {};

    function passesFilters(card) {
        for (var key in activeFilters) {
            if (!activeFilters[key]) continue;
            if (key === 'fuel' && card.dataset.fuel !== '1') return false;
            if (key === 'night' && card.dataset.night !== '1') return false;
            if (key === 'surface-paved' && (card.dataset.surface || '').indexOf('paved') === -1) return false;
            if (key === 'surface-grass' && (card.dataset.surface || '').indexOf('grass') === -1) return false;
            if (key === 'access-public' && card.dataset.access !== 'public') return false;
            if (key === 'access-ppr' && card.dataset.access !== 'ppr') return false;
            if (key === 'towered' && card.dataset.towered !== '1') return false;
            if (key === 'official' && card.dataset.official !== '1') return false;
        }
        return true;
    }

    var hasActiveFilter = function() {
        for (var k in activeFilters) { if (activeFilters[k]) return true; }
        return false;
    };

    function doSearch() {
        var q = searchBox.value.toLowerCase().trim();
        clearBtn.style.display = q ? 'block' : 'none';
        var filtering = hasActiveFilter();
        var active = q || filtering;
        var visible = 0;
        cards.forEach(function(card) {
            var text = card.dataset.search || card.textContent.toLowerCase();
            var matchSearch = !q || text.indexOf(q) !== -1;
            var matchFilter = !filtering || passesFilters(card);
            var show = matchSearch && matchFilter;
            card.style.display = show ? '' : 'none';
            if (show) visible++;
        });
        var hideGroups = active || currentSort !== 'province';
        groups.forEach(function(g) {
            g.style.display = hideGroups ? 'none' : '';
        });
        // Hide TOC when searching, filtering, or sorted non-default
        if (tocSection) tocSection.style.display = hideGroups ? 'none' : '';
        // Hide FIR section and nearby panel when searching/filtering
        if (firSectionEl) firSectionEl.style.display = active ? 'none' : '';
        if (nearbyPanel && active) nearbyPanel.style.display = 'none';
        else if (nearbyPanel && !active && currentSort === 'nearest') nearbyPanel.style.display = 'block';
        // Hide sort index when searching or filtering
        if (sortIndex && active) sortIndex.style.display = 'none';
        else if (sortIndex && !active && currentSort !== 'province') sortIndex.style.display = '';
        if (active) {
            searchCount.textContent = visible + ' of ' + totalCount + ' airfields';
            filterCount.textContent = filtering ? visible + ' match' : '';
            noResults.style.display = visible === 0 ? 'block' : 'none';
        } else {
            searchCount.textContent = '';
            filterCount.textContent = '';
            noResults.style.display = 'none';
        }
    }

    filterBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            var f = btn.dataset.filter;
            activeFilters[f] = !activeFilters[f];
            btn.classList.toggle('active', activeFilters[f]);
            doSearch();
        });
    });

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


    // --- Sorting ---
    var sortBtns = document.querySelectorAll('.sort-btn');
    var nearbyBtn = document.getElementById('nearby-btn');
    var nearbyPanel = document.getElementById('nearby-panel');
    var nearbyStatus = document.getElementById('nearby-status');
    var nearbyList = document.getElementById('nearby-list');
    var sortIndex = document.getElementById('sort-index');
    var sortIndexGrid = sortIndex ? sortIndex.querySelector('.sort-index-grid') : null;
    var cardsContainer = cards[0] ? cards[0].parentNode : null;
    var currentSort = 'province';

    // Save original DOM order for province sort restore
    var originalOrder = [];
    if (cardsContainer) {
        Array.prototype.forEach.call(cardsContainer.children, function(el) {
            originalOrder.push(el);
        });
    }

    // Show nearest button only if geolocation available
    if (nearbyBtn && navigator.geolocation) {
        nearbyBtn.style.display = '';
    }

    function haversine(lat1, lon1, lat2, lon2) {
        var R = 6371;
        var dLat = (lat2 - lat1) * Math.PI / 180;
        var dLon = (lon2 - lon1) * Math.PI / 180;
        var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                Math.sin(dLon/2) * Math.sin(dLon/2);
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    function buildSortIndex(items, mode) {
        if (!sortIndexGrid) return;
        var html = '';
        if (mode === 'alpha') {
            var curLetter = '';
            items.forEach(function(c) {
                var name = (c.querySelector('h3') || {}).textContent || '';
                var letter = name.charAt(0).toUpperCase();
                if (letter !== curLetter) {
                    curLetter = letter;
                    html += '<div class="si-letter">' + letter + '</div>';
                }
                html += '<div class="si-item"><a href="#' + c.id + '">' + name + '</a></div>';
            });
        } else if (mode === 'nearest') {
            var buckets = [
                {label: 'Within 25 NM', max: 25},
                {label: '25\u201350 NM', max: 50},
                {label: '50\u2013100 NM', max: 100},
                {label: '100\u2013200 NM', max: 200},
                {label: '200+ NM', max: Infinity}
            ];
            items.forEach(function(item) {
                var nm = item.nm;
                if (nm === Infinity) return;
                for (var i = 0; i < buckets.length; i++) {
                    if (nm <= buckets[i].max) {
                        if (!buckets[i].items) buckets[i].items = [];
                        buckets[i].items.push(item);
                        break;
                    }
                }
            });
            buckets.forEach(function(b) {
                if (!b.items || b.items.length === 0) return;
                html += '<div class="si-letter">' + b.label + ' (' + b.items.length + ')</div>';
                b.items.forEach(function(item) {
                    var name = item.card.querySelector('h3').textContent;
                    html += '<div class="si-item"><a href="#' + item.card.id + '">' + name;
                    html += ' <span class="si-dist">' + item.nm.toFixed(0) + ' NM</span>';
                    html += '</a></div>';
                });
            });
        }
        sortIndexGrid.innerHTML = html;
        sortIndex.style.display = html ? '' : 'none';
    }

    function applySort(mode, userLat, userLon) {
        if (!cardsContainer) return;
        currentSort = mode;
        document.body.classList.remove('sort-nearest');
        if (sortIndex) sortIndex.style.display = 'none';

        sortBtns.forEach(function(b) { b.classList.toggle('active', b.dataset.sort === mode); });

        if (mode === 'province') {
            originalOrder.forEach(function(el) { cardsContainer.appendChild(el); });
            groups.forEach(function(g) { g.style.display = ''; });
            nearbyPanel.style.display = 'none';
            cards.forEach(function(c) {
                var badge = c.querySelector('.dist-badge');
                if (badge) badge.textContent = '';
            });

        } else if (mode === 'alpha') {
            var sorted = Array.prototype.slice.call(cards);
            sorted.sort(function(a, b) {
                var na = (a.querySelector('h3') || {}).textContent || '';
                var nb = (b.querySelector('h3') || {}).textContent || '';
                return na.localeCompare(nb);
            });
            groups.forEach(function(g) { g.style.display = 'none'; });
            nearbyPanel.style.display = 'none';
            sorted.forEach(function(c) { cardsContainer.appendChild(c); });
            cards.forEach(function(c) {
                var badge = c.querySelector('.dist-badge');
                if (badge) badge.textContent = '';
            });
            buildSortIndex(sorted, 'alpha');

        } else if (mode === 'nearest' && userLat !== undefined) {
            document.body.classList.add('sort-nearest');
            var withDist = [];
            cards.forEach(function(card) {
                var lat = parseFloat(card.dataset.lat);
                var lon = parseFloat(card.dataset.lon);
                var dist = (!isNaN(lat) && !isNaN(lon)) ? haversine(userLat, userLon, lat, lon) : Infinity;
                var nm = dist * 0.539957;
                withDist.push({card: card, dist: dist, nm: nm});
                var badge = card.querySelector('.dist-badge');
                if (badge) badge.textContent = dist === Infinity ? '' : nm.toFixed(0) + ' NM';
            });
            withDist.sort(function(a, b) { return a.dist - b.dist; });
            groups.forEach(function(g) { g.style.display = 'none'; });
            withDist.forEach(function(item) { cardsContainer.appendChild(item.card); });

            // Populate top-10 panel
            nearbyPanel.style.display = 'block';
            nearbyStatus.textContent = '';
            var top = withDist.filter(function(x) { return x.dist < Infinity; }).slice(0, 10);
            if (top.length === 0) {
                nearbyStatus.textContent = 'No airfields with coordinates found.';
                nearbyList.innerHTML = '';
            } else {
                var panelHtml = '';
                top.forEach(function(af) {
                    var name = af.card.querySelector('h3').textContent;
                    var id = af.card.id;
                    panelHtml += '<li class="nearby-item">';
                    panelHtml += '<a href="#' + id + '">' + name + '</a>';
                    panelHtml += '<span class="nearby-dist">' + af.nm.toFixed(0) + ' NM (' + af.dist.toFixed(0) + ' km)</span>';
                    panelHtml += '</li>';
                });
                nearbyList.innerHTML = panelHtml;
            }
            buildSortIndex(withDist, 'nearest');
        }
        doSearch();
    }

    sortBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            var mode = btn.dataset.sort;
            if (mode === currentSort) return;
            if (mode === 'nearest') {
                nearbyStatus.textContent = 'Getting your location...';
                nearbyPanel.style.display = 'block';
                nearbyList.innerHTML = '';
                sortBtns.forEach(function(b) { b.classList.toggle('active', b.dataset.sort === 'nearest'); });
                navigator.geolocation.getCurrentPosition(function(pos) {
                    applySort('nearest', pos.coords.latitude, pos.coords.longitude);
                }, function(err) {
                    nearbyStatus.textContent = 'Location unavailable: ' + err.message;
                }, {enableHighAccuracy: true, timeout: 10000});
            } else {
                applySort(mode);
            }
        });
    });

    // --- FIR Tabs ---
    var firTabs = document.querySelectorAll('.fir-tab');
    firTabs.forEach(function(tab) {
        tab.addEventListener('click', function() {
            firTabs.forEach(function(t) { t.classList.remove('active'); });
            tab.classList.add('active');
            document.querySelectorAll('.fir-tab-content').forEach(function(c) { c.classList.remove('active'); });
            var target = document.getElementById(tab.dataset.firTab);
            if (target) target.classList.add('active');
        });
    });

    // --- FIR Map ---
    var firMapEl = document.getElementById('fir-map');
    if (firMapEl && typeof L !== 'undefined') {
        var firMap = L.map('fir-map', {scrollWheelZoom: false}).setView([-29, 25], 5);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 12
        }).addTo(firMap);

        // FIR boundary (approximate Cape Town / Johannesburg split)
        var firBoundary = [
            [-28.5, 16.5], [-28.8, 17.5], [-29.0, 18.5], [-29.2, 19.5],
            [-29.3, 20.5], [-29.5, 21.5], [-29.7, 22.5], [-29.8, 23.5],
            [-29.8, 24.5], [-29.7, 25.5], [-29.5, 26.5], [-29.3, 27.5],
            [-29.2, 28.5], [-29.3, 29.5], [-29.5, 30.0]
        ];
        L.polyline(firBoundary, {color: '#b8860b', weight: 3, dashArray: '8,6', opacity: 0.8}).addTo(firMap);

        // FIR labels
        var ctLabel = L.divIcon({className: '', html: '<div style="background:rgba(255,255,255,0.85);padding:2px 6px;border-radius:3px;font-size:11px;font-weight:700;color:#1a1a1a;white-space:nowrap;border:1px solid #b8860b;">FACA — Cape Town FIR</div>'});
        var jnbLabel = L.divIcon({className: '', html: '<div style="background:rgba(255,255,255,0.85);padding:2px 6px;border-radius:3px;font-size:11px;font-weight:700;color:#1a1a1a;white-space:nowrap;border:1px solid #b8860b;">FAJA — Johannesburg FIR</div>'});
        L.marker([-33, 20], {icon: ctLabel, interactive: false}).addTo(firMap);
        L.marker([-26, 28], {icon: jnbLabel, interactive: false}).addTo(firMap);

        // Airfield markers
        var smallDot = function(color) {
            return L.divIcon({className: '', html: '<div style="width:8px;height:8px;background:'+color+';border-radius:50%;border:1px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.3);"></div>', iconSize: [8,8], iconAnchor: [4,4]});
        };
        cards.forEach(function(card) {
            var lat = parseFloat(card.dataset.lat);
            var lon = parseFloat(card.dataset.lon);
            if (isNaN(lat) || isNaN(lon)) return;
            var name = (card.querySelector('h3') || {}).textContent || '';
            var color = lat < -29.5 ? '#276749' : '#b8860b';
            var marker = L.marker([lat, lon], {icon: smallDot(color)}).addTo(firMap);
            marker.bindTooltip(name, {direction: 'top', offset: [0, -6]});
            marker.on('click', function() {
                card.scrollIntoView({behavior: 'smooth', block: 'center'});
                card.style.boxShadow = '0 0 0 3px var(--blue), 0 2px 8px rgba(0,0,0,0.12)';
                setTimeout(function() { card.style.boxShadow = ''; }, 2000);
            });
        });

        // Fix map tiles when section becomes visible
        setTimeout(function() { firMap.invalidateSize(); }, 100);
        var firSection = document.getElementById('fir-section');
        if (firSection) {
            var obs = new MutationObserver(function() { firMap.invalidateSize(); });
            obs.observe(firSection, {attributes: true, attributeFilter: ['class']});
        }
    }
});
"""


# Tower / ATC phone numbers (from SA AIP, vfrPlanner, ATNS sources)
TOWER_PHONES = {
    'FAOR': '+27 11 921 6262',     # OR Tambo — airport helpdesk (tower direct not public)
    'FACT': '+27 21 937 1122',     # Cape Town — ATC tower (AIP GEN 3.4)
    'FALE': '+27 32 436 5001',     # King Shaka — ATC tower (vfrPlanner)
    'FALA': '+27 11 701 3278',     # Lanseria — ATC tower (vfrPlanner)
    'FAGC': '+27 11 805 3166',     # Grand Central — ATS (vfrPlanner)
    'FAWB': '+27 12 543 1402',     # Wonderboom — tower (pilot forum)
    'FAGM': '+27 11 827 8884',     # Rand Airport
    'FABL': '+27 51 433 1452',     # Bram Fischer — ATC tower (vfrPlanner)
    'FAPE': '+27 41 513 5851',     # Chief Dawid Stuurman — tower (AIP GEN 3.4)
    'FAEL': '+27 43 736 6161',     # King Phalo / East London — tower (vfrPlanner)
    'FAGG': '+27 44 803 7732',     # George — ATC tower (verified)
    'FAKM': '+27 53 851 1012',     # Kimberley — tower (vfrPlanner)
    'FAUP': '+27 54 337 7900',     # Upington — airport (tower direct not public)
    'FAKN': '+27 13 753 7519',     # Kruger Mpumalanga — ATC tower (kmiairport.co.za)
    'FAPP': '+27 15 288 0343',     # Polokwane Gateway — tower (AcuKwik)
    'FAPM': '+27 33 392 3110',     # Pietermaritzburg — tower (SA AIP AD 2)
    'FARB': '+27 35 786 0836',     # Richards Bay
    'FAHS': '+27 15 799 2251',     # Hoedspruit AFB — approach (SA AIP AD 2)
    'FAMY': '+27 22 487 3571',     # Malmesbury
    'FASK': '+27 12 671 2001',     # Swartkop AFB (military)
    'FAWK': '+27 12 672 3100',     # Waterkloof AFB (military)
}


def build_airfield_card(airfield, embed_diagrams=False, pdf_filename=None):
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
    import re as _re
    has_icao = bool(_re.search(r'\bFA[A-Z]{2}\b', code_clean))
    official_attr = '1' if has_icao else '0'

    filter_attrs = f' data-fuel="{has_fuel}" data-night="{has_night}" data-surface="{surface_attr}" data-access="{access_type}" data-towered="{towered_attr}" data-official="{official_attr}"'

    html = f'<div class="airfield-card" id="af-{airfield["number"]}" data-search="{escape(search_text)}"{coord_attrs}{filter_attrs}>\n'
    html += f'  <div class="airfield-header {header_class}">\n'
    html += f'    <h3>{escape(name)}</h3>\n'
    html += f'    <span class="dist-badge"></span>\n'
    if pdf_filename:
        html += f'    <a class="pdf-dl" href="airfield-pdfs/{pdf_filename}" download title="Download PDF info sheet">&#8681;</a>\n'
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


def generate_html(airfields, output_path, embed_diagrams=False, download_links=None, freq_tables=None, pdf_mapping=None):
    """Generate a complete searchable HTML file.

    Args:
        airfields: List of parsed airfield dicts.
        output_path: Where to write the HTML file.
        embed_diagrams: If True, base64-encode diagram images into the HTML.
        download_links: Optional list of dicts with 'label', 'href' keys for download bar.
        freq_tables: Optional list of regional frequency table dicts from parse_frequency_tables().
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
    if freq_tables:
        html += '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin=""/>\n'
        html += '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>\n'
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
    html += '<span class="filter-sep"></span>\n'
    html += '<span class="filter-label">Sort:</span>\n'
    html += '<button class="filter-btn sort-btn active" data-sort="province">Province</button>\n'
    html += '<button class="filter-btn sort-btn" data-sort="alpha">A\u2013Z</button>\n'
    html += '<button class="filter-btn sort-btn" id="nearby-btn" style="display:none;" data-sort="nearest">Nearest</button>\n'
    html += '<span id="filter-count"></span>\n'
    html += '<span id="search-count"></span>\n'
    html += f'<span class="updated">Updated {build_date}</span>\n'
    html += '</div>\n'
    html += '</header>\n'

    html += '<div class="container">\n'

    # Sort index (A-Z / Nearest, populated by JS)
    html += '<div id="sort-index"><h2>Airfield Index</h2><div class="sort-index-grid"></div></div>\n'

    # Nearby airfields panel (hidden until activated)
    html += '<div id="nearby-panel">\n'
    html += '<h2>Nearest Airfields</h2>\n'
    html += '<div id="nearby-status" class="nearby-status"></div>\n'
    html += '<ul id="nearby-list" class="nearby-list"></ul>\n'
    html += '</div>\n'

    # FIR Frequencies section (map + tabbed frequency tables)
    if freq_tables:
        # FIR-level frequencies organised by region
        cape_town_fir = [
            ['Cape Town Information (FIS)', '131.125'],
            ['Cape Town ACC (CTA)', '125.100'],
            ['Cape Town SRA West', '125.800'],
            ['Cape Town SRA East / TIBA', '124.800'],
        ]
        johannesburg_fir = [
            ['Johannesburg ACC North', '126.700'],
            ['Johannesburg ACC South', '128.300'],
            ['Johannesburg ACC East', '129.100'],
            ['Johannesburg ACC West', '118.500'],
            ['Johannesburg ACC Central', '120.300'],
        ]
        common_freqs = [
            ['Emergency (Guard)', '121.500'],
            ['SAR (Search &amp; Rescue)', '123.100'],
            ['Air-to-Air', '130.350'],
        ]

        html += '<div class="fir-section" id="fir-section">\n'
        html += '<h2 onclick="this.parentElement.classList.toggle(\'collapsed\')">FIR Frequencies &amp; Map &#9662;</h2>\n'
        html += '<div class="fir-body">\n'
        html += '<div id="fir-map" class="fir-map"></div>\n'

        # Tabs
        html += '<div class="fir-tabs">\n'
        html += '<button class="fir-tab active" data-fir-tab="fir-general">FIR Overview</button>\n'
        for idx, ft in enumerate(freq_tables):
            tab_id = f'fir-tab-{idx}'
            html += f'<button class="fir-tab" data-fir-tab="{tab_id}">{escape(ft["name"])}</button>\n'
        html += '</div>\n'

        # FIR Overview tab content — grouped sub-tables
        html += '<div class="fir-tab-content active" id="fir-general">\n'

        html += '<h4 style="margin:12px 0 6px">Cape Town FIR (FACA)</h4>\n'
        html += '<table class="freq-table"><tr><th>Service</th><th>Frequency (MHz)</th></tr>\n'
        for row in cape_town_fir:
            html += f'<tr><td>{row[0]}</td><td>{row[1]}</td></tr>\n'
        html += '</table>\n'

        html += '<h4 style="margin:12px 0 6px">Johannesburg FIR (FAJA)</h4>\n'
        html += '<table class="freq-table"><tr><th>Service</th><th>Frequency (MHz)</th></tr>\n'
        for row in johannesburg_fir:
            html += f'<tr><td>{row[0]}</td><td>{row[1]}</td></tr>\n'
        html += '</table>\n'

        html += '<h4 style="margin:12px 0 6px">Common Frequencies</h4>\n'
        html += '<table class="freq-table"><tr><th>Service</th><th>Frequency (MHz)</th></tr>\n'
        for row in common_freqs:
            html += f'<tr><td>{row[0]}</td><td>{row[1]}</td></tr>\n'
        html += '</table>\n'

        html += '</div>\n'

        # Regional tab contents
        for idx, ft in enumerate(freq_tables):
            tab_id = f'fir-tab-{idx}'
            html += f'<div class="fir-tab-content" id="{tab_id}">\n'
            html += '<table class="freq-table"><tr><th>Service</th><th>Frequency (MHz)</th></tr>\n'
            for row in ft['rows']:
                html += f'<tr><td>{escape(row[0])}</td><td>{escape(row[1])}</td></tr>\n'
            html += '</table>\n'
            if ft.get('note'):
                html += f'<div class="fir-tab-note">{escape(ft["note"])}</div>\n'
            html += '</div>\n'

        html += '</div>\n</div>\n'  # fir-body, fir-section

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
            code = af['fields'].get('ICAO', af['fields'].get('ICAO / Code', af['fields'].get('Code', '')))
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
        af_pdf = (pdf_mapping or {}).get(af['number'])
        html += build_airfield_card(af, embed_diagrams=embed_diagrams, pdf_filename=af_pdf)

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

    freq_tables = parse_frequency_tables(MD_FILE)
    print(f"  Found {len(freq_tables)} frequency tables")

    print("\nGenerating HTML (with linked diagrams)...")
    generate_html(airfields, OUTPUT_HTML, embed_diagrams=False, freq_tables=freq_tables)

    file_size = os.path.getsize(OUTPUT_HTML)
    print(f"File size: {file_size / 1024:.1f} KB")
