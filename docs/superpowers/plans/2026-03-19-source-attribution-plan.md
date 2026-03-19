# Source Attribution & Data Provenance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add source attribution to the SA airfield directory so pilots can see where data came from and verify it themselves.

**Architecture:** Migrate from `AIRFIELD_DIRECTORY.md` as source-of-truth to `airfields.json` with per-group source annotations. All renderers (HTML, A5 PDF, A4 PDF, markdown) read from JSON. Build-time NOTAM fetching with relevance filtering. Feature branch `feature/source-attribution`.

**Tech Stack:** Python 3.12, reportlab (PDF), JSON Schema validation, Vercel deployment

**Spec:** `docs/superpowers/specs/2026-03-19-source-attribution-design.md`

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `airfields.json` | Single source of truth for all airfield data + source annotations |
| `airfields.schema.json` | JSON Schema for validating `airfields.json` |
| `migrate_to_json.py` | One-time migration: parses markdown + verified_facts + tower_data → JSON |
| `source_utils.py` | Source resolution: registry lookups, link generation, verified defaults |
| `fetch_notams.py` | Build-time NOTAM fetching + relevance filtering |
| `generate_markdown.py` | JSON → markdown output (for Notion import) |
| `tests/test_source_utils.py` | Tests for source resolution logic |
| `tests/test_migration.py` | Tests for markdown → JSON migration |
| `tests/test_notams.py` | Tests for NOTAM fetching + filtering |
| `tests/test_generate_markdown.py` | Tests for markdown generation |

### Modified files
| File | Changes |
|------|---------|
| `generate_html.py` | Read from JSON, add source attribution UX, click-to-copy coords |
| `generate_pdf.py` | Read from JSON, add source footer per card |
| `generate_airfield_pdfs.py` | Read from JSON, remove duplicate TOWER_PHONES, add source sections |
| `build.py` | New pipeline: fetch NOTAMs → JSON → all renderers |
| `validate_data.py` | Validate JSON schema instead of markdown parsing |
| `shared.py` | Add `AIRFIELDS_JSON` path constant |
| `pdf_styles.py` | May need updates if card styling changes |
| `diagrams_util.py` | May need updates — JSON has `diagram.file` instead of runtime lookup |
| `tests/test_html.py` | Update to work with JSON-based rendering |
| `tests/test_build.py` | Update for new build pipeline |
| `tests/test_parse.py` | Keep existing tests, add JSON loading tests |
| `tests/test_validate.py` | Update for JSON schema validation |

### Notes on lifecycle
- **`verified_facts.json`** — baked into `airfields.json` during migration. Becomes archival/read-only after. Do NOT edit it going forward; edit `airfields.json` directly.
- **`parse_markdown.py`** — kept functional during transition. Can be removed once JSON pipeline is stable and verified.
- **`frequency_tables`** — regional common frequency tables are migrated into `airfields.json` under `meta.frequency_tables` (same structure as current `parse_frequency_tables()` output).
- **Parallelizable tasks:** Tasks 5, 6, and 9 are independent and can be executed in parallel.

---

## Task 1: Create feature branch and JSON schema

**Files:**
- Create: `airfields.schema.json`
- Modify: `shared.py:11-16`

- [ ] **Step 1: Create feature branch**

```bash
git checkout -b feature/source-attribution
```

- [ ] **Step 2: Add AIRFIELDS_JSON path to shared.py**

In `shared.py`, after line 13 (`VERIFIED_FACTS_FILE = ...`), add:

```python
AIRFIELDS_JSON = os.path.join(BASE_DIR, 'airfields.json')
```

- [ ] **Step 3: Write the JSON Schema file**

