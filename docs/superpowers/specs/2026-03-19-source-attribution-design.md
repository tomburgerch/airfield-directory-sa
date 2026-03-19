# Source Attribution & Data Provenance — Design Spec

## Problem

The airfield directory presents information (coordinates, frequencies, runway data, notes) with no indication of where it came from. A pilot looking at the data has no way to assess its credibility or verify it independently. For safety-critical aviation data, this is a significant gap.

## Solution

Add clear, per-airfield source attribution that answers two questions:
1. **Provenance** — where did this specific data come from?
2. **Verification** — where can I go to check it myself?

## Approach: Unified Data File (Approach B)

Migrate from markdown-as-source-of-truth to a structured `airfields.json`. The markdown becomes a generated output (for Notion import). All three renderers (HTML, PDF, markdown) read from JSON.

### Why

- Source annotations are co-located with the data they describe
- Single source of truth for all renderers
- Natural place for data collection dates, verification status
- Easier to validate, lint, and automate updates
- The markdown was a great bootstrapping format but doesn't scale for structured metadata

## Data Model

### `airfields.json` — Top-Level Structure

```json
{
  "meta": {
    "version": "2.0",
    "last_full_scan": "2026-03-19",
    "source_registry": { ... }
  },
  "airfields": [ ... ]
}
```

### Source Registry

Defined once at the top level. Maps short IDs to full metadata. Sources with `url_template` can auto-generate per-airfield links using `{icao}` placeholder.

**Authority levels:**
- `official` — Government/regulatory sources (SACAA AIP). Verified defaults to `true`.
- `community` — Crowd-sourced or user-generated (OurAirports, AvCom, flying clubs). Verified defaults to `false`.

```json
"source_registry": {
  "sacaa_aip": {
    "name": "SACAA AIP",
    "url_template": "https://caasanwebsitestorage.blob.core.windows.net/aerodrone-and-helicompter-directory/{icao}AD2.pdf",
    "authority": "official",
    "description": "South African Civil Aviation Authority Aeronautical Information Publication"
  },
  "ourairports": {
    "name": "OurAirports",
    "url_template": "https://ourairports.com/airports/{icao}/",
    "authority": "community",
    "license": "CC BY-SA 4.0"
  },
  "skyvector": {
    "name": "SkyVector",
    "url_template": "https://skyvector.com/airport/{icao}",
    "authority": "community"
  },
  "airportguide": {
    "name": "AirportGuide",
    "url_template": "https://airportguide.com/airport/info/{icao}",
    "authority": "community"
  },
  "avcom": {
    "name": "AvCom Forum",
    "url_base": "https://www.avcom.co.za/phpBB3/",
    "authority": "community"
  }
}
```

Note: The `aerodrone-and-helicompter-directory` path contains typos — these are in the actual SACAA upstream URL, not a spec error.

Notes:
- `url_template` with `{icao}` — auto-generates links for airfields with proper ICAO codes (FA-series). Skipped for ZA-series codes.
- Custom/one-off sources (flying club websites) use inline `url` on the source object instead of a registry ID.

### Airfield Entry

Each airfield has grouped sections, each with a `source` object.

