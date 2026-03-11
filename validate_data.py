#!/usr/bin/env python3
"""
Validate airfield data for consistency, completeness, and freshness.
Parses AIRFIELD_DIRECTORY.md and reports issues.
"""

import re
import sys
import os
from datetime import datetime, timedelta

MD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'AIRFIELD_DIRECTORY.md')
DIAGRAMS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diagrams')

# South Africa bounding box (generous)
WC_LAT_MIN, WC_LAT_MAX = -35.0, -22.0  # S35 to S22
WC_LON_MIN, WC_LON_MAX = 16.0, 33.0    # E16 to E33

REQUIRED_FIELDS = ['Coordinates', 'Elevation']
IMPORTANT_FIELDS = ['Frequencies', 'Access']

STALENESS_DAYS = 365  # Flag data older than this


def parse_coordinate(coord_str):
    """Parse DMS coordinate string like S33°45'44\" E18°32'55\" to decimal."""
    pattern = r'([NS])(\d+)[°](\d+)[\'′](\d+(?:\.\d+)?)[\"″]?\s*([EW])(\d+)[°](\d+)[\'′](\d+(?:\.\d+)?)[\"″]?'
    m = re.search(pattern, coord_str)
    if not m:
        return None, None
    lat = int(m.group(2)) + int(m.group(3)) / 60 + float(m.group(4)) / 3600
    if m.group(1) == 'S':
        lat = -lat
    lon = int(m.group(6)) + int(m.group(7)) / 60 + float(m.group(8)) / 3600
    if m.group(5) == 'W':
        lon = -lon
    return lat, lon


