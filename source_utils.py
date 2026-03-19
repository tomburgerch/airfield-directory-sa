"""
source_utils.py — Source resolution, link generation, and authority helpers.

Used by all renderers to resolve source objects (from JSON airfield data) into
displayable information. The source registry maps short IDs (e.g. "sacaa_aip")
to full metadata: name, URL template, and authority level.
"""

import re


# ── FA-series ICAO regex ──────────────────────────────────────────────────────
_FA_ICAO_RE = re.compile(r'^FA[A-Z]{2,4}$')


def resolve_source(source, registry):
    """Resolve a source object to its full form.

    If the source has an ``id`` field, looks up the registry for name and
    authority. Defaults ``verified`` based on authority:
      - "official" → verified=True
      - anything else (e.g. "community") → verified=False

    An explicit ``verified`` key in the source object always overrides the
    registry default.

    Args:
        source (dict): Source object from airfield JSON data.
        registry (dict): Mapping of source IDs to metadata dicts.

    Returns:
        dict: Resolved source with at minimum ``name`` and ``verified`` keys.
    """
    resolved = dict(source)

    source_id = source.get("id")
    if source_id and source_id in registry:
        entry = registry[source_id]
        # Merge registry metadata (source keys win for name etc. if present)
        resolved.setdefault("name", entry.get("name", source_id))
        authority = entry.get("authority", "community")
    else:
        authority = "community"

    # Determine default verified from authority
    default_verified = (authority == "official")

    # Explicit "verified" in source overrides default
    if "verified" in source:
        resolved["verified"] = bool(source["verified"])
    else:
        resolved["verified"] = default_verified

    return resolved


def generate_verification_links(icao, registry):
    """Generate verification links from URL templates for a given ICAO code.

    Only generates links for FA-series ICAO codes (regex: ``^FA[A-Z]{2,4}$``).
    Registry entries without a ``url_template`` are skipped.

    Args:
        icao (str): ICAO or airfield code (e.g. "FASH", "ZA-0120").
        registry (dict): Mapping of source IDs to metadata dicts.

    Returns:
        list[dict]: List of ``{"name": ..., "url": ...}`` dicts. Empty list
                    if the ICAO is not FA-series.
    """
    if not _FA_ICAO_RE.match(icao):
        return []

    links = []
    for _source_id, entry in registry.items():
        template = entry.get("url_template")
        if not template:
            continue
        url = template.replace("{icao}", icao)
        links.append({"name": entry.get("name", _source_id), "url": url})

    return links


def is_official_source(source, registry):
    """Return True if the source's authority is "official".

    Looks up the registry using the source's ``id`` field. Returns False if
    the source has no ``id``, the id is not in the registry, or the authority
    is not "official".

    Args:
        source (dict): Source object from airfield JSON data.
        registry (dict): Mapping of source IDs to metadata dicts.

    Returns:
        bool
    """
    source_id = source.get("id")
    if not source_id:
        return False
    entry = registry.get(source_id)
    if not entry:
        return False
    return entry.get("authority") == "official"


def get_source_url(source, registry, icao=None):
    """Get the URL for a source, resolving templates if needed.

    If the source has an ``id`` in the registry and the registry entry has a
    ``url_template``, substitutes ``icao`` into the template (when provided).
    Falls back to the inline ``url`` field on the source object.

    Args:
        source (dict): Source object from airfield JSON data.
        registry (dict): Mapping of source IDs to metadata dicts.
        icao (str | None): ICAO code used for template substitution.

    Returns:
        str | None: Resolved URL, or None if no URL could be determined.
    """
    source_id = source.get("id")
    if source_id and source_id in registry:
        entry = registry[source_id]
        template = entry.get("url_template")
        if template:
            if icao and "{icao}" in template:
                return template.replace("{icao}", icao)
            # Return template as-is if no icao substitution needed/possible
            if "{icao}" not in template:
                return template

    # Fall back to inline URL
    return source.get("url")
