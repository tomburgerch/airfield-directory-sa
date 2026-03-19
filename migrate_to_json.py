#!/usr/bin/env python3
"""
migrate_to_json.py — Convert AIRFIELD_DIRECTORY.md to airfields.json.

Reads the markdown source, merges verified_facts.json and tower_data,
and writes airfields.json in the new structured schema.
"""

import json
import os
import re
import sys

from parse_markdown import parse_airfields, parse_frequency_tables
from shared import (
    AIRFIELDS_JSON,
    MD_FILE,
    get_icao,
    load_verified_facts,
    parse_dms_coord,
)
from tower_data import TOWER_PHONES
from diagrams_util import find_diagram

# ── Constants ─────────────────────────────────────────────────────────────────

MIGRATION_DATE = "2026-03-19"

SOURCE_REGISTRY = {
    "sacaa_aip": {
        "name": "SACAA AIP",
        "url_template": "https://caasanwebsitestorage.blob.core.windows.net/aerodrone-and-helicompter-directory/{icao}AD2.pdf",
        "authority": "official",
        "description": "South African Civil Aviation Authority Aeronautical Information Publication",
    },
    "ourairports": {
        "name": "OurAirports",
        "url_template": "https://ourairports.com/airports/{icao}/",
        "authority": "community",
        "license": "CC BY-SA 4.0",
    },
    "skyvector": {
        "name": "SkyVector",
        "url_template": "https://skyvector.com/airport/{icao}",
        "authority": "community",
    },
    "airportguide": {
        "name": "AirportGuide",
        "url_template": "https://airportguide.com/airport/info/{icao}",
        "authority": "community",
    },
    "avcom": {
        "name": "AvCom Forum",
        "url_base": "https://www.avcom.co.za/phpBB3/",
        "authority": "community",
    },
}

COMMUNITY_SOURCE = {
    "url": "https://www.avcom.co.za/phpBB3/",
    "name": "Community sources",
    "collected": MIGRATION_DATE,
}

AIP_SOURCE = {
    "id": "sacaa_aip",
    "collected": MIGRATION_DATE,
}

# Regex to detect an actual AIP hyperlink (not "Not in SACAA AIP")
_AIP_LINK_RE = re.compile(r'\[.*?\]\(https?://.*?\.pdf\)', re.IGNORECASE)

# Regex to extract markdown links [label](url)
_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')

# Website keys to scan in fields_raw for curated links
_WEBSITE_KEYS = ('Websites', 'Website')

# Additional link keys (non-AIP) to extract
_EXTRA_LINK_KEYS = ('Operator AIP',)

# Keys mapping to runway columns:  rwy, length, width, surface, strength, circuit
_RWY_KEYS = ('rwy', 'length', 'width', 'surface', 'strength', 'circuit')


# ── Helper functions ──────────────────────────────────────────────────────────

def _clean_icao(raw_icao):
    """Extract just the ICAO/code from a string like 'FAWN (previously FAFK)' or 'ZA-0120 (note)'."""
    if not raw_icao:
        return ''
    # Try FA-series first
    m = re.match(r'(FA[A-Z]{2,4})\b', raw_icao.strip())
    if m:
        return m.group(1)
    # Try ZA-series
    m = re.match(r'(ZA-\d+)', raw_icao.strip())
    if m:
        return m.group(1)
    # Fall back to first token
    return raw_icao.strip().split()[0].split('(')[0].strip()


def _clean_circuit(val):
    """Clean circuit direction string — strip emoji prefixes.

    Returns 'Left', 'Right', or None if unresolvable.
    The schema only allows Left/Right/left/right; unknown values must be omitted.
    """
    if not val:
        return None
    # Strip all emoji characters (including variation selectors)
    cleaned = re.sub(r'[\U00002600-\U0001ffff\ufe0f]+', '', val).strip()
    # Normalise to capitalised form
    low = cleaned.lower()
    if low.startswith('left'):
        return 'Left'
    if low.startswith('right'):
        return 'Right'
    # Unresolvable (e.g. "N/A", empty after stripping)
    return None


def _convert_night_ops(value):
    """Convert Night Ops string to boolean or None."""
    if not value:
        return None
    val_lower = value.lower().strip()
    # Strip leading emoji
    val_lower = re.sub(r'^[🚫🌙\U0001f6ab\U0001f319\s]+', '', val_lower).strip()
    if val_lower.startswith('no'):
        return False
    if val_lower.startswith('yes') or 'available' in val_lower or 'remote-activated' in val_lower:
        return True
    return None


def _parse_contact(contact_str):
    """Parse contact string into name/phone dict."""
    if not contact_str:
        return {"name": None, "phone": None}
    # Try to split by common delimiters
    name = contact_str
    phone = None
    # Look for TEL: pattern
    tel_m = re.search(r'TEL:\s*([^\s,]+(?:\s*/\s*[^\s,]+)*)', contact_str)
    if tel_m:
        phone = tel_m.group(1).strip()
    # The name is everything before the first comma or TEL
    parts = re.split(r',\s*(?:P\s*O\s*Box|TEL:)', contact_str, maxsplit=1)
    if parts:
        name = parts[0].strip()
    return {"name": name if name else None, "phone": phone}


