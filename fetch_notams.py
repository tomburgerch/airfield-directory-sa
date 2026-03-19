#!/usr/bin/env python3
"""
NOTAM fetching, filtering, and relevance ranking for SA airfields.

Fetches NOTAMs at build time and filters to the most relevant items per airfield.
Falls back gracefully if the NOTAM API is unavailable.
"""

import json
import re
from datetime import datetime, timezone

# ── Relevance keywords ────────────────────────────────────────────────────────
_HIGH_KEYWORDS = re.compile(
    r'CLSD|CLOSED|AD CLSD|RWY.*CLSD|AIRSPACE|DANGER AREA|FREQ CHANGED|FREQ CHG',
    re.IGNORECASE,
)
_MEDIUM_KEYWORDS = re.compile(
    r'HR OF OPS|CRANE|OBST|BIRD|WILDLIFE|TEMPO|RESTRICTED|FIRE',
    re.IGNORECASE,
)
_LOW_KEYWORDS = re.compile(
    r'LGT U/S|LIGHT|ILS|VOR|NDB|DME|DVOR|PAPI',
    re.IGNORECASE,
)

_PRIORITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}


def rank_by_relevance(notams):
    """Assign priority to NOTAMs and return sorted by relevance (high first).

    Priority levels:
      - high: runway/airfield closures, airspace restrictions, frequency changes
      - medium: operating hours changes, obstacles, wildlife, temporary hazards
      - low: lights unserviceable, instrument-only items (ILS/VOR/NDB)

    Args:
        notams: List of NOTAM dicts with at least 'text' field.

    Returns:
        List of NOTAM dicts with 'priority' field added, sorted high→medium→low.
    """
    ranked = []
    for notam in notams:
        n = dict(notam)
        text = n.get('text', '')
        if _HIGH_KEYWORDS.search(text):
            n['priority'] = 'high'
        elif _MEDIUM_KEYWORDS.search(text):
            n['priority'] = 'medium'
        else:
            n['priority'] = 'low'
        ranked.append(n)

    ranked.sort(key=lambda n: _PRIORITY_ORDER.get(n['priority'], 2))
    return ranked


def filter_notams(notams, as_of=None, max_items=3):
    """Filter NOTAMs: remove expired, rank by relevance, cap at max_items.

    Args:
        notams: List of NOTAM dicts with 'expiry' and 'effective' date strings.
        as_of: Date string (YYYY-MM-DD) to use as "now". Defaults to today.
        max_items: Maximum number of NOTAMs to return.

    Returns:
        List of active, ranked NOTAMs (up to max_items).
    """
    if as_of:
        ref_date = as_of
    else:
        ref_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # Filter out expired NOTAMs
    active = []
    for notam in notams:
        expiry = notam.get('expiry', '')
        if expiry and expiry < ref_date:
            continue
        active.append(notam)

    # Rank and cap
    ranked = rank_by_relevance(active)
    return ranked[:max_items]


def fetch_notams_for_icao(icao):
    """Fetch NOTAMs for a single ICAO code from an available API.

    Currently returns empty results — NOTAM API integration to be added
    when a suitable free API for South African airfields is identified.

    Args:
        icao: ICAO code (e.g. 'FASH').

    Returns:
        List of NOTAM dicts, or empty list if unavailable.
    """
    # TODO: Integrate with ICAO API, AirportGuide, or SACAA NOTAM source
    # For now, return empty — the build won't fail, just won't have NOTAMs
    return []


def fetch_all_notams(airfields):
    """Batch fetch NOTAMs for all FA-series airfields.

    Args:
        airfields: List of JSON-schema airfield dicts.

    Returns:
        Dict keyed by ICAO code, values are NOTAM result dicts:
        {"fetched": "ISO timestamp", "items": [...], "all_notams_url": "..."}
    """
    results = {}
    fetched_ts = datetime.now(timezone.utc).isoformat()

    for af in airfields:
        icao = af.get('icao', '')
        if not re.match(r'^FA[A-Z]{2,4}$', icao):
            continue

        raw_notams = fetch_notams_for_icao(icao)
        if not raw_notams:
            continue

        filtered = filter_notams(raw_notams, max_items=3)
        if filtered:
            results[icao] = {
                'fetched': fetched_ts,
                'items': filtered,
                'all_notams_url': f'https://www.caa.co.za/',  # placeholder
            }

    return results
