"""Tests for markdown parsing."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parse_markdown import parse_airfields

MD_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'AIRFIELD_DIRECTORY.md')


def test_parse_returns_airfields():
    """Parser should find airfields in the markdown file."""
    airfields = parse_airfields(MD_FILE)
    assert len(airfields) > 0, "Should parse at least one airfield"


def test_parse_minimum_count():
    """Should find at least 60 airfields (current count is ~70)."""
    airfields = parse_airfields(MD_FILE)
    assert len(airfields) >= 60, f"Expected >= 60 airfields, got {len(airfields)}"


def test_airfield_has_required_keys():
    """Each airfield dict should have the expected structure."""
    airfields = parse_airfields(MD_FILE)
    required_keys = ['number', 'name', 'group', 'fields', 'runways', 'notes', 'warnings']
    for af in airfields:
        for key in required_keys:
            assert key in af, f"Airfield #{af.get('number', '?')} missing key '{key}'"


def test_first_airfield_is_morningstar():
    """First airfield should be Morningstar."""
    airfields = parse_airfields(MD_FILE)
    assert airfields[0]['number'] == 1
    assert 'MORNINGSTAR' in airfields[0]['name'].upper()


def test_airfield_numbers_are_sequential():
    """Airfield numbers should be sequential starting from 1."""
    airfields = parse_airfields(MD_FILE)
    numbers = [af['number'] for af in airfields]
    assert numbers == list(range(1, len(numbers) + 1)), "Numbers should be sequential"


def test_groups_are_assigned():
    """Most airfields should belong to a group."""
    airfields = parse_airfields(MD_FILE)
    grouped = [af for af in airfields if af['group']]
    assert len(grouped) > len(airfields) * 0.9, "At least 90% of airfields should have a group"


def test_coordinates_present():
    """Most airfields should have coordinates."""
    airfields = parse_airfields(MD_FILE)
    with_coords = [af for af in airfields if 'Coordinates' in af['fields']]
    assert len(with_coords) > len(airfields) * 0.8, "At least 80% should have coordinates"


def test_stellenbosch_has_icao():
    """Stellenbosch should have ICAO code FASH."""
    airfields = parse_airfields(MD_FILE)
    stellenbosch = next((af for af in airfields if 'STELLENBOSCH' in af['name'].upper()), None)
    assert stellenbosch is not None, "Stellenbosch should be in the directory"
    icao = stellenbosch['fields'].get('ICAO', '')
    assert 'FASH' in icao, f"Stellenbosch ICAO should contain FASH, got '{icao}'"


def test_stellenbosch_has_runways():
    """Stellenbosch should have runway data."""
    airfields = parse_airfields(MD_FILE)
    stellenbosch = next(af for af in airfields if 'STELLENBOSCH' in af['name'].upper())
    assert len(stellenbosch['runways']) > 0, "Stellenbosch should have runway data"