# ── Core migration functions ──────────────────────────────────────────────────

def determine_status(name, fields):
    """Determine airfield status from name and fields.

    Returns: 'active' | 'closed' | 'military' | 'decommissioned'
    """
    name_upper = name.upper()
    access = (fields.get('Access', '') or '').upper()

    # Closed indicators
    if 'CLOSED' in name_upper or '[X]' in name_upper:
        return 'closed'
    if 'CLOSED' in access:
        return 'closed'
    if 'DECOMMISSIONED' in name_upper or 'DECOMMISSIONED' in access:
        return 'decommissioned'

    # Military
    if 'MILITARY' in access or 'SAAF' in access:
        return 'military'

    return 'active'


def build_source_for_field(icao, fields_raw):
    """Build a source object for a field group.

    FA-series with an actual AIP hyperlink → sacaa_aip source.
    Otherwise → generic community source.
    """
    aip_raw = fields_raw.get('AIP Link', '')
    has_aip_link = bool(_AIP_LINK_RE.search(aip_raw))

    if has_aip_link:
        return dict(AIP_SOURCE)
    else:
        return dict(COMMUNITY_SOURCE)


def extract_websites_from_raw(fields_raw):
    """Extract website links from fields_raw markdown.

    Scans 'Websites', 'Website', and 'Operator AIP' keys.
    Does NOT include 'AIP Link' (that's used for source determination).

    Returns: list of {"label": ..., "url": ...}
    """
    websites = []
    for key in list(_WEBSITE_KEYS) + list(_EXTRA_LINK_KEYS):
        val = fields_raw.get(key, '')
        if not val:
            continue
        for m in _MD_LINK_RE.finditer(val):
            websites.append({"label": m.group(1), "url": m.group(2)})
    return websites


def build_meta(freq_tables):
    """Build the meta object with source registry and frequency tables."""
    meta = {
        "version": "2.0",
        "last_full_scan": MIGRATION_DATE,
        "source_registry": SOURCE_REGISTRY,
    }
    if freq_tables:
        meta["frequency_tables"] = freq_tables
    return meta


def _convert_runways(raw_runways, source):
    """Convert list-of-lists runway data to list-of-dicts."""
    data = []
    for row in raw_runways:
        entry = {}
        for i, key in enumerate(_RWY_KEYS):
            if i < len(row):
                val = row[i]
                if key == 'circuit':
                    val = _clean_circuit(val)
                    if val is None:
                        continue  # Omit unknown circuit directions
                entry[key] = val
        if entry.get('rwy'):
            data.append(entry)
    return {"data": data, "source": source}


def _convert_frequencies_table(freq_table):
    """Convert frequencies table rows to list-of-dicts."""
    result = []
    for row in freq_table:
        if len(row) >= 2:
            entry = {"service": row[0], "freq": row[1]}
            if len(row) >= 3 and row[2]:
                entry["remarks"] = row[2]
            result.append(entry)
    return result


