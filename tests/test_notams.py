"""Tests for fetch_notams.py — NOTAM filtering and relevance ranking."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetch_notams import filter_notams, rank_by_relevance

SAMPLE_NOTAMS = [
    {"id": "A0001/26", "text": "RWY 01/19 CLSD DUE MAINT", "effective": "2026-03-18", "expiry": "2026-03-25"},
    {"id": "A0002/26", "text": "TWR LGT U/S", "effective": "2026-01-01", "expiry": "2026-12-31"},
    {"id": "A0003/26", "text": "TEMPO CRANE 50M AGL ERECTED 200M NE OF THR 19", "effective": "2026-03-01", "expiry": "2026-06-01"},
    {"id": "A0004/26", "text": "AD HR OF OPS CHANGED TO 0600-1800", "effective": "2026-03-15", "expiry": "2026-04-15"},
    {"id": "A0005/26", "text": "ILS RWY 01 U/S", "effective": "2026-03-10", "expiry": "2026-03-20"},
]


def test_filter_removes_expired():
    result = filter_notams(SAMPLE_NOTAMS, as_of="2026-03-26")
    ids = [n["id"] for n in result]
    assert "A0001/26" not in ids  # expired 2026-03-25


def test_filter_keeps_active():
    result = filter_notams(SAMPLE_NOTAMS, as_of="2026-03-19")
    ids = [n["id"] for n in result]
    assert "A0001/26" in ids  # active until 2026-03-25


def test_rank_prioritizes_runway_closure():
    ranked = rank_by_relevance(SAMPLE_NOTAMS)
    assert ranked[0]["id"] == "A0001/26"  # runway closure is highest priority


def test_rank_deprioritizes_lights():
    ranked = rank_by_relevance(SAMPLE_NOTAMS)
    lights = [n for n in ranked if n["id"] == "A0002/26"]
    assert lights[0].get("priority") == "low"


def test_filter_caps_at_max():
    result = filter_notams(SAMPLE_NOTAMS, as_of="2026-03-19", max_items=2)
    assert len(result) <= 2
