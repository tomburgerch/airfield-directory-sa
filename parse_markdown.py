#!/usr/bin/env python3
"""
Parse AIRFIELD_DIRECTORY.md and extract structured airfield data.
"""

import re
import os

from shared import MD_FILE, get_icao


def parse_airfields(md_path=MD_FILE):
    """Parse the markdown file and extract airfield data."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by airfield headers (### N. NAME)
    airfield_pattern = r'^### (\d+)\. (.+?)$'
    sections = re.split(r'^### \d+\.', content, flags=re.MULTILINE)
    headers = re.findall(airfield_pattern, content, re.MULTILINE)

    airfields = []

    # Extract group headings (## PROVINCE NAME)
    group_pattern = r'^## ([A-Z][A-Z \-/&]+)$'
    group_positions = [(m.start(), m.group(1).strip()) for m in re.finditer(group_pattern, content, re.MULTILINE)]

    for i, (num, name) in enumerate(headers):
        section = sections[i + 1] if i + 1 < len(sections) else ""
        first_line = section.split('\n')[0].strip()
        full_name = first_line.lstrip('. ').strip()

        airfield = parse_single_airfield(num, full_name, section)

        # Find which group this airfield belongs to
        header_pos = content.find(f'### {num}. ')
        for gpos, gname in reversed(group_positions):
            if gpos < header_pos:
                airfield['group'] = gname
                break

        airfields.append(airfield)

    return airfields


def parse_single_airfield(num, name, section):
    """Parse a single airfield section."""
    data = {
        'number': int(num),
        'name': name,
        'group': '',
        'fields': {},
        'fields_raw': {},
        'runways': [],
        'notes': [],
        'frequencies_table': [],
        'contact': '',
        'warnings': [],
    }

    lines = section.split('\n')

    # Extract table fields (| **Key** | Value |)
    field_pattern = r'\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|'
    for line in lines:
        m = re.match(field_pattern, line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            data['fields_raw'][key] = val
            val = re.sub(r'\*\*(.+?)\*\*', r'\1', val)
            val = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', val)
            data['fields'][key] = val

    # Extract runway table rows
    rwy_section = False
    rwy_headers_found = False
    for line in lines:
        if '**Runways' in line:
            rwy_section = True
            continue
        if rwy_section and re.match(r'\|\s*RWY\s*\|', line):
            rwy_headers_found = True
            continue
        if rwy_section and rwy_headers_found and re.match(r'\|\s*-', line):
            continue
        if rwy_section and rwy_headers_found and line.startswith('|'):
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if cols and cols[0] and not cols[0].startswith('-'):
                data['runways'].append(cols)
        elif rwy_section and rwy_headers_found and not line.startswith('|') and line.strip():
            if '**Notes' in line or '**Contact' in line or line.startswith('---'):
                rwy_section = False

    # Extract frequencies table (standalone section, not inline field rows)
    freq_section = False
    for line in lines:
        if ('**Frequencies:**' in line or '**Frequencies**' in line) and not re.match(r'\|\s*\*\*', line):
            freq_section = True
            continue
        if freq_section and re.match(r'\|\s*Service\s*\|', line):
            continue
        if freq_section and re.match(r'\|\s*-', line):
            continue
        if freq_section and line.startswith('|'):
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if len(cols) >= 2 and cols[0]:
                data['frequencies_table'].append(cols)
        elif freq_section and not line.startswith('|') and line.strip():
            freq_section = False

    # Extract notes
    note_section = False
    for line in lines:
        if line.strip().startswith('**Notes:**') or line.strip().startswith('**Notes**'):
            note_section = True
            continue
        if note_section and line.strip().startswith('- '):
            note = line.strip()[2:]
            note = re.sub(r'\*\*(.+?)\*\*', r'\1', note)
            note = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', note)
            if note.startswith(('WARNING', 'CAUTION')) or '⚠️' in note or '⛔' in note:
                data['warnings'].append(note)
            else:
                data['notes'].append(note)
        elif note_section and line.strip().startswith('---'):
            note_section = False

    # Extract contact
    for line in lines:
        if line.strip().startswith('**Contact:**'):
            data['contact'] = line.strip().replace('**Contact:**', '').strip()
            data['contact'] = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', data['contact'])

    return data


if __name__ == '__main__':
    airfields = parse_airfields()
    print(f"Parsed {len(airfields)} airfields")
    for af in airfields:
        code = get_icao(af) or '?'
        print(f"  #{af['number']:2d}  {af['name'][:40]:<40s}  {code[:12]}")