def parse_airfields_for_validation(md_path):
    """Parse markdown and return list of airfield dicts for validation."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    airfield_pattern = r'^### (\d+)\. (.+?)$'
    sections = re.split(r'^### \d+\.', content, flags=re.MULTILINE)
    headers = re.findall(airfield_pattern, content, re.MULTILINE)

    airfields = []
    for i, (num, name) in enumerate(headers):
        section = sections[i + 1] if i + 1 < len(sections) else ""
        first_line = section.split('\n')[0].strip().lstrip('. ').strip()

        fields = {}
        field_pattern = r'\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|'
        for line in section.split('\n'):
            m = re.match(field_pattern, line)
            if m:
                fields[m.group(1).strip()] = m.group(2).strip()

        # Count unverified markers
        unverified_count = section.count('❓')

        # Find dates mentioned
        date_matches = re.findall(r'(\d{4})-(\d{2})-(\d{2})', section)
        date_matches += re.findall(r'\((\d{4})\)', section)

        airfields.append({
            'number': int(num),
            'name': first_line,
            'raw_name': name.strip(),
            'fields': fields,
            'section': section,
            'unverified_count': unverified_count,
            'dates_mentioned': date_matches,
        })

    return airfields


def validate_icao(airfield):
    """Check ICAO code format."""
    issues = []
    icao = airfield['fields'].get('ICAO', airfield['fields'].get('ICAO / Code', airfield['fields'].get('Code', '')))
    if not icao:
        issues.append(('warning', 'No ICAO code specified'))
        return issues

    # Extract FAXX-style codes
    fa_codes = re.findall(r'\b(FA[A-Z]{2,4})\b', icao.upper())
    za_codes = re.findall(r'\b(ZA-\d{4})\b', icao)

    if not fa_codes and not za_codes:
        issues.append(('info', f'Non-standard code format: {icao[:40]}'))

    for code in fa_codes:
        if len(code) != 4:
            issues.append(('warning', f'ICAO code {code} is not 4 characters'))

    return issues


def validate_coordinates(airfield):
    """Check coordinates are valid and within expected region."""
    issues = []
    coords = airfield['fields'].get('Coordinates', '')
    if not coords:
        issues.append(('error', 'Missing coordinates'))
        return issues

    lat, lon = parse_coordinate(coords)
    if lat is None:
        issues.append(('error', f'Could not parse coordinates: {coords[:50]}'))
        return issues

    if not (WC_LAT_MIN <= lat <= WC_LAT_MAX):
        issues.append(('warning', f'Latitude {lat:.4f} outside Western Cape range ({WC_LAT_MIN} to {WC_LAT_MAX})'))
    if not (WC_LON_MIN <= lon <= WC_LON_MAX):
        issues.append(('warning', f'Longitude {lon:.4f} outside Western Cape range ({WC_LON_MIN} to {WC_LON_MAX})'))

    return issues


def validate_frequency(airfield):
    """Check frequency format and range."""
    issues = []
    freq_str = airfield['fields'].get('Frequencies', airfield['fields'].get('Frequency', ''))
    if not freq_str:
        issues.append(('info', 'No frequency specified'))
        return issues

    # Extract MHz values
    freqs = re.findall(r'(\d{2,3}\.\d{1,3})\s*MHz', freq_str)
    for f in freqs:
        val = float(f)
        if not (108.0 <= val <= 137.0):
            issues.append(('error', f'Frequency {f} MHz outside aviation band (108-137 MHz)'))

    return issues


def validate_elevation(airfield):
    """Check elevation is reasonable."""
    issues = []
    elev_str = airfield['fields'].get('Elevation', '')
    if not elev_str:
        issues.append(('warning', 'Missing elevation'))
        return issues

    m = re.search(r'(\d[\d,]*)\s*ft', elev_str)
    if m:
        elev = int(m.group(1).replace(',', ''))
        if elev > 10000:
            issues.append(('warning', f'Elevation {elev} ft seems very high for Western Cape'))
        if elev < 0:
            issues.append(('error', f'Negative elevation: {elev} ft'))

    return issues


def validate_diagram(airfield):
    """Check if an aerodrome diagram exists."""
    issues = []
    icao = airfield['fields'].get('ICAO', airfield['fields'].get('ICAO / Code', airfield['fields'].get('Code', '')))
    if not icao:
        return issues

    fa_codes = re.findall(r'\b(FA[A-Z]{2,4})\b', icao.upper())
    has_diagram = False
    for code in fa_codes:
        for ext in ['.png', '.jpg']:
            for suffix in ['', '_AD01', '_AD02', '_chart']:
                path = os.path.join(DIAGRAMS_DIR, f'{code}{suffix}{ext}')
                if os.path.exists(path):
                    has_diagram = True
                    break

    if fa_codes and not has_diagram:
        issues.append(('info', f'No diagram found for {", ".join(fa_codes)}'))

    return issues


def check_freshness(airfield):
    """Check if data might be stale."""
    issues = []
    now = datetime.now()
    cutoff = now - timedelta(days=STALENESS_DAYS)

    # Check for explicit dates in format YYYY-MM-DD
    dates = []
    for match in re.finditer(r'(\d{4})-(\d{2})-(\d{2})', airfield['section']):
        try:
            d = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            dates.append(d)
        except ValueError:
            pass

    # Check for year-only mentions (e.g., "2014", "2020")
    year_mentions = re.findall(r'\b(20\d{2})\b', airfield['section'])
    for y in year_mentions:
        yr = int(y)
        if yr < cutoff.year:
            dates.append(datetime(yr, 6, 15))  # approximate mid-year

    if dates:
        newest = max(dates)
        if newest < cutoff:
            age_days = (now - newest).days
            issues.append(('warning', f'Most recent data reference is {age_days} days old ({newest.strftime("%Y-%m-%d")})'))

    if airfield['unverified_count'] > 3:
        issues.append(('warning', f'{airfield["unverified_count"]} unverified (❓) markers'))
    elif airfield['unverified_count'] > 0:
        issues.append(('info', f'{airfield["unverified_count"]} unverified (❓) marker(s)'))

    return issues


def check_duplicates(airfields):
    """Check for duplicate ICAO codes."""
    issues = []
    seen_codes = {}
    for af in airfields:
        icao = af['fields'].get('ICAO', af['fields'].get('ICAO / Code', af['fields'].get('Code', '')))
        fa_codes = re.findall(r'\b(FA[A-Z]{2,4})\b', icao.upper()) if icao else []
        for code in fa_codes:
            if code in seen_codes:
                issues.append(('error', f'Duplicate ICAO code {code}: #{seen_codes[code]} and #{af["number"]}'))
            else:
                seen_codes[code] = af['number']
    return issues


def run_validation(md_path=MD_FILE):
    """Run all validations and return structured results."""
    airfields = parse_airfields_for_validation(md_path)

    counts = {'error': 0, 'warning': 0, 'info': 0}

    results = {
        'airfield_count': len(airfields),
        'airfield_issues': [],
        'global_issues': [],
    }

    # Global checks
    dup_issues = check_duplicates(airfields)
    for level, msg in dup_issues:
        results['global_issues'].append((level, msg))
        counts[level] += 1

    # Per-airfield checks
    for af in airfields:
        af_issues = []
        for check_fn in [validate_icao, validate_coordinates, validate_frequency,
                         validate_elevation, validate_diagram, check_freshness]:
            af_issues.extend(check_fn(af))

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in af['fields']:
                af_issues.append(('error', f'Missing required field: {field}'))
        for field in IMPORTANT_FIELDS:
            if field not in af['fields']:
                af_issues.append(('info', f'Missing field: {field}'))

        if af_issues:
            results['airfield_issues'].append({
                'number': af['number'],
                'name': af['raw_name'],
                'issues': af_issues,
            })
            for level, _ in af_issues:
                counts[level] += 1

    results['errors'] = counts['error']
    results['warnings'] = counts['warning']
    results['info'] = counts['info']

    return results


def print_report(results):
    """Print a human-readable validation report."""
    print("=" * 60)
    print("AIRFIELD DATA VALIDATION REPORT")
    print("=" * 60)
    print(f"\nAirfields checked: {results['airfield_count']}")
    print(f"Errors:   {results['errors']}")
    print(f"Warnings: {results['warnings']}")
    print(f"Info:     {results['info']}")

    if results['global_issues']:
        print(f"\n{'─' * 60}")
        print("GLOBAL ISSUES:")
        for level, msg in results['global_issues']:
            icon = {'error': '[ERROR]', 'warning': '[WARN]', 'info': '[INFO]'}[level]
            print(f"  {icon} {msg}")

    if results['airfield_issues']:
        print(f"\n{'─' * 60}")
        print("PER-AIRFIELD ISSUES:")
        for af in results['airfield_issues']:
            errors = [i for i in af['issues'] if i[0] == 'error']
            warnings = [i for i in af['issues'] if i[0] == 'warning']
            infos = [i for i in af['issues'] if i[0] == 'info']

            # Only show header if there are errors or warnings
            if errors or warnings:
                print(f"\n  #{af['number']} {af['name']}")
                for level, msg in errors:
                    print(f"    [ERROR] {msg}")
                for level, msg in warnings:
                    print(f"    [WARN]  {msg}")
                for level, msg in infos:
                    print(f"    [INFO]  {msg}")

        # Summary of info-only airfields
        info_only = [af for af in results['airfield_issues']
                     if all(i[0] == 'info' for i in af['issues'])]
        if info_only:
            print(f"\n  ({len(info_only)} additional airfields with info-level notes only)")

    print(f"\n{'=' * 60}")
    if results['errors'] > 0:
        print("RESULT: FAIL — fix errors before generating PDF")
        return 1
    elif results['warnings'] > 0:
        print("RESULT: PASS with warnings — review before publishing")
        return 0
    else:
        print("RESULT: PASS")
        return 0


if __name__ == '__main__':
    results = run_validation()
    exit_code = print_report(results)
    sys.exit(exit_code)