Create `airfields.schema.json` with the full schema from the spec. Key validation rules:
- `meta.version` required string
- `meta.last_full_scan` required string (YYYY-MM-DD)
- `meta.source_registry` required object with known source IDs
- `airfields` required array of airfield objects
- Each airfield: `number` (int), `name` (string), `icao` (string), `group` (string), `status` (enum: active/closed/military/decommissioned)
- Each source object: exactly one of `id` or `url`, required `collected` (date string)
- If `url` present, `name` required

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["meta", "airfields"],
  "properties": {
    "meta": {
      "type": "object",
      "required": ["version", "last_full_scan", "source_registry"],
      "properties": {
        "version": { "type": "string" },
        "last_full_scan": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" },
        "source_registry": {
          "type": "object",
          "additionalProperties": {
            "type": "object",
            "required": ["name", "authority"],
            "properties": {
              "name": { "type": "string" },
              "authority": { "type": "string", "enum": ["official", "community"] },
              "url_template": { "type": "string" },
              "url_base": { "type": "string" },
              "description": { "type": "string" },
              "license": { "type": "string" }
            }
          }
        }
      }
    },
    "airfields": {
      "type": "array",
      "items": { "$ref": "#/$defs/airfield" }
    }
  },
  "$defs": {
    "source_object": {
      "type": "object",
      "required": ["collected"],
      "properties": {
        "id": { "type": "string" },
        "url": { "type": "string", "format": "uri" },
        "name": { "type": "string" },
        "collected": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" },
        "verified": { "type": "boolean" }
      },
      "oneOf": [
        { "required": ["id"], "not": { "required": ["url"] } },
        { "required": ["url", "name"], "not": { "required": ["id"] } }
      ]
    },
    "airfield": {
      "type": "object",
      "required": ["number", "name", "icao", "group", "status", "basic_info", "operations", "communications", "runways", "notes", "warnings"],
      "properties": {
        "number": { "type": "integer" },
        "name": { "type": "string" },
        "icao": { "type": "string" },
        "group": { "type": "string" },
        "status": { "type": "string", "enum": ["active", "closed", "military", "decommissioned"] },
        "basic_info": {
          "type": "object",
          "required": ["coordinates", "source"],
          "properties": {
            "coordinates": {
              "type": "object",
              "required": ["lat", "lon"],
              "properties": {
                "lat": { "type": "number" },
                "lon": { "type": "number" },
                "dms": { "type": "string" }
              }
            },
            "elevation": { "type": "string" },
            "mag_var": { "type": "string" },
            "ref_temp": { "type": "string" },
            "source": { "$ref": "#/$defs/source_object" }
          }
        },
        "operations": {
          "type": "object",
          "required": ["source"],
          "properties": {
            "access": { "type": "string" },
            "hours": { "type": "string" },
            "fuel": { "type": "string" },
            "fuel_hours": { "type": "string" },
            "night_ops": { "type": ["boolean", "string"] },
            "fire_cat": { "type": "string" },
            "joining_alt": { "type": "string" },
            "circuit_alt": { "type": "string" },
            "source": { "$ref": "#/$defs/source_object" }
          }
        },
        "communications": {
          "type": "object",
          "required": ["source"],
          "properties": {
            "primary_freq": { "type": "string" },
            "frequencies_table": { "type": "array" },
            "tower_phone": { "type": ["string", "null"] },
            "source": { "$ref": "#/$defs/source_object" }
          }
        },
        "runways": {
          "type": "object",
          "required": ["data", "source"],
          "properties": {
            "data": { "type": "array" },
            "source": { "$ref": "#/$defs/source_object" }
          }
        },
        "notes": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["text", "source"],
            "properties": {
              "text": { "type": "string" },
              "source": { "$ref": "#/$defs/source_object" }
            }
          }
        },
        "warnings": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["text", "source"],
            "properties": {
              "text": { "type": "string" },
              "source": { "$ref": "#/$defs/source_object" }
            }
          }
        },
        "contact": {
          "type": "object",
          "properties": {
            "name": { "type": "string" },
            "phone": { "type": "string" },
            "address": { "type": "string" },
            "source": { "$ref": "#/$defs/source_object" }
          }
        },
        "links": {
          "type": "object",
          "properties": {
            "websites": { "type": "array" },
            "aip": { "type": "string" }
          }
        },
        "diagram": {
          "type": "object",
          "properties": {
            "file": { "type": "string" },
            "source": { "$ref": "#/$defs/source_object" }
          }
        },
        "notams": {}
      }
    }
  }
}
```

- [ ] **Step 4: Add test artifacts to .gitignore**

```bash
echo -e "\n# Test artifacts\ntest_output.pdf\ntest_pdfs/\n.superpowers/" >> .gitignore
```

- [ ] **Step 5: Commit**

```bash
git add shared.py airfields.schema.json .gitignore
git commit -m "feat: add JSON schema and path constant for airfields.json"
```

---

## Task 2: Build source_utils.py

**Files:**
- Create: `source_utils.py`
- Create: `tests/test_source_utils.py`

- [ ] **Step 1: Write failing tests for source resolution**

Create `tests/test_source_utils.py`:

```python
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
    assert "url" not in resolved or resolved["url"] is None


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
    # Templates with {icao} should not generate for ZA-series
    assert not any("{icao}" in link.get("url", "") for link in links)