def migrate_airfield(af, verified_facts, tower_phones):
    """Migrate a single airfield dict from the old parsed format to the new JSON schema.

    Args:
        af: Airfield dict from parse_markdown.parse_airfields()
        verified_facts: Dict keyed by airfield number (int) from load_verified_facts()
        tower_phones: Dict keyed by ICAO code from tower_data.TOWER_PHONES

    Returns:
        dict: Airfield in the new JSON schema format.
    """
    fields = af.get('fields', {})
    fields_raw = af.get('fields_raw', {})
    name = af['name']
    number = af['number']

    # Extract and clean ICAO
    raw_icao = get_icao(af)
    icao = _clean_icao(raw_icao)

    # Determine source
    source = build_source_for_field(icao, fields_raw)

    # Determine status
    status = determine_status(name, fields)

    # Parse coordinates
    coord_str = fields.get('Coordinates', '')
    lat, lon = parse_dms_coord(coord_str)
    coordinates = None
    if lat is not None and lon is not None:
        coordinates = {"lat": lat, "lon": lon, "dms": coord_str.split('(')[0].strip()}

    # Basic info — elevation, mag_var, ref_temp are non-nullable strings;
    # omit them when the value is absent rather than setting to None.
    basic_info = {"source": dict(source)}
    if coordinates is not None:
        basic_info["coordinates"] = coordinates
    for bi_key, bi_field in [("elevation", "Elevation"), ("mag_var", "Mag Var"), ("ref_temp", "Ref Temp")]:
        val = fields.get(bi_field)
        if val:
            basic_info[bi_key] = val

    # Operations — access is a non-nullable string; the rest allow null.
    night_ops_raw = fields.get('Night Ops', '')
    operations = {
        "hours": fields.get('Hours') or fields.get('Operating Hours'),
        "fuel": fields.get('Fuel'),
        "fuel_hours": fields.get('Fuel Hours') or fields.get('Fuel Bay Hours'),
        "night_ops": _convert_night_ops(night_ops_raw),
        "fire_cat": fields.get('Fire Cat'),
        "joining_alt": fields.get('Joining Alt'),
        "circuit_alt": fields.get('Circuit Alt') or fields.get('Pattern Alt'),
        "source": dict(source),
    }
    access_val = fields.get('Access')
    if access_val:
        operations["access"] = access_val

    # Communications
    freq_raw = fields.get('Frequencies', '')
    primary_freq = None
    if freq_raw:
        # Extract the MHz value
        freq_m = re.search(r'(\d{2,3}\.\d+\s*MHz)', freq_raw)
        if freq_m:
            primary_freq = freq_m.group(1)

    freq_table = _convert_frequencies_table(af.get('frequencies_table', []))

    tower_phone = tower_phones.get(icao)

    communications = {
        "primary_freq": primary_freq,
        "frequencies_table": freq_table,
        "tower_phone": tower_phone,
        "source": dict(source),
    }

    # Runways
    runways = _convert_runways(af.get('runways', []), dict(source))

    # Notes — each gets its own source
    notes = [{"text": n, "source": dict(source)} for n in af.get('notes', [])]

    # Warnings — each gets its own source
    warnings = [{"text": w, "source": dict(source)} for w in af.get('warnings', [])]

    # Contact
    contact_parsed = _parse_contact(af.get('contact', ''))
    contact = {
        "name": contact_parsed.get('name'),
        "phone": contact_parsed.get('phone'),
        "source": dict(source),
    }

    # Links
    websites = extract_websites_from_raw(fields_raw)
    links = {"websites": websites} if websites else {"websites": []}

    # Diagram
    diagram_path = find_diagram(af)
    diagram = None
    if diagram_path:
        # Convert absolute path to relative
        base_dir = os.path.dirname(os.path.abspath(__file__))
        rel_path = os.path.relpath(diagram_path, base_dir)
        diagram = {"file": rel_path, "source": dict(source)}

    # Merge verified facts
    vf = verified_facts.get(number)
    if vf:
        # Bake verified notes into the notes list
        if 'verified_notes' in vf:
            vf_source = dict(source)
            if 'verified_date' in vf:
                vf_source = {
                    "url": "https://www.avcom.co.za/phpBB3/",
                    "name": vf.get('source', 'Verified fact'),
                    "collected": vf['verified_date'],
                    "verified": True,
                }
            existing_texts = {n['text'] for n in notes}
            for vn in vf['verified_notes']:
                if vn not in existing_texts:
                    notes.insert(0, {"text": vn, "source": vf_source})

    # Build the entry
    entry = {
        "number": number,
        "name": name,
        "icao": icao,
        "group": af.get('group', ''),
        "status": status,
        "basic_info": basic_info,
        "operations": operations,
        "communications": communications,
        "runways": runways,
        "notes": notes,
        "warnings": warnings,
        "contact": contact,
        "links": links,
        "notams": [],
    }

    if diagram:
        entry["diagram"] = diagram

    return entry


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    """Run the full migration."""
    print(f"Migration date: {MIGRATION_DATE}")
    print(f"Parsing {MD_FILE} ...")

    airfields = parse_airfields(MD_FILE)
    freq_tables = parse_frequency_tables(MD_FILE)
    verified_facts = load_verified_facts()

    print(f"  Parsed {len(airfields)} airfields")
    print(f"  Parsed {len(freq_tables)} frequency tables")
    print(f"  Loaded {len(verified_facts)} verified facts")
    print(f"  Tower phones for {len(TOWER_PHONES)} airfields")

    # Build meta
    meta = build_meta(freq_tables)

    # Migrate each airfield
    migrated = []
    warnings_count = 0
    no_coords = 0
    no_icao = 0
    closed_count = 0
    military_count = 0

    for af in airfields:
        entry = migrate_airfield(af, verified_facts, TOWER_PHONES)
        migrated.append(entry)

        # Stats
        if entry['status'] == 'closed':
            closed_count += 1
        elif entry['status'] == 'military':
            military_count += 1
        if not entry['basic_info'].get('coordinates'):
            no_coords += 1
        if not entry['icao']:
            no_icao += 1
        warnings_count += len(entry['warnings'])

    # Build output
    output = {
        "meta": meta,
        "airfields": migrated,
    }

    # Write JSON
    with open(AIRFIELDS_JSON, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    file_size = os.path.getsize(AIRFIELDS_JSON)

    # Summary
    print(f"\n{'='*60}")
    print(f"Migration complete!")
    print(f"{'='*60}")
    print(f"  Total airfields:   {len(migrated)}")
    print(f"  Active:            {len(migrated) - closed_count - military_count}")
    print(f"  Closed:            {closed_count}")
    print(f"  Military:          {military_count}")
    print(f"  With coordinates:  {len(migrated) - no_coords}")
    print(f"  Without coords:    {no_coords}")
    print(f"  Without ICAO:      {no_icao}")
    print(f"  Total warnings:    {warnings_count}")
    print(f"  Frequency tables:  {len(freq_tables)}")
    print(f"  Output:            {AIRFIELDS_JSON}")
    print(f"  File size:         {file_size:,} bytes")
    print(f"{'='*60}")

    return output


if __name__ == '__main__':
    main()
