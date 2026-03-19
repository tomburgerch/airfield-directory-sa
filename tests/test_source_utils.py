"""Tests for source_utils.py — source resolution, link generation, verified defaults."""
import pytest
from source_utils import resolve_source, generate_verification_links, is_official_source

SAMPLE_REGISTRY = {
    "sacaa_aip": {
        "name": "SACAA AIP",
        "url_template": "https://caasanwebsitestorage.blob.core.windows.net/aerodrone-and-helicompter-directory/{icao}AD2.pdf",
        "authority": "official",
    },
    "ourairports": {
        "name": "OurAirports",
        "url_template": "https://ourairports.com/airports/{icao}/",
        "authority": "community",
    },
}

def test_resolve_source_with_registry_id():
    source = {"id": "sacaa_aip", "collected": "2026-02-15"}
    resolved = resolve_source(source, SAMPLE_REGISTRY)
    assert resolved["name"] == "SACAA AIP"
    assert resolved["verified"] is True  # official default

def test_resolve_source_with_inline_url():
    source = {"url": "https://stelfly.co.za/", "name": "Stellenbosch FC", "collected": "2026-03-10"}
    resolved = resolve_source(source, SAMPLE_REGISTRY)
    assert resolved["name"] == "Stellenbosch FC"
    assert resolved["verified"] is False  # inline default

def test_resolve_source_explicit_verified_overrides_default():
    source = {"id": "ourairports", "collected": "2026-01-01", "verified": True}
    resolved = resolve_source(source, SAMPLE_REGISTRY)
    assert resolved["verified"] is True  # explicit overrides community default

def test_generate_links_for_fa_series():
    links = generate_verification_links("FASH", SAMPLE_REGISTRY)
    assert any("ourairports.com/airports/FASH" in link["url"] for link in links)
    assert any("FASHAD2.pdf" in link["url"] for link in links)

def test_generate_links_skips_za_series():
    links = generate_verification_links("ZA-0120", SAMPLE_REGISTRY)
    assert not any("{icao}" in link.get("url", "") for link in links)

def test_is_official_source():
    assert is_official_source({"id": "sacaa_aip"}, SAMPLE_REGISTRY) is True
    assert is_official_source({"id": "ourairports"}, SAMPLE_REGISTRY) is False
    assert is_official_source({"url": "https://x.com", "name": "X"}, SAMPLE_REGISTRY) is False