def test_is_official_source():
    assert is_official_source({"id": "sacaa_aip"}, SAMPLE_REGISTRY) is True
    assert is_official_source({"id": "ourairports"}, SAMPLE_REGISTRY) is False
    assert is_official_source({"url": "https://x.com", "name": "X"}, SAMPLE_REGISTRY) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_source_utils.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'source_utils'`

- [ ] **Step 3: Implement source_utils.py**

Create `source_utils.py`:

```python
#!/usr/bin/env python3
"""Source resolution utilities for airfield data provenance."""

import re


def resolve_source(source, registry):
    """Resolve a source object to its full form with name, URL, and verified status.

    Args:
        source: dict with either 'id' (registry key) or 'url' + 'name'
        registry: the meta.source_registry dict

    Returns:
        dict with 'name', 'collected', 'verified', and optionally 'url'
    """
    resolved = {"collected": source["collected"]}

    if "id" in source:
        entry = registry.get(source["id"], {})
        resolved["name"] = entry.get("name", source["id"])
        resolved["authority"] = entry.get("authority", "community")
        # Default verified based on authority
        if "verified" in source:
            resolved["verified"] = source["verified"]
        else:
            resolved["verified"] = entry.get("authority") == "official"
    else:
        resolved["name"] = source["name"]
        resolved["url"] = source["url"]
        resolved["authority"] = "community"
        resolved["verified"] = source.get("verified", False)

    return resolved


def generate_verification_links(icao, registry):
    """Generate verification links for an airfield from the source registry.

    Only generates template-based links for FA-series ICAO codes.
    Returns list of dicts: [{"name": "...", "url": "..."}, ...]
    """
    links = []
    is_fa = bool(re.match(r'^FA[A-Z]{2,4}$', icao))

    for source_id, entry in registry.items():
        template = entry.get("url_template")
        if template and is_fa:
            url = template.replace("{icao}", icao)
            links.append({"name": entry["name"], "url": url})

    return links


def is_official_source(source, registry):
    """Check if a source is from an official authority."""
    if "id" in source:
        entry = registry.get(source["id"], {})
        return entry.get("authority") == "official"
    return False


def get_source_url(source, registry, icao=None):
    """Get the URL for a source object, resolving templates if needed."""
    if "url" in source:
        return source["url"]
    if "id" in source:
        entry = registry.get(source["id"], {})
        template = entry.get("url_template")
        if template and icao and re.match(r'^FA[A-Z]{2,4}$', icao):
            return template.replace("{icao}", icao)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_source_utils.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add source_utils.py tests/test_source_utils.py
git commit -m "feat: add source_utils for source resolution and link generation"
```

---

## Task 3: Build migration script (markdown → JSON)

**Files:**
- Create: `migrate_to_json.py`
- Create: `tests/test_migration.py`

- [ ] **Step 1: Write failing tests for migration**

Create `tests/test_migration.py`:

```python
"""Tests for migrate_to_json.py — markdown to JSON migration."""
import json
import pytest
from migrate_to_json import migrate_airfield, build_source_for_field, extract_websites_from_raw


def test_migrate_airfield_basic_structure():
    """A migrated airfield has all required top-level keys."""
    af = {
        'number': 1, 'name': 'TEST AIRFIELD', 'group': 'Western Cape',
        'fields': {'ICAO / Code': 'FASH', 'Coordinates': 'S33°58\'50" E18°49\'22"',
                   'Elevation': '321 ft AMSL', 'Frequencies': '119.3 MHz',
                   'Access': 'Public'},
        'fields_raw': {}, 'runways': [], 'notes': [], 'warnings': [],
        'frequencies_table': [], 'contact': '',
    }
    result = migrate_airfield(af, {}, {})
    assert result['number'] == 1
    assert result['name'] == 'TEST AIRFIELD'
    assert result['icao'] == 'FASH'
    assert result['status'] == 'active'
    assert 'basic_info' in result
    assert 'operations' in result
    assert 'communications' in result
    assert 'runways' in result


