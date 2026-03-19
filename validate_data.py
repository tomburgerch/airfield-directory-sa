#!/usr/bin/env python3
"""
Validate airfield data for consistency, completeness, and freshness.
Parses AIRFIELD_DIRECTORY.md and reports issues.
"""

import re
import sys
import os
from datetime import datetime, timedelta

from parse_markdown import parse_airfields
from shared import MD_FILE, DIAGRAMS_DIR, parse_dms_coord, get_icao

# South Africa bounding box (generous)
WC_LAT_MIN, WC_LAT_MAX = -35.0, -22.0  # S35 to S22
WC_LON_MIN, WC_LON_MAX = 16.0, 33.0    # E16 to E33

REQUIRED_FIELDS = ['Coordinates', 'Elevation']
IMPORTANT_FIELDS = ['Frequencies', 'Access']

STALENESS_DAYS = 365  # Flag data older than this



# Keep parse_coordinate as an alias for backwards compatibility with tests
parse_coordinate = parse_dms_coord


def parse_airfields_for_validation(md_path):
    """Parse markdown for validation, extending the shared parser with extra fields.

    Adds 'section' (raw markdown text), 'unverified_count', 'dates_mentioned',
    and 'raw_name' on top of the base parse_airfields() output.
    """
    # Get base airfield data from shared parser
    base_airfields = parse_airfields(md_path)

    # Re-read markdown to extract raw sections for validation-specific fields
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    airfield_pattern = r'^### (\d+)\. (.+?)$'
    sections = re.split(r'^### \d+\.', content, flags=re.MULTILINE)
    headers = re.findall(airfield_pattern, content, re.MULTILINE)

    # Build section lookup by number
    section_map = {}
    for i, (num, name) in enumerate(headers):
        section = sections[i + 1] if i + 1 < len(sections) else ""
        section_map[int(num)] = (name.strip(), section)

    # Enrich base airfields with validation-specific fields
    airfields = []
    for af in base_airfields:
        raw_name, section = section_map.get(af['number'], ('', ''))
        af['raw_name'] = raw_name
        af['section'] = section
        af['unverified_count'] = section.count('❓')
        date_matches = re.findall(r'(\d{4})-(\d{2})-(\d{2})', section)
        date_matches += re.findall(r'\((\d{4})\)', section)
        af['dates_mentioned'] = date_matches
        airfields.append(af)

    return airfields


def validate_icao(airfield):
    """Check ICAO code format."""
    issues = []
    icao = get_icao(airfield)
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

    lat, lon = parse_dms_coord(coords)
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
    icao = get_icao(airfield)
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
        icao = get_icao(af)
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


def validate_json_schema(json_path=None, schema_path=None):
    """Validate airfields.json against airfields.schema.json.

    Returns dict with 'valid' (bool) and 'errors' (list of error messages).
    """
    import json as _json
    from shared import AIRFIELDS_JSON, BASE_DIR as _BASE_DIR

    json_path = json_path or AIRFIELDS_JSON
    schema_path = schema_path or os.path.join(_BASE_DIR, 'airfields.schema.json')

    result = {'valid': True, 'errors': []}

    if not os.path.exists(json_path):
        result['valid'] = False
        result['errors'].append(f'File not found: {json_path}')
        return result

    if not os.path.exists(schema_path):
        result['valid'] = False
        result['errors'].append(f'Schema not found: {schema_path}')
        return result

    with open(json_path, 'r', encoding='utf-8') as f:
        data = _json.load(f)
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = _json.load(f)

    try:
        import jsonschema
        jsonschema.validate(data, schema)
    except ImportError:
        result['errors'].append('jsonschema package not installed — skipping schema validation')
        return result
    except jsonschema.ValidationError as e:
        result['valid'] = False
        result['errors'].append(f'Schema validation failed: {e.message}')
        if e.path:
            result['errors'].append(f'  at path: {"/".join(str(p) for p in e.path)}')

    # Basic structure checks
    airfields = data.get('airfields', [])
    if len(airfields) == 0:
        result['valid'] = False
        result['errors'].append('No airfields in JSON')
    elif len(airfields) < 100:
        result['errors'].append(f'Only {len(airfields)} airfields — expected ~276')

    return result


if __name__ == '__main__':
    # Run JSON validation first if available
    json_result = validate_json_schema()
    if json_result['errors']:
        print("JSON Schema Validation:")
        for err in json_result['errors']:
            print(f"  {err}")
        print()

    # Run legacy markdown validation
    results = run_validation()
    exit_code = print_report(results)
    sys.exit(exit_code)
