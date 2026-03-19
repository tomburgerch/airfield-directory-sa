#!/usr/bin/env python3
"""
Generate markdown from airfields.json — for Notion import and offline reference.
"""

import json
import os
import re

from shared import AIRFIELDS_JSON, BASE_DIR


def generate_markdown_for_airfield(af):
    """Generate markdown for a single airfield entry."""
    lines = []

    name = af['name']
    number = af['number']
    icao = af.get('icao', '')
    status = af.get('status', 'active')

    lines.append(f"### {number}. {name}")
    lines.append("")

    if status == 'closed':
        lines.append("> **CLOSED — DO NOT PLAN OPERATIONS**")
        lines.append("")

    # Info table
    basic = af.get('basic_info', {})
    ops = af.get('operations', {})
    comms = af.get('communications', {})

    lines.append("| Field | Value |")
    lines.append("|-------|-------|")

    if icao:
        lines.append(f"| ICAO / Code | {icao} |")

    coords = basic.get('coordinates', {})
    if coords.get('dms'):
        lines.append(f"| Coordinates | {coords['dms']} |")
    if basic.get('elevation'):
        lines.append(f"| Elevation | {basic['elevation']} |")
    if basic.get('mag_var'):
        lines.append(f"| Mag Var | {basic['mag_var']} |")
    if comms.get('primary_freq'):
        lines.append(f"| Frequency | {comms['primary_freq']} |")
    if ops.get('access'):
        lines.append(f"| Access | {ops['access']} |")
    if ops.get('joining_alt'):
        lines.append(f"| Joining Alt | {ops['joining_alt']} |")
    if ops.get('circuit_alt'):
        lines.append(f"| Circuit Alt | {ops['circuit_alt']} |")
    if ops.get('fuel'):
        lines.append(f"| Fuel | {ops['fuel']} |")
    if ops.get('hours'):
        lines.append(f"| Hours | {ops['hours']} |")
    night_val = ops.get('night_ops')
    if night_val is not None and night_val is not False:
        night_str = str(night_val) if night_val is not True else 'Yes'
        lines.append(f"| Night Ops | {night_str} |")
    if ops.get('fire_cat'):
        lines.append(f"| Fire Cat | {ops['fire_cat']} |")

    lines.append("")

    # Runways
    runways = af.get('runways', {}).get('data', [])
    if runways:
        has_width = any(r.get('width') for r in runways)
        has_strength = any(r.get('strength') for r in runways)
        has_circuit = any(r.get('circuit') for r in runways)

        headers = ['RWY', 'Length']
        keys = ['rwy', 'length']
        if has_width:
            headers.append('Width')
            keys.append('width')
        headers.append('Surface')
        keys.append('surface')
        if has_strength:
            headers.append('Strength')
            keys.append('strength')
        if has_circuit:
            headers.append('Circuit')
            keys.append('circuit')

        lines.append("**Runways**")
        lines.append("")
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for rwy in runways:
            vals = [rwy.get(k, '') or '' for k in keys]
            lines.append("| " + " | ".join(vals) + " |")
        lines.append("")

    # Warnings
    for w in af.get('warnings', []):
        w_text = w.get('text', w) if isinstance(w, dict) else w
        lines.append(f"**⚠️ {w_text}**")
    if af.get('warnings'):
        lines.append("")

    # Notes
    for note in af.get('notes', []):
        n_text = note.get('text', note) if isinstance(note, dict) else note
        lines.append(f"- {n_text}")
    if af.get('notes'):
        lines.append("")

    # Contact
    contact = af.get('contact', {})
    if isinstance(contact, dict):
        parts = [v for v in [contact.get('name'), contact.get('phone'), contact.get('address')] if v]
        if parts:
            lines.append(f"**Contact:** {', '.join(parts)}")
            lines.append("")

    # Links
    websites = af.get('links', {}).get('websites', [])
    if websites:
        for site in websites:
            lines.append(f"- [{site.get('label', 'Link')}]({site.get('url', '')})")
        lines.append("")

    # Sources section
    collected_dates = []
    source_names = set()
    for section in ['basic_info', 'operations', 'communications', 'runways']:
        src = af.get(section, {}).get('source', {})
        if src.get('collected'):
            collected_dates.append(src['collected'])
        if src.get('id'):
            source_names.add(src['id'])
        elif src.get('name'):
            source_names.add(src['name'])

    is_fa = bool(re.search(r'\bFA[A-Z]{2}\b', icao))
    if collected_dates:
        earliest = min(collected_dates)
        if is_fa:
            lines.append(f"*Source: SACAA AIP (collected {earliest})*")
        else:
            names = ', '.join(sorted(source_names)) if source_names else 'community sources'
            lines.append(f"*Sources: {names} (collected {earliest})*")
        lines.append("")

    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def generate_markdown(airfields, meta=None):
    """Generate complete markdown document from JSON airfield data."""
    lines = []

    lines.append("# SA Airfield Directory")
    lines.append("")
    scan_date = (meta or {}).get('last_full_scan', '')
    if scan_date:
        lines.append(f"*Data collected: {scan_date}*")
    lines.append(f"*{len(airfields)} airfields*")
    lines.append("")
    lines.append("> **DISCLAIMER:** Supplementary reference only. Does NOT replace SACAA AIP, NOTAMs, or official charts.")
    lines.append("")
    lines.append("---")
    lines.append("")

    current_group = ''
    for af in airfields:
        group = af.get('group', '')
        if group and group != current_group:
            current_group = group
            lines.append(f"## {group}")
            lines.append("")
        lines.append(generate_markdown_for_airfield(af))

    return "\n".join(lines)


if __name__ == '__main__':
    print("Loading airfield data from JSON...")
    with open(AIRFIELDS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    meta, airfields = data['meta'], data['airfields']

    md = generate_markdown(airfields, meta)
    output_path = os.path.join(BASE_DIR, 'AIRFIELD_DIRECTORY_generated.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"Generated {output_path} ({len(airfields)} airfields)")