def test_migrate_airfield_extracts_coordinates():
    af = {
        'number': 1, 'name': 'TEST', 'group': '',
        'fields': {'Coordinates': 'S33°58\'50" E18°49\'22"', 'Elevation': '100 ft AMSL'},
        'fields_raw': {}, 'runways': [], 'notes': [], 'warnings': [],
        'frequencies_table': [], 'contact': '',
    }
    result = migrate_airfield(af, {}, {})
    coords = result['basic_info']['coordinates']
    assert coords['lat'] == pytest.approx(-33.9806, abs=0.001)
    assert coords['lon'] == pytest.approx(18.8228, abs=0.001)


def test_migrate_closed_airfield():
    af = {
        'number': 1, 'name': '[X] CLOSED FIELD', 'group': '',
        'fields': {}, 'fields_raw': {}, 'runways': [], 'notes': [],
        'warnings': [], 'frequencies_table': [], 'contact': '',
    }
    result = migrate_airfield(af, {}, {})
    assert result['status'] == 'closed'


def test_migrate_military_airfield():
    af = {
        'number': 1, 'name': 'AFB OVERBERG', 'group': '',
        'fields': {'Access': 'Military'}, 'fields_raw': {}, 'runways': [],
        'notes': [], 'warnings': [], 'frequencies_table': [], 'contact': '',
    }
    result = migrate_airfield(af, {}, {})
    assert result['status'] == 'military'


def test_extract_websites_from_raw():
    raw = {'Websites': '[Club](https://example.com), [Info](https://info.com)'}
    sites = extract_websites_from_raw(raw)
    assert len(sites) == 2
    assert sites[0]['label'] == 'Club'
    assert sites[0]['url'] == 'https://example.com'


def test_build_source_aip_airfield():
    """FA-series airfield with AIP link gets sacaa_aip source."""
    source = build_source_for_field('FASH', {'AIP Link': '[SACAA](https://example.com/FASHAD2.pdf)'})
    assert source['id'] == 'sacaa_aip'


def test_build_source_non_aip_airfield():
    """ZA-series airfield without AIP link gets no default source id."""
    source = build_source_for_field('ZA-0120', {})
    assert 'id' not in source or source.get('id') != 'sacaa_aip'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_migration.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement migrate_to_json.py**

Create `migrate_to_json.py`. This script:
1. Parses `AIRFIELD_DIRECTORY.md` using existing `parse_markdown.parse_airfields()`
2. Loads `verified_facts.json`
3. Loads `tower_data.TOWER_PHONES`
4. Converts each airfield dict to the new JSON schema
5. Determines source based on: AIP link in `fields_raw` → `sacaa_aip`, else community
6. Extracts website links from `fields_raw`
7. Merges tower phones into `communications.tower_phone`
8. Writes `airfields.json` with the source registry in `meta`

Key functions:
- `migrate_airfield(af, verified_facts, tower_phones)` → new-schema dict
- `build_source_for_field(icao, fields_raw)` → source object
- `extract_websites_from_raw(fields_raw)` → list of `{label, url}`
- `determine_status(name, fields)` → status string
- `build_meta()` → meta object with source registry

Also migrate:
- **Diagrams**: use `diagrams_util.find_diagram()` to populate `diagram.file` per airfield
- **Frequency tables**: call `parse_frequency_tables()` and store under `meta.frequency_tables`
- **Verified facts**: bake `verified_facts.json` data directly into the airfield entries (this is the last time verified_facts is read; after migration, edit `airfields.json` directly)

The script should print a summary: total migrated, FA-series count, ZA-series count, warnings.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_migration.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run the migration and validate output**

```bash
python migrate_to_json.py
python -c "
import json
with open('airfields.json') as f:
    data = json.load(f)
print(f'Airfields: {len(data[\"airfields\"])}')
print(f'Version: {data[\"meta\"][\"version\"]}')
# Spot-check Stellenbosch
fash = [a for a in data['airfields'] if a['icao'] == 'FASH'][0]
print(f'FASH: {fash[\"name\"]}, coords: {fash[\"basic_info\"][\"coordinates\"][\"lat\"]}')
print(f'FASH source: {fash[\"basic_info\"][\"source\"]}')
"
```

Expected: 276 airfields, version 2.0, FASH data looks correct.

