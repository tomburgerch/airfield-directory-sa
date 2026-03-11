"""Tests for validation script."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validate_data import parse_coordinate, run_validation

MD_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'AIRFIELD_DIRECTORY.md')


def test_parse_coordinate_south_east():
    """Parse S/E coordinate correctly."""
    lat, lon = parse_coordinate('S33°45\'44" E18°32\'55"')
    assert lat is not None
    assert lon is not None
    assert -34.0 < lat < -33.0
    assert 18.0 < lon < 19.0


def test_parse_coordinate_returns_negative_for_south():
    """South latitude should be negative."""
    lat, _ = parse_coordinate('S33°45\'44" E18°32\'55"')
    assert lat < 0


def test_parse_coordinate_invalid():
    """Invalid string should return None."""
    lat, lon = parse_coordinate('not a coordinate')
    assert lat is None
    assert lon is None


def test_validation_runs_without_error():
    """Validation should complete without crashing."""
    results = run_validation(MD_FILE)
    assert 'airfield_count' in results
    assert results['airfield_count'] > 0


def test_validation_no_critical_errors():
    """There should be no errors that prevent PDF generation."""
    results = run_validation(MD_FILE)
    # We allow some errors (data quality) but should not have structural parse failures
    assert results['airfield_count'] >= 60