```json
{
  "number": 2,
  "name": "STELLENBOSCH AIRFIELD",
  "icao": "FASH",
  "group": "Western Cape",
  "status": "active",

  "basic_info": {
    "coordinates": {
      "lat": -33.9806,
      "lon": 18.8228,
      "dms": "S33°58'50\" E18°49'22\""
    },
    "elevation": "321 ft AMSL",
    "mag_var": "23°W",
    "ref_temp": "15°C",
    "source": { "id": "sacaa_aip", "collected": "2026-02-15", "verified": true }
  },

  "operations": {
    "access": "Private — Club members and training only",
    "hours": "MON–FRI 0700–1500",
    "fuel": "AVGAS 100LL, Aeroshell Oil ASO W100",
    "fuel_hours": "MON–SUN 0600–1600",
    "night_ops": false,
    "fire_cat": "Category 2",
    "joining_alt": "1800 ft AMSL",
    "circuit_alt": "1300 ft AMSL",
    "source": { "id": "sacaa_aip", "collected": "2026-02-15", "verified": true }
  },

  "communications": {
    "primary_freq": "119.3 MHz",
    "frequencies_table": [
      { "service": "Aerodrome Traffic", "freq": "119.3 MHz" }
    ],
    "tower_phone": null,
    "source": { "id": "sacaa_aip", "collected": "2026-02-15", "verified": true }
  },

  "runways": {
    "data": [
      {
        "rwy": "01", "length": "760 m", "width": "16 m",
        "surface": "Asphalt", "strength": "LCN 20", "circuit": "Left"
      },
      {
        "rwy": "19", "length": "760 m", "width": "16 m",
        "surface": "Asphalt", "strength": "LCN 20", "circuit": "Right"
      }
    ],
    "source": { "id": "sacaa_aip", "collected": "2026-02-15", "verified": true }
  },

  "notes": [
    {
      "text": "Western circuit — all circuits flown WEST of and within 2.5 NM of FASH",
      "source": { "id": "sacaa_aip", "collected": "2026-02-15", "verified": true }
    },
    {
      "text": "Club reports increased microlight activity on weekends",
      "source": { "url": "https://stelfly.co.za/", "name": "Stellenbosch FC", "collected": "2026-03-10", "verified": false }
    }
  ],

  "warnings": [
    {
      "text": "Poles 4 m high erected 150 m from final approach of RWY 01",
      "source": { "id": "sacaa_aip", "collected": "2026-02-15", "verified": true }
    }
  ],

  "contact": {
    "name": "Stellenbosch Flying Club",
    "phone": "(021) 880-1907",
    "address": "P O Box 12653, DIE BOORD 7613",
    "source": { "url": "https://stelfly.co.za/", "name": "Stellenbosch FC", "collected": "2026-03-10" }
  },

  "links": {
    "websites": [
      { "label": "Stellenbosch Flying Club", "url": "https://stelfly.co.za/" },
      { "label": "Morningstar FC – Stellenbosch page", "url": "https://morningstarflyingclub.co.za/stellenbosch-airfield/" }
    ]
  },

  "diagram": {
    "file": "diagrams/FASH.png",
    "source": { "id": "sacaa_aip", "collected": "2026-02-15" }
  },

  "notams": []
}
```

### Source Object Schema

Source objects appear in two patterns:
1. **Per-group** — on field group objects (`basic_info.source`, `operations.source`, `runways.source`, `communications.source`, `contact.source`, `diagram.source`). One source covers all fields in the group.
2. **Per-item** — on individual entries in `notes` and `warnings` arrays, since different notes may come from different sources.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | no | Key into `source_registry`. Use for well-known sources. |
| `url` | string | no | Direct URL. Use for one-off sources (flying club sites). |
| `name` | string | no | Display name. Required if `id` is absent. |
| `collected` | string (YYYY-MM-DD) | yes | Date the data was gathered — NOT the generation date. |
| `verified` | boolean | no | Whether the data has been independently verified. |

**Validation rules:**
- Exactly one of `id` or `url` must be present. If both are absent, or both are present, the schema is invalid.
- If `id` is present, the registry provides `name` and `url_template`. The `name` field on the source object is ignored.
- If `url` is present, `name` is required (the registry cannot supply it).
- If `verified` is absent, it defaults to `true` when the source's `authority` is `"official"`, and `false` otherwise. For inline sources (using `url` instead of `id`), it defaults to `false`.

### Status Field

Valid values for `status`:
- `active` — operational airfield
- `closed` — permanently closed (renders with CLOSED banner)
- `military` — military airfield (restricted access)
- `decommissioned` — no longer exists

### Coordinates

The `coordinates` object stores both decimal (`lat`/`lon`) and DMS (`dms`). **Decimal is canonical.** DMS is for display. If they disagree, decimal takes precedence. Click-to-copy uses decimal format.

### Links: Computed at Build Time

The `links` section is **not stored** in `airfields.json`. It is computed at build time by the renderers, using the source registry's `url_template` fields and the airfield's `icao` code. This avoids redundant data that could drift out of sync.