- [ ] **Step 6: Validate JSON against schema**

```bash
pip install jsonschema
python -c "
import json, jsonschema
with open('airfields.json') as f: data = json.load(f)
with open('airfields.schema.json') as f: schema = json.load(f)
jsonschema.validate(data, schema)
print('Schema validation passed')
"
```

- [ ] **Step 7: Commit**

```bash
git add migrate_to_json.py tests/test_migration.py airfields.json
git commit -m "feat: migrate 276 airfields from markdown to airfields.json"
```

---

## Task 4: Update HTML renderer for JSON + source attribution

**Files:**
- Modify: `generate_html.py:1-1458`
- Modify: `tests/test_html.py`

This is the largest task. The HTML renderer needs to:
1. Read from `airfields.json` instead of calling `parse_airfields()`
2. Replace `fields_raw` link extraction with `links.websites`
3. Replace `TOWER_PHONES` lookup with `communications.tower_phone`
4. Add source attribution UX (inline ↗ arrows, sources footer)
5. Add click-to-copy coordinates
6. Remove airfield number from card header display
7. Ensure runway table always shows Width column

- [ ] **Step 1: Write new test for source footer rendering**

Add to `tests/test_html.py`:

```python
def test_source_footer_rendered():
    """Each airfield card should have a sources footer."""
    assert 'class="sources-footer"' in html_output

def test_click_to_copy_coordinates():
    """Coordinates should have click-to-copy data attribute."""
    assert 'data-copy-coords' in html_output

def test_no_airfield_number_in_header():
    """Airfield number should not appear in the card header."""
    # The old format was "2. STELLENBOSCH AIRFIELD"
    # New format should just be "STELLENBOSCH AIRFIELD"
    assert '2. STELLENBOSCH' not in html_output
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `python -m pytest tests/test_html.py -v -k "source_footer or click_to_copy or no_airfield_number"`
Expected: FAIL

- [ ] **Step 3: Create a JSON loading function in generate_html.py**

At the top of `generate_html.py`, add:

```python
import json
from source_utils import resolve_source, generate_verification_links, is_official_source, get_source_url
from shared import AIRFIELDS_JSON

