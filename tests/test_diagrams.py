"""Tests for diagram lookup utilities."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diagrams_util import find_diagram, DIAGRAMS_DIR
from parse_markdown import parse_airfields

MD_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'AIRFIELD_DIRECTORY.md')


@pytest.fixture(scope='module')
def airfields():
    return parse_airfields(MD_FILE)


class TestFindDiagram:
    def test_finds_diagram_by_icao(self, airfields):
        """Should find the diagram for FACT (Cape Town Intl), which ships a
        SACAA chart in diagrams/ (FACT_AD02.pdf → FACT_AD02.png)."""
        fact = next((af for af in airfields if 'FACT' in af['fields'].get('ICAO', '')), None)
        if fact is None:
            pytest.skip('FACT not in directory')
        path = find_diagram(fact)
        assert path is not None
        assert os.path.exists(path)
        assert 'FACT' in os.path.basename(path)

    def test_returns_none_for_unknown(self):
        """Should return None for airfield with no diagram."""
        fake = {
            'name': 'ZZZZZ Nonexistent Airfield',
            'fields': {'ICAO': 'ZZZZ'},
        }
        assert find_diagram(fake) is None

    def test_finds_multiple_known_diagrams(self, airfields):
        """Several well-known airfields should have diagrams."""
        known_codes = ['FACT', 'FAOR', 'FASH', 'FALE', 'FAKN']
        found = 0
        for code in known_codes:
            af = next((a for a in airfields if code in a['fields'].get('ICAO', '')), None)
            if af and find_diagram(af):
                found += 1
        assert found >= 2, f"Expected at least 2 diagrams for known airfields, found {found}"

    def test_diagram_files_are_valid_images(self):
        """All PNG files in diagrams/ should be valid PNG images."""
        png_files = [f for f in os.listdir(DIAGRAMS_DIR) if f.endswith('.png')]
        assert len(png_files) > 0, 'No PNG files in diagrams directory'
        for png in png_files[:10]:  # Check first 10
            path = os.path.join(DIAGRAMS_DIR, png)
            with open(path, 'rb') as f:
                header = f.read(8)
            # PNG magic bytes
            assert header[:4] == b'\x89PNG', f'{png} is not a valid PNG file'

    def test_diagrams_directory_exists(self):
        assert os.path.isdir(DIAGRAMS_DIR)


class TestDiagramCoverage:
    """Test that diagrams referenced in HTML actually exist."""

    def test_all_found_diagrams_exist(self, airfields):
        """Every diagram path returned by find_diagram should exist on disk."""
        missing = []
        for af in airfields:
            path = find_diagram(af)
            if path and not os.path.exists(path):
                missing.append((af['name'], path))
        assert missing == [], f"Missing diagram files: {missing}"

    def test_reasonable_diagram_coverage(self, airfields):
        """A meaningful set of airfields should resolve to a diagram.

        The directory expanded to the full WC/EC/KZN field-folio (~276
        airfields), most of which have no official SACAA aerodrome chart, so a
        percentage floor is no longer meaningful — assert an absolute count of
        successfully matched diagrams instead.
        """
        with_diagram = sum(1 for af in airfields if find_diagram(af))
        assert with_diagram >= 10, (
            f"Only {with_diagram} airfields resolved to a diagram (expected >= 10)"
        )
