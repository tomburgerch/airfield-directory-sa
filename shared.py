#!/usr/bin/env python3
"""
Shared constants and utilities used across the airfield directory codebase.
"""

import os
import re

# ── Paths ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MD_FILE = os.path.join(BASE_DIR, 'AIRFIELD_DIRECTORY.md')
DIAGRAMS_DIR = os.path.join(BASE_DIR, 'diagrams')
OUTPUT_HTML = os.path.join(BASE_DIR, 'Airfield_Directory.html')
FAVICON_FILE = os.path.join(BASE_DIR, 'favicon.svg')


def parse_dms_coord(coord_str):
    """Parse DMS coordinate string like 'S33°45'44" E18°32'55"' to (lat, lon) decimal.

    Handles optional minutes/seconds, approximate markers (~), and trailing notes.
    Returns (None, None) if parsing fails.
    """
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


def get_icao(airfield):
    """Extract the ICAO/code string from an airfield dict's fields.

    Handles the various key names used in the markdown: 'ICAO', 'ICAO / Code', 'Code'.
    """
    fields = airfield.get('fields', airfield)
    return fields.get('ICAO', fields.get('ICAO / Code', fields.get('Code', '')))