def load_airfields_json(json_path=None):
    """Load airfields from JSON file."""
    path = json_path or AIRFIELDS_JSON
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['meta'], data['airfields']
```

- [ ] **Step 4: Rewrite build_airfield_card() to read from JSON schema**

Rewrite `generate_html.py:build_airfield_card()` (currently lines 1009-1209) to:
- Accept a JSON-schema airfield dict + meta dict
- Remove the `fields`/`fields_raw` pattern — read directly from `basic_info`, `operations`, etc.
- Remove airfield number from header display (keep internally for HTML `id` attribute)
- Add `data-copy-coords` attribute on coordinates with decimal lat/lon
- Add inline `↗` source indicator for non-AIP notes/warnings
- Add hover-to-reveal source indicator on non-AIP field groups
- Add sources footer with "Unless otherwise indicated" text + pill links
- Ensure runway table includes Width column

- [ ] **Step 5: Add click-to-copy JavaScript**

In the JavaScript section of `generate_html.py`, add:

```javascript
// Click-to-copy coordinates
document.addEventListener('click', function(e) {
    var el = e.target.closest('[data-copy-coords]');
    if (!el) return;
    var coords = el.getAttribute('data-copy-coords');
    navigator.clipboard.writeText(coords).then(function() {
        var toast = document.createElement('div');
        toast.className = 'copy-toast';
        toast.textContent = 'Copied!';
        el.appendChild(toast);
        setTimeout(function() { toast.remove(); }, 1500);
    });
});
```

Add CSS for `.copy-toast`:
```css
.copy-toast {
    position: absolute; top: -24px; left: 50%; transform: translateX(-50%);
    background: var(--navy); color: white; padding: 2px 8px;
    border-radius: 4px; font-size: 11px; pointer-events: none;
    animation: fadeOut 1.5s ease-in forwards;
}
@keyframes fadeOut { 0%{opacity:1} 70%{opacity:1} 100%{opacity:0} }
```

- [ ] **Step 6: Add CSS for source indicators**

```css
/* Source indicators */
.source-link { color: var(--text-muted); font-size: 11px; text-decoration: none; opacity: 0; transition: opacity 0.2s; }
.source-group:hover .source-link { opacity: 0.7; }
.note .source-link, .warning .source-link { opacity: 0.6; }
@media (hover: none) { .source-link { opacity: 0.6; } }
.sources-footer { padding: 10px 14px; background: #f0ebe3; font-size: 10px; color: var(--text-muted); }
.sources-footer a { color: #1a6bc4; text-decoration: none; padding: 2px 8px; background: white; border-radius: 3px; border: 1px solid var(--border); }
```

- [ ] **Step 7: Update generate_html() function signature and build.py caller**

Change `generate_html()` to accept `meta` and `airfields` (JSON-schema). **Immediately update `build.py` to load from `airfields.json` and pass JSON-schema data to `generate_html()`.** This prevents the build from being broken between tasks. Keep the old `parse_airfields()` call in `build.py` as a fallback with `if os.path.exists(AIRFIELDS_JSON)` until Task 10 finalizes the pipeline.

Also migrate `frequency_tables` — either include them in `airfields.json` under `meta.frequency_tables` in the migration script, or keep `parse_frequency_tables()` as a standalone call for now.

- [ ] **Step 8: Run all HTML tests**

Run: `python -m pytest tests/test_html.py -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 9: Build and visually verify**

```bash
python build.py
open public/index.html
```

Verify: cards render correctly, source footers appear, coordinates are clickable, no airfield numbers in headers, runway width column present.

- [ ] **Step 10: Commit**

```bash
git add generate_html.py tests/test_html.py
git commit -m "feat: HTML renderer reads from JSON, adds source attribution and click-to-copy coords"
```

---

## Task 5: Update A5 PDF renderer for JSON

**Files:**
- Modify: `generate_pdf.py:1-310`

- [ ] **Step 1: Update generate_pdf.py to read from JSON schema**

Change `build_airfield_block()` to accept JSON-schema airfield dicts:
- Read from `basic_info`, `operations`, `communications`, `runways` instead of `fields` dict
- Add source footer per card: small text showing "Source: SACAA AIP (YYYY-MM-DD)" or "Sources: Multiple — see online version"
- Use the earliest `collected` date across all source objects as the card's collection date
- Update `build_cover()` to show data collection date range instead of hardcoded "Updated: 2026-03-11"

- [ ] **Step 2: Update generate_pdf() function signature**

Accept `meta` + `airfields` (JSON) instead of markdown-parsed dicts.

- [ ] **Step 3: Run existing PDF tests**

Run: `python -m pytest tests/test_pdf_styles.py -v`
Expected: PASS (styles are independent of data source)

- [ ] **Step 4: Generate and verify PDF**

```bash
python -c "
import json
from generate_pdf import generate_pdf
with open('airfields.json') as f: data = json.load(f)
generate_pdf(data['airfields'], 'test_output.pdf', meta=data['meta'])
"
```

Open `test_output.pdf` and verify cards render correctly with source footers.

- [ ] **Step 5: Commit**

```bash
git add generate_pdf.py
git commit -m "feat: A5 PDF reads from JSON, adds source footer per card"
```

---

## Task 6: Update A4 PDF renderer for JSON

**Files:**
- Modify: `generate_airfield_pdfs.py:1-400`

- [ ] **Step 1: Update to read from JSON schema**

- Remove the duplicated `TOWER_PHONES` dict (lines 41-52) — read from `communications.tower_phone`
- Change `build_airfield_pdf()` to accept JSON-schema airfield dicts
- Add per-section source text in small muted type (e.g., "Source: SACAA AIP, collected 2026-02-15")
- Add sources summary at bottom with URLs printed as text
- Show data collection date prominently

- [ ] **Step 2: Update function signature**

Accept `meta` + `airfields` (JSON). Update `generate_airfield_pdfs()` accordingly.

- [ ] **Step 3: Generate and verify**

```bash
python -c "
import json
from generate_airfield_pdfs import generate_airfield_pdfs
with open('airfields.json') as f: data = json.load(f)
generate_airfield_pdfs(data['airfields'], 'test_pdfs/', meta=data['meta'])
"
ls test_pdfs/ | head -5
```

- [ ] **Step 4: Commit**

```bash
git add generate_airfield_pdfs.py
git commit -m "feat: A4 PDFs read from JSON, add per-section source text and summary"
```

---

## Task 7: NOTAM fetching and filtering

**Files:**
- Create: `fetch_notams.py`
- Create: `tests/test_notams.py`

- [ ] **Step 1: Research available NOTAM API**

Check these in order of preference:
1. ICAO API (api.icao.int) — may require registration
2. AirportGuide NOTAM data — check if scrapable per ICAO
3. FAA NOTAM API (notams.aim.faa.gov) — may only cover US
4. OurAirports — check if they expose NOTAMs

Determine which source works for South African FA-series ICAO codes. Document the chosen source.

- [ ] **Step 2: Write failing tests for NOTAM filtering**

Create `tests/test_notams.py`:

```python
"""Tests for fetch_notams.py — NOTAM filtering and relevance ranking."""
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_notams.py -v`
Expected: FAIL

- [ ] **Step 4: Implement fetch_notams.py**

Create `fetch_notams.py` with:
- `fetch_notams_for_icao(icao)` — calls the chosen NOTAM API, returns raw NOTAMs
- `filter_notams(notams, as_of, max_items=3)` — removes expired, ranks by relevance, caps
- `rank_by_relevance(notams)` — assigns priority (high/medium/low) based on keywords:
  - HIGH: `CLSD`, `CLOSED`, `RWY.*CLSD`, `AD CLSD`, `AIRSPACE`, `DANGER AREA`, `FREQ CHANGED`
  - MEDIUM: `HR OF OPS`, `CRANE`, `OBST`, `BIRD`, `WILDLIFE`, `TEMPO`
  - LOW: `LGT U/S`, `LIGHT`, `ILS`, `VOR`, `NDB`, `DME` (instrument-only items for VFR directory)
- `fetch_all_notams(airfields_json_path)` — batch fetch for all FA-series airfields, returns dict keyed by ICAO

If the NOTAM API is unavailable or rate-limited, the function should gracefully return empty results (not fail the build).

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_notams.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add fetch_notams.py tests/test_notams.py
git commit -m "feat: NOTAM fetching with relevance filtering (max 2-3 per airfield)"
```

---

## Task 8: Add NOTAM rendering to all outputs

**Files:**
- Modify: `generate_html.py`
- Modify: `generate_pdf.py`
- Modify: `generate_airfield_pdfs.py`

- [ ] **Step 1: Add NOTAM section to HTML cards**

In `build_airfield_card()`, after warnings and before contact, add:

```python
# NOTAMs (amber section)
notams = airfield.get('notams', {})
notam_items = notams.get('items', [])
if notam_items:
    html += '    <div class="notams-section">\n'
    html += '    <div class="section-title notam-title">NOTAMs</div>\n'
    for notam in notam_items[:3]:
        html += f'    <div class="notam-item">{escape(notam["text"])}'
        if notam.get("expiry"):
            html += f' <span class="notam-expiry">(until {escape(notam["expiry"])})</span>'
        html += '</div>\n'
    all_url = notams.get('all_notams_url', '')
    if all_url:
        html += f'    <a class="notam-all-link" href="{escape(all_url)}" target="_blank">See all NOTAMs ↗</a>\n'
    fetched = notams.get('fetched', '')
    if fetched:
        html += f'    <div class="notam-fetched">NOTAMs as of {escape(fetched[:10])}</div>\n'
    html += '    </div>\n'
```

Add CSS:
```css
.notams-section { padding: 8px 14px; background: #fffbeb; border-bottom: 1px solid var(--border); }
.notam-title { color: #92400e; }
.notam-item { font-size: 12px; color: #92400e; font-weight: 500; margin-bottom: 4px; }
.notam-expiry { font-weight: 400; color: var(--text-muted); font-size: 10px; }
.notam-all-link { display: block; font-size: 10px; color: #1a6bc4; margin-top: 4px; }
.notam-fetched { font-size: 9px; color: var(--text-muted); margin-top: 2px; }
```

- [ ] **Step 2: Add NOTAM count to A5 PDF**

In `generate_pdf.py:build_airfield_block()`, after warnings section, add:

```python
notam_items = airfield.get('notams', {}).get('items', [])
if notam_items:
    elements.append(Paragraph(
        f"[NOTAM] {len(notam_items)} active — see online version",
        styles['AFWarning']))
```

- [ ] **Step 3: Add NOTAM text to A4 PDF**

In `generate_airfield_pdfs.py`, add a NOTAMs section showing up to 2 items with text + "NOTAMs as of" date.

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add generate_html.py generate_pdf.py generate_airfield_pdfs.py
git commit -m "feat: add NOTAM rendering to HTML (amber), A5 PDF (count), A4 PDF (text)"
```

---

## Task 9: Markdown generator

**Files:**
- Create: `generate_markdown.py`
- Create: `tests/test_generate_markdown.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_generate_markdown.py`:

```python
"""Tests for generate_markdown.py — JSON to markdown output."""
from generate_markdown import generate_markdown_for_airfield, generate_markdown

def test_generates_table_format():
    af = {
        "number": 1, "name": "TEST FIELD", "icao": "FATS", "group": "Western Cape",
        "status": "active",
        "basic_info": {"coordinates": {"lat": -33.0, "lon": 18.0, "dms": "S33°00'00\" E18°00'00\""}, "elevation": "100 ft AMSL", "source": {"id": "sacaa_aip", "collected": "2026-01-01"}},
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
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement generate_markdown.py**

Generate markdown in the same table format as the original `AIRFIELD_DIRECTORY.md`, plus a "Sources" section at the bottom of each airfield entry showing data collection dates.

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git add generate_markdown.py tests/test_generate_markdown.py
git commit -m "feat: add markdown generator from JSON (for Notion import)"
```

---

## Task 10: Update build pipeline

**Files:**
- Modify: `build.py:1-105`
- Modify: `validate_data.py`

- [ ] **Step 1: Update build.py to use JSON pipeline**

Rewrite `build()` to:
1. Load `airfields.json` (not parse markdown)
2. Optionally fetch NOTAMs and inject into airfield data
3. Generate HTML from JSON
4. Generate A5 PDF from JSON
5. Generate A4 PDFs from JSON
6. Generate markdown from JSON
7. Copy markdown + PDF + favicons to `public/`

```python
import json
from shared import AIRFIELDS_JSON
from fetch_notams import fetch_all_notams

def build():
    # Load data
    with open(AIRFIELDS_JSON) as f:
        data = json.load(f)
    meta, airfields = data['meta'], data['airfields']

    # Fetch NOTAMs (graceful on failure)
    try:
        notams = fetch_all_notams(airfields)
        for af in airfields:
            icao = af.get('icao', '')
            if icao in notams:
                af['notams'] = notams[icao]
    except Exception as e:
        print(f"  NOTAM fetch failed (non-fatal): {e}")

    # Generate all outputs...
```

- [ ] **Step 2: Update validate_data.py to validate JSON**

Add a `validate_json_schema()` function that loads `airfields.json` and validates against `airfields.schema.json`. Keep existing markdown validation as a fallback.

- [ ] **Step 3: Run full build**

```bash
python build.py
```

Expected: Full build succeeds, `public/` contains index.html, PDFs, markdown.

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add build.py validate_data.py
git commit -m "feat: update build pipeline to use airfields.json with NOTAM injection"
```

---

## Task 11: Final verification and cleanup

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v
```

- [ ] **Step 2: Run validation**

```bash
python validate_data.py
```

- [ ] **Step 3: Build and verify all outputs**

```bash
python build.py
```

Open `public/index.html` — verify:
- Source footers on every card
- ↗ indicators on non-AIP notes/warnings
- Click-to-copy coordinates works
- Runway tables include width
- No airfield numbers in headers
- NOTAMs displayed in amber (if any were fetched)
- "Unless otherwise indicated" wording in footer

- [ ] **Step 4: Verify PDF outputs**

Open `public/Airfield_Directory.pdf` — verify source footers on A5 cards.
Open one file from `public/airfield-pdfs/` — verify per-section sources on A4.

- [ ] **Step 5: Add .superpowers to .gitignore**

```bash
echo ".superpowers/" >> .gitignore
git add .gitignore
```

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup and verification for source attribution feature"
```

- [ ] **Step 7: Summary**

The feature branch `feature/source-attribution` is ready for review. Key changes:
- `airfields.json` is the new single source of truth (276 airfields)
- All 4 renderers (HTML, A5 PDF, A4 PDF, markdown) read from JSON
- Source attribution on every card with verification links
- Build-time NOTAM fetching with relevance filtering
- Click-to-copy coordinates
- Mobile-first card layout improvements
