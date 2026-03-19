"""Tests for migrate_to_json.py — migration from markdown to JSON."""

import os
import sys
import re
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrate_to_json import (
    migrate_airfield,
    build_source_for_field,
    extract_websites_from_raw,
    determine_status,
    build_meta,
    MIGRATION_DATE,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def stellenbosch_af():
    """A minimal airfield dict mimicking Stellenbosch (FASH) from the parser."""
    return {
        'number': 2,
        'name': 'STELLENBOSCH AIRFIELD (FASH)',
        'group': 'WESTERN CAPE',
        'fields': {
            'ICAO': 'FASH',
            'AIP Link': 'SACAA AIP AD2',
            'Coordinates': 'S33°58\'50" E18°49\'22"',
            'Elevation': '321 ft AMSL',
            'Ref Temp': '15°C',
            'Mag Var': '23°W (1.3° westward annual change)',
            'Frequencies': '119.3 MHz (aerodrome traffic)',
            'Joining Alt': '1800 ft AMSL (overhead join from the east)',
            'Circuit Alt': '1300 ft AMSL (downwind)',
            'Access': 'Private — Club members and training only',
            'Night Ops': 'No (no lighting)',
            'Fuel': 'AVGAS 100LL, Aeroshell Oil ASO W100',
            'Fire Cat': 'Category 2 (fire tender 2,200L medium pumper)',
        },
        'fields_raw': {
            'ICAO': 'FASH',
            'AIP Link': '[SACAA AIP AD2](https://caasanwebsitestorage.blob.core.windows.net/aerodrone-and-helicompter-directory/FASHAD2.pdf)',
            'Websites': '[Morningstar Flying Club – Stellenbosch page](https://morningstarflyingclub.co.za/stellenbosch-airfield/), [Stellenbosch Flying Club](https://stelfly.co.za/)',
            'Coordinates': 'S33°58\'50" E18°49\'22"',
            'Elevation': '321 ft AMSL',
            'Ref Temp': '15°C',
            'Mag Var': '23°W (1.3° westward annual change)',
            'Frequencies': '**119.3 MHz** (aerodrome traffic)',
            'Joining Alt': '**1800 ft** AMSL (overhead join from the east)',
            'Circuit Alt': '**1300 ft** AMSL (downwind)',
            'Access': '🔒 Private — Club members and training only',
            'Night Ops': '🚫 No (no lighting)',
            'Fuel': '⛽ AVGAS 100LL, Aeroshell Oil ASO W100',
            'Fire Cat': 'Category 2 (fire tender 2,200L medium pumper)',
        },
        'runways': [
            ['01', '760 m', '16 m', 'Asphalt', 'LCN 20', '⬅️ Left'],
            ['19', '760 m', '16 m', 'Asphalt', 'LCN 20', '➡️ Right'],
        ],
        'notes': [
            'Western circuit — all circuits flown WEST of and within 2.5 NM of FASH',
            'Noise abatement: constant speed units per AIC 20.12',
        ],
        'warnings': [
            'Poles 4 m high erected 150 m from final approach of RWY 01',
        ],
        'frequencies_table': [],
        'contact': 'Stellenbosch Flying Club, TEL: (021) 880-1907',
    }


@pytest.fixture
def morningstar_af():
    """Morningstar — ZA-series, no AIP link."""
    return {
        'number': 1,
        'name': 'MORNINGSTAR AIRFIELD',
        'group': 'WESTERN CAPE',
        'fields': {
            'ICAO / Code': 'ZA-0120 (no official ICAO; sometimes FAMORN)',
            'AIP Link': 'Not in SACAA AIP (unlicensed)',
            'Coordinates': 'S33°45\'44" E18°32\'55"',
            'Elevation': '200 ft AMSL',
            'Frequencies': '126.8 MHz (changed Oct 2020 from 124.8)',
            'Access': 'Club members & visitors (contact MSFA)',
            'Night Ops': 'No',
        },
        'fields_raw': {
            'ICAO / Code': 'ZA-0120 (no official ICAO; sometimes FAMORN)',
            'AIP Link': 'Not in SACAA AIP (unlicensed)',
            'Websites': '[Morningstar Flying Club](https://morningstarflyingclub.co.za/airfield-info/), [MSFA](https://msfa.co.za/)',
            'Coordinates': 'S33°45\'44" E18°32\'55"',
            'Elevation': '200 ft AMSL',
            'Frequencies': '**126.8 MHz** (changed Oct 2020 from 124.8)',
            'Access': '🔒 Club members & visitors (contact MSFA)',
            'Night Ops': '🚫 No',
        },
        'runways': [
            ['02', '645 m', '12 m', 'Tar', 'Right'],
            ['20', '645 m', '12 m', 'Tar', 'Left'],
        ],
        'notes': ['RWY 02: RIGHT-HAND circuit', 'RWY 20: Left-hand circuit'],
        'warnings': [],
        'frequencies_table': [],
        'contact': '',
    }


@pytest.fixture
def closed_af():
    """A closed airfield."""
    return {
        'number': 10,
        'name': 'PAARL EAST AIRPORT (FAPU) — ⛔ CLOSED',
        'group': 'WESTERN CAPE',
        'fields': {
            'ICAO': 'FAPU',
            'Access': 'CLOSED',
            'Coordinates': 'S33°42\'39" E19°01\'28" (historical)',
            'Elevation': '596 ft AMSL (historical)',
        },
        'fields_raw': {
            'ICAO': 'FAPU',
            'Access': '⛔ **CLOSED**',
            'AIP Link': 'Not in current SACAA AIP',
            'Coordinates': 'S33°42\'39" E19°01\'28" (historical)',
        },
        'runways': [],
        'notes': ['Located on Buffet Olives farm'],
        'warnings': ['DO NOT plan operations to FAPU'],
        'frequencies_table': [],
        'contact': '',
    }


@pytest.fixture
def military_af():
    """A military airfield."""
    return {
        'number': 15,
        'name': 'YSTERPLAAT AIR FORCE BASE (FAYP)',
        'group': 'WESTERN CAPE',
        'fields': {
            'ICAO': 'FAYP',
            'Access': 'Military — NO civilian access',
            'Coordinates': 'S33°54\'00" E18°29\'53"',
            'Elevation': '52 ft AMSL',
        },
        'fields_raw': {
            'ICAO': 'FAYP',
            'Access': '🪖 Military — NO civilian access',
            'Coordinates': 'S33°54\'00" E18°29\'53"',
        },
        'runways': [],
        'notes': ['South African Air Force base'],
        'warnings': [],
        'frequencies_table': [],
        'contact': '',
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestMigrateAirfieldBasicStructure:
    """A migrated airfield has all required top-level keys."""

    def test_required_keys_present(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        required = [
            'number', 'name', 'icao', 'group', 'status',
            'basic_info', 'operations', 'communications', 'runways',
            'notes', 'warnings',
        ]
        for key in required:
            assert key in result, f"Missing required key: {key}"

    def test_optional_keys_present(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        for key in ['contact', 'links', 'notams']:
            assert key in result, f"Missing optional key: {key}"

    def test_notams_is_empty_array(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        assert result['notams'] == []

    def test_number_preserved(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        assert result['number'] == 2

    def test_name_preserved(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        assert result['name'] == 'STELLENBOSCH AIRFIELD (FASH)'

    def test_group_preserved(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        assert result['group'] == 'WESTERN CAPE'


class TestMigrateAirfieldCoordinates:
    """Coordinates correctly parsed to lat/lon decimal."""

    def test_stellenbosch_lat(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        coords = result['basic_info']['coordinates']
        assert coords['lat'] == pytest.approx(-33.980556, abs=0.001)

    def test_stellenbosch_lon(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        coords = result['basic_info']['coordinates']
        assert coords['lon'] == pytest.approx(18.822778, abs=0.001)

    def test_dms_string_present(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        coords = result['basic_info']['coordinates']
        assert 'dms' in coords
        assert 'S33' in coords['dms']

    def test_no_coords_gives_none(self):
        af = {
            'number': 99, 'name': 'TEST', 'group': 'G', 'fields': {},
            'fields_raw': {}, 'runways': [], 'notes': [], 'warnings': [],
            'frequencies_table': [], 'contact': '',
        }
        result = migrate_airfield(af, {}, {})
        assert result['basic_info'].get('coordinates') is None


class TestMigrateClosedAirfield:
    """Status is 'closed' when name has CLOSED."""

    def test_closed_status(self, closed_af):
        result = migrate_airfield(closed_af, {}, {})
        assert result['status'] == 'closed'


class TestMigrateMilitaryAirfield:
    """Status is 'military' when Access contains Military."""

    def test_military_status(self, military_af):
        result = migrate_airfield(military_af, {}, {})
        assert result['status'] == 'military'


class TestMigrateActiveAirfield:
    """Default active status."""

    def test_active_status(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        assert result['status'] == 'active'


class TestExtractWebsitesFromRaw:
    """Correctly extracts markdown links from fields_raw."""

    def test_multiple_websites(self):
        fields_raw = {
            'Websites': '[Club](https://club.co.za), [Other](https://other.co.za/)',
        }
        websites = extract_websites_from_raw(fields_raw)
        assert len(websites) == 2
        assert websites[0]['label'] == 'Club'
        assert websites[0]['url'] == 'https://club.co.za'
        assert websites[1]['label'] == 'Other'
        assert websites[1]['url'] == 'https://other.co.za/'

    def test_single_website(self):
        fields_raw = {
            'Website': '[My Site](https://example.com/)',
        }
        websites = extract_websites_from_raw(fields_raw)
        assert len(websites) == 1
        assert websites[0]['label'] == 'My Site'

    def test_operator_aip(self):
        fields_raw = {
            'Operator AIP': '[AIP FAWN PDF](https://capewinelands.aero/aip.pdf)',
        }
        websites = extract_websites_from_raw(fields_raw)
        assert len(websites) == 1
        assert websites[0]['url'] == 'https://capewinelands.aero/aip.pdf'

    def test_no_websites(self):
        fields_raw = {'ICAO': 'FAXX'}
        websites = extract_websites_from_raw(fields_raw)
        assert websites == []

    def test_aip_link_not_included(self):
        """AIP Link is used for source, not extracted as website."""
        fields_raw = {
            'AIP Link': '[SACAA AIP AD2](https://caasanwebsitestorage.blob.core.windows.net/FASHAD2.pdf)',
        }
        websites = extract_websites_from_raw(fields_raw)
        assert websites == []


class TestBuildSourceAipAirfield:
    """FA-series with AIP Link -> sacaa_aip source."""

    def test_fa_with_aip_link(self):
        fields_raw = {
            'ICAO': 'FASH',
            'AIP Link': '[SACAA AIP AD2](https://caasanwebsitestorage.blob.core.windows.net/FASHAD2.pdf)',
        }
        source = build_source_for_field('FASH', fields_raw)
        assert source['id'] == 'sacaa_aip'
        assert source['collected'] == MIGRATION_DATE

    def test_fa_without_aip_link(self):
        fields_raw = {
            'ICAO': 'FAPU',
            'AIP Link': 'Not in current SACAA AIP',
        }
        source = build_source_for_field('FAPU', fields_raw)
        assert 'id' not in source
        assert 'url' in source


class TestBuildSourceNonAipAirfield:
    """ZA-series without AIP Link -> not sacaa_aip."""

    def test_za_series(self):
        fields_raw = {
            'ICAO / Code': 'ZA-0120',
            'AIP Link': 'Not in SACAA AIP (unlicensed)',
        }
        source = build_source_for_field('ZA-0120', fields_raw)
        assert 'id' not in source
        assert 'url' in source
        assert source['name'] == 'Community sources'


class TestDetermineStatus:
    """Test determine_status logic."""

    def test_closed_in_name(self):
        assert determine_status('PAARL EAST (FAPU) — ⛔ CLOSED', {}) == 'closed'

    def test_closed_x_in_name(self):
        assert determine_status('SOME FIELD [X]', {}) == 'closed'

    def test_military(self):
        assert determine_status('YSTERPLAAT', {'Access': 'Military — NO civilian access'}) == 'military'

    def test_active_default(self):
        assert determine_status('STELLENBOSCH', {'Access': 'Private'}) == 'active'

    def test_permanently_closed(self):
        assert determine_status('HERMANUS (FAHM) — ⛔ PERMANENTLY CLOSED', {}) == 'closed'

    def test_closed_in_access(self):
        assert determine_status('SOME FIELD', {'Access': 'CLOSED'}) == 'closed'


class TestBuildMeta:
    """Test build_meta produces correct structure."""

    def test_has_version(self):
        meta = build_meta([])
        assert 'version' in meta

    def test_has_source_registry(self):
        meta = build_meta([])
        assert 'source_registry' in meta
        assert 'sacaa_aip' in meta['source_registry']
        assert meta['source_registry']['sacaa_aip']['authority'] == 'official'

    def test_has_last_full_scan(self):
        meta = build_meta([])
        assert 'last_full_scan' in meta
        assert meta['last_full_scan'] == MIGRATION_DATE

    def test_source_registry_has_all_keys(self):
        meta = build_meta([])
        expected = {'sacaa_aip', 'ourairports', 'skyvector', 'airportguide', 'avcom'}
        assert set(meta['source_registry'].keys()) == expected


class TestRunwayConversion:
    """Test that runways are converted from list-of-lists to list-of-dicts."""

    def test_runway_dict_format(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        rwys = result['runways']['data']
        assert len(rwys) == 2
        assert rwys[0]['rwy'] == '01'
        assert rwys[0]['length'] == '760 m'
        assert rwys[0]['surface'] == 'Asphalt'

    def test_runway_circuit_cleaned(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        rwys = result['runways']['data']
        # Emoji should be stripped
        assert rwys[0]['circuit'] in ('Left', 'left')
        assert rwys[1]['circuit'] in ('Right', 'right')


class TestNotesAndWarnings:
    """Each note/warning gets its own source object."""

    def test_notes_have_source(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        for note in result['notes']:
            assert 'text' in note
            assert 'source' in note
            assert 'collected' in note['source']

    def test_warnings_have_source(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        for warning in result['warnings']:
            assert 'text' in warning
            assert 'source' in warning


class TestTowerPhone:
    """Tower phone is merged from tower_data."""

    def test_tower_phone_merged(self, stellenbosch_af):
        tower_phones = {'FASH': '+27 21 555 1234'}
        result = migrate_airfield(stellenbosch_af, {}, tower_phones)
        assert result['communications']['tower_phone'] == '+27 21 555 1234'

    def test_no_tower_phone(self, morningstar_af):
        result = migrate_airfield(morningstar_af, {}, {})
        assert result['communications']['tower_phone'] is None


class TestNightOps:
    """Night ops conversion from string to boolean."""

    def test_no_becomes_false(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        assert result['operations']['night_ops'] is False

    def test_yes_becomes_true(self):
        af = {
            'number': 99, 'name': 'TEST', 'group': 'G',
            'fields': {'Night Ops': 'Yes — remote-activated runway lights',
                       'Coordinates': 'S33°54\'00" E18°29\'53"'},
            'fields_raw': {'Night Ops': '🌙 Yes — remote-activated runway lights'},
            'runways': [], 'notes': [], 'warnings': [],
            'frequencies_table': [], 'contact': '',
        }
        result = migrate_airfield(af, {}, {})
        assert result['operations']['night_ops'] is True


class TestIcaoExtraction:
    """ICAO is cleaned to just the code."""

    def test_fa_series(self, stellenbosch_af):
        result = migrate_airfield(stellenbosch_af, {}, {})
        assert result['icao'] == 'FASH'

    def test_za_series(self, morningstar_af):
        result = migrate_airfield(morningstar_af, {}, {})
        assert result['icao'] == 'ZA-0120'

    def test_previously_fafk(self):
        """ICAO field like 'FAWN (previously FAFK)' -> 'FAWN'."""
        af = {
            'number': 3, 'name': 'CAPE WINELANDS', 'group': 'G',
            'fields': {'ICAO': 'FAWN (previously FAFK)'},
            'fields_raw': {'ICAO': 'FAWN (previously FAFK)'},
            'runways': [], 'notes': [], 'warnings': [],
            'frequencies_table': [], 'contact': '',
        }
        result = migrate_airfield(af, {}, {})
        assert result['icao'] == 'FAWN'


class TestVerifiedFactsMerge:
    """Verified facts are baked into the entry."""

    def test_notes_prepended(self, morningstar_af):
        vf = {
            1: {
                'verified_notes': ['RWY 02: RIGHT-HAND circuit'],
                'source': 'Pilot confirmation',
                'verified_date': '2026-03-15',
            }
        }
        result = migrate_airfield(morningstar_af, vf, {})
        note_texts = [n['text'] for n in result['notes']]
        assert 'RWY 02: RIGHT-HAND circuit' in note_texts
