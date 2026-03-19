"""Tests for generate_markdown.py — JSON to markdown output."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_markdown import generate_markdown_for_airfield, generate_markdown


def test_generates_table_format():
    af = {
        "number": 1, "name": "TEST FIELD", "icao": "FATS", "group": "Western Cape",
        "status": "active",
        "basic_info": {"coordinates": {"lat": -33.0, "lon": 18.0, "dms": "S33\u00b000'00\" E18\u00b000'00\""}, "elevation": "100 ft AMSL", "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
        "operations": {"access": "Public", "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
        "communications": {"primary_freq": "118.1 MHz", "frequencies_table": [], "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
        "runways": {"data": [], "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
        "notes": [], "warnings": [], "contact": {}, "links": {},
    }
    md = generate_markdown_for_airfield(af)
    assert "### 1. TEST FIELD" in md
    assert "FATS" in md
    assert "100 ft AMSL" in md


def test_includes_sources_section():
    af = {
        "number": 1, "name": "TEST", "icao": "FATS", "group": "", "status": "active",
        "basic_info": {"coordinates": {"lat": -33.0, "lon": 18.0, "dms": ""}, "elevation": "", "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
        "operations": {"source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
        "communications": {"frequencies_table": [], "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
        "runways": {"data": [], "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
        "notes": [], "warnings": [], "contact": {}, "links": {},
    }
    md = generate_markdown_for_airfield(af)
    assert "Sources" in md or "Source" in md
    assert "2026-01-01" in md


def test_generates_full_document():
    airfields = [
        {
            "number": 1, "name": "ALPHA FIELD", "icao": "FAAF", "group": "Group A",
            "status": "active",
            "basic_info": {"coordinates": {"lat": -30.0, "lon": 25.0, "dms": "S30 E25"}, "elevation": "5000 ft", "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
            "operations": {"access": "Public", "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
            "communications": {"primary_freq": "118.1", "frequencies_table": [], "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
            "runways": {"data": [{"rwy": "01", "length": "1000 m", "surface": "Asphalt"}], "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
            "notes": [{"text": "Test note", "source": {"id": "sacaa_aip", "collected": "2026-01-01"}}],
            "warnings": [], "contact": {}, "links": {},
        },
    ]
    meta = {"version": "2.0", "last_full_scan": "2026-01-01", "source_registry": {}}
    md = generate_markdown(airfields, meta)
    assert "# SA Airfield Directory" in md
    assert "ALPHA FIELD" in md
    assert "118.1" in md


def test_closed_airfield_marked():
    af = {
        "number": 1, "name": "CLOSED FIELD", "icao": "", "group": "", "status": "closed",
        "basic_info": {"coordinates": {"lat": -30.0, "lon": 25.0, "dms": ""}, "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
        "operations": {"source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
        "communications": {"frequencies_table": [], "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
        "runways": {"data": [], "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
        "notes": [], "warnings": [], "contact": {}, "links": {},
    }
    md = generate_markdown_for_airfield(af)
    assert "CLOSED" in md