Exception: `links.websites` (curated per-airfield URLs) and `links.aip` (when the URL doesn't follow the standard template) ARE stored, since they can't be auto-generated.

## HTML Card Design

### Layout (Mobile-First)

Single-column card, touch-friendly. No airfield number displayed (internal only).

**Header:**
- Airfield name (bold, 15px)
- ICAO code | Access type (muted, 11px)

**Field Groups (top to bottom):**
1. **Basic Info** — Coordinates (click-to-copy), Elevation, Mag Var
2. **Operations** — Frequency, Joining Alt, Circuit Alt, Fuel, Hours, Night Ops
3. **Communications** — Frequencies table (if multiple)
4. **Runways** — Table with: RWY, Length, Width, Surface, Strength (if available), Circuit
5. **Notes** — Individual note lines
6. **Warnings** — Red background, bold
7. **Contact** — Name, phone, address
8. **Diagram** — Aerodrome diagram image (if available)
9. **Sources Footer** — Default source note + verification links

### Source Attribution UX

**Core principle:** AIP is the assumed default. Only non-AIP sources get visual indicators.

**Inline source indicator:**
- A subtle `↗` arrow appears next to notes, warnings, or field groups sourced from non-AIP sources
- On desktop: visible on hover for field groups; always visible on individual notes/warnings
- On mobile: always visible (no hover available)
- Clicking the arrow opens the source URL in a new tab
- Tooltip on hover shows source name (e.g., "Source: Stellenbosch Flying Club website")

**Sources footer (bottom of every card):**
- For licensed airfields (FA-series ICAO): "Unless otherwise indicated, data sourced from **SACAA AIP** (collected YYYY-MM-DD)"
- For unlicensed airfields (ZA-series): "No official SACAA AIP entry for this airfield. Data compiled from community sources."
- Pill-style links to all verification sources: AIP (if exists), OurAirports, SkyVector, plus any curated websites

### Coordinates Click-to-Copy

Clicking coordinates copies them in decimal degrees format (e.g., `-33.9806, 18.8228`) to clipboard — compatible with Garmin, ForeFlight, and Google Maps. A brief "Copied!" toast appears for 1.5 seconds.

### Runway Table

Always includes: RWY, Length, Width, Surface, Circuit. Adds Strength column if data available for any runway. Right-hand circuits highlighted in red.

## PDF Design

### A5 Compact PDF

Same field groupings as HTML. Source attribution appears as:
- Small footer text per card: "Source: SACAA AIP (YYYY-MM-DD)" or "Sources: Multiple — see online version"
- No inline source arrows (too small at A5 scale)
- Data collection date in footer, not generation date

### A4 Individual PDFs

More space available:
- Source listed per section in small muted text
- Sources summary at bottom with URLs printed as text (for offline reference)
- Data collection date prominent

## Markdown Output (for Notion)

Auto-generated from `airfields.json`. Includes:
- All airfield data in the current table format
- Sources section at the bottom of each airfield entry
- Data collection dates noted

## Data Sources — Scan List

These sources should be re-scanned on every data refresh:

### Tier 1: Official
| Source | Type | Auto-linkable | Notes |
|--------|------|---------------|-------|
| SACAA AIP | PDF per airfield | Yes (`{icao}AD2.pdf`) | Only for licensed aerodromes (FA-series). Some major airports use a different URL container. |

### Tier 2: Structured Community
| Source | Type | Auto-linkable | Notes |
|--------|------|---------------|-------|
| OurAirports | Web + CSV bulk data | Yes (`/airports/{icao}/`) | Good coverage, crowd-sourced. CSV at davidmegginson.github.io/ourairports-data/ |
| SkyVector | Web | Yes (`/airport/{icao}`) | Charts and basic info |
| AirportGuide | Web | Yes (`/airport/info/{icao}`) | Frequencies, runway info, NOTAMs |

### Tier 3: Community / Manual
| Source | Type | Auto-linkable | Notes |
|--------|------|---------------|-------|
| AvCom Forum | Forum threads | No (manual thread links) | De facto SA GA community. Search: `site:avcom.co.za {ICAO}` |
| Flying club / operator websites | Per-airfield | No (manually curated) | Discover via Google: `"{airfield name}" airfield site` |
| Google Search | Discovery | N/A | Used to find per-airfield websites, not a data source itself |
| Local pilot feedback | Manual | No | Verified facts from airfield operators / pilots |

### Not Usable
| Source | Reason |
|--------|--------|
| SkyDemon | App-only, no web-accessible database or API |
| ATNS eAIP | URLs are AIRAC-versioned (not stable for linking) |
| OpenAIP | Web URLs use internal MongoDB IDs, not ICAO codes. Could be used via API with a lookup table. |

## Migration Plan

### Phase 1: Data Migration
1. Write a migration script (`migrate_to_json.py`) that parses `AIRFIELD_DIRECTORY.md` + `verified_facts.json` + `tower_data.py` into `airfields.json`
2. Enrich with source annotations:
   - Airfields with `AIP Link` / `AIP Ref` in markdown → source = `sacaa_aip`
   - Airfields with website links (currently in `fields_raw`) → extract to `links.websites`
   - Tower phone data from `tower_data.py` (and the duplicate in `generate_airfield_pdfs.py`) → consolidate into `communications.tower_phone` with source from inline comments
   - AvCom forum links in notes → extract and annotate with per-item sources
   - Remaining fields without explicit sources → default to `sacaa_aip` for FA-series, no source for ZA-series (to be manually filled)
3. Verification: render JSON back to markdown and diff against original to catch data loss
4. Create `airfields.schema.json` (JSON Schema) for automated validation

### Phase 2: HTML Renderer (first, since it's the primary output)
5. Update `generate_html.py` to read from `airfields.json` instead of parsing markdown
   - Replace `fields_raw` link extraction with structured `links.websites`
   - Replace `TOWER_PHONES` dict lookup with `communications.tower_phone`
   - Add source attribution UX (inline arrows, sources footer)
   - Add click-to-copy coordinates
6. Run existing `test_html.py` tests + new tests for source rendering
7. Verify HTML output manually against current live site

### Phase 3: PDF Renderers
8. Update `generate_pdf.py` (A5) to read from `airfields.json` — add source footer per card
9. Update `generate_airfield_pdfs.py` (A4) — add per-section source text and sources summary
10. Run existing PDF tests + verify output

### Phase 4: NOTAM Integration
11. Research and select NOTAM API source for South African airfields
12. Write `fetch_notams.py` — fetches NOTAMs per ICAO code, filters by relevance, caps at 2-3 per airfield
13. Integrate into `airfields.json` pipeline — NOTAMs fetched fresh on each build
14. Add NOTAM rendering to HTML (amber section), A5 PDF (count only), A4 PDF (summary text)

### Phase 5: Markdown Generator & Pipeline
15. Write `generate_markdown.py` to produce markdown from JSON (for Notion import)
16. Update `build.py` to orchestrate: fetch NOTAMs → JSON → HTML + A5 PDF + A4 PDFs + Markdown
17. Update `validate_data.py` to validate `airfields.json` schema
18. Keep `parse_markdown.py` functional during transition (can be removed once JSON is stable)

## Testing

- `airfields.schema.json` validation on every build (catches missing fields, invalid sources)
- All 276 airfields render correctly in HTML, A5 PDF, A4 PDF, and markdown
- Migration verification: diff generated markdown against original `AIRFIELD_DIRECTORY.md`
- Click-to-copy coordinates in HTML
- Source link generation for FA-series vs ZA-series airfields
- Hover/tap behavior for source indicators (desktop and mobile)
- Data collection dates appear (not generation dates)
- NOTAM filtering: verify routine/recurring NOTAMs are excluded, priority NOTAMs surface
- NOTAM staleness: expired NOTAMs excluded, fetch timestamp displayed
- Cross-check against existing test suite (`test_html.py`, `test_pdf_styles.py`, `test_parse.py`)

## Branch Strategy

All work on a feature branch (`feature/source-attribution`) to isolate from main. The migration touches the core data pipeline, so clean rollback is important. The phased approach means each renderer can be validated independently before moving to the next.

## NOTAMs — Build-Time Integration

NOTAMs are fetched at build time and included as a point-in-time snapshot. They are NOT live-updating.

### Data Source

Fetch from an available NOTAM API (ICAO API, AirportGuide, or OurAirports — to be determined during implementation based on API availability for South African airfields). Fall back to SACAA/ATNS if no API is suitable.

### Relevance Filtering

Raw NOTAMs are filtered and ranked before display. The goal is to show only NOTAMs a pilot would actually care about when planning a flight to that airfield.

**Prioritize (show):**
- Runway closures or restrictions
- Airspace restrictions or temporary danger areas
- Frequency changes
- Operating hours changes
- Temporary hazards (obstacles, wildlife, construction affecting operations)

**Deprioritize (hide):**
- Recurring/routine items (lights unserviceable, cranes, long-running construction)
- NOTAMs that have been reissued identically multiple times
- NOTAMs that are clearly irrelevant to VFR GA traffic (e.g., ILS out of service at a VFR-only field)

**Display rules:**
- Maximum 2-3 NOTAMs per airfield card
- Each NOTAM shows: summary text, effective/expiry dates
- "See all NOTAMs →" link to the official SACAA/ATNS NOTAM page for that airfield
- Clear "as of" timestamp showing when NOTAMs were fetched

### Schema

```json
"notams": {
  "fetched": "2026-03-19T08:30:00Z",
  "items": [
    {
      "id": "A1234/26",
      "text": "RWY 01/19 CLSD FOR MAINTENANCE",
      "effective": "2026-03-18",
      "expiry": "2026-03-25",
      "priority": "high"
    }
  ],
  "all_notams_url": "https://www.caa.co.za/..."
}
```

### Rendering

**HTML:** NOTAMs section appears between Warnings and Contact. Amber/yellow styling to distinguish from permanent warnings (red). "See all NOTAMs →" link at the end.

**A5 PDF:** Show count only ("2 active NOTAMs — see online version"). Too small for full text.

**A4 PDF:** Show up to 2 NOTAMs with text. Include "NOTAMs as of YYYY-MM-DD" and "See online version for current NOTAMs."

**Staleness:** Expired NOTAMs are automatically excluded at build time. The `fetched` timestamp is always shown so pilots know the currency.
