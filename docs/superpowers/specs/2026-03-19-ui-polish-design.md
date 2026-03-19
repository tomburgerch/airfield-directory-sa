# UI Polish — Design Spec

## Problem

The airfield directory header is visually heavy — two dense dark rows with 8 filter pills, 3 sort buttons, labels, and separators all competing for attention. The info grid inside cards feels like a spreadsheet. TOC links scroll cards behind the sticky header. Website links are shown redundantly in both the card body and source footer.

## Changes

### 1. Slim Header + Light Filter Strip

**Current:** Two dark rows — logo/search/actions on top, filters/sort/date below. Everything dark background, lots of visual weight.

**New:** Split into two visually distinct sections:

**Dark header row (`.header-top`):**
- Remove the `<span>SA Airfield Directory</span>` from the `<h1>` tag. Also remove the CSS rule `.site-header h1 span`. The page `<title>` already contains the full name.
- Logo text "Wagyu Wings" (gold, bold, links to wagyuwings.com)
- Search box (same styling, takes more horizontal space now)
- Download dropdown (keep existing `.dl-dropdown` structure)
- Contact: keep existing `.contact-tip` hover tooltip but restyle as a small `?` or `i` icon instead of a text button labeled "Contact"

**Light filter strip (`.header-bottom`):**
- `.header-bottom` gets its own background override: `background: #f5f3ee` (warm cream). The parent `<header class="site-header">` keeps its dark background for `.header-top`.
- Bottom border: `1px solid #e5e0d5`
- Filter pills: `background: white`, `border: 1px solid #d4cfc5`, `border-radius: 14px`, `color: #6b6560`, `font-weight: 500`
- Active filter pill: `background: #1a1a1a`, `color: white`, `border-color: #1a1a1a`
- Sort buttons: same pill style as filters, active sort gets same dark fill
- Separator between filters and sort: thin vertical line (`#d4cfc5`)
- Right-aligned: `<span class="updated">` reformatted to show "276 airfields · Mar 2026"
- Keep "Sort:" label to distinguish sort buttons from filter toggles on mobile where pills wrap. Remove "Filter:" label.

Both rows remain sticky together inside the same `<header>` element.

**Mobile (`@media max-width: 600px`):** Pills wrap naturally. The light background makes wrapping less visually heavy than the current dark second row.

**JS impact:** The `#search-count` and `#filter-count` elements stay in the filter strip. JS continues to populate them during search/filter — no JS changes needed. The always-visible "276 airfields" text is the existing `.updated` span, just reformatted. During active search/filter, the JS-populated count replaces it visually (existing behavior).

### 2. Scroll Offset Fix

Add CSS `scroll-margin-top` to `.airfield-card` to account for the sticky header height. The implementer should measure the rendered header height after the restructuring and set the value accordingly — expected to be approximately 90–100px. Use a round value that provides a small visual gap.

```css
.airfield-card { scroll-margin-top: 100px; }
```

This fixes both TOC link clicks and direct page loads with `#af-N` hash URLs.

### 3. Remove Duplicate Website Links

Remove the `.web-links` rendering block from `build_airfield_card()` (the section that outputs website links in the card body). These links are already rendered as pill links in the source footer at the bottom of each card.

The `extract_links()` function at the top of `generate_html.py` is already unused (dead code from the pre-JSON era) and can be safely deleted.

### 4. Tighten Info Grid

**All label/value mappings (complete list):**

| Current Label | New Label | Notes |
|---------------|-----------|-------|
| Coordinates | Coords | Shortened |
| Elevation | Elevation | Unchanged |
| Frequency | Freq | Shortened |
| Joining Alt | Joining | Shortened |
| Circuit Alt | Circuit | Shortened |
| Night Ops | Night | Shortened |
| Fuel | Fuel | Unchanged |
| Hours | Hours | Unchanged |
| Tower Tel | Tower | Shortened |

**Label column CSS:**
- Width: 90px (down from 120px)
- Font size: 11px (down from 13px)
- Color: `#8a8480` (lighter than current `#6b6560`)
- Font weight: 500

**Value column CSS:**
- Font size: 12.5px (down from 13px)
- Color: `#1a1a1a` (full contrast — unchanged)
- Elevation stays bold (`font-weight: 700`)
- Frequency stays gold bold (`#b8860b`)

**Parenthetical details:**
- Many values already contain parenthetical text in the JSON data strings (e.g., "1800 ft AMSL (overhead join from the east)"). No parsing needed — just style literal `(...)` content.
- Implementation: after rendering the value string, use a regex replace to wrap text inside parentheses in a `<span>` with class `detail`: `re.sub(r'\(([^)]+)\)', r'<span class="detail">(\1)</span>', value)`
- CSS for `.detail`: `font-size: 11px; color: #8a8480`

**Spacing:**
- Row gap: 1px (down from 3px)
- Padding: 10px 14px (down from 12px 14px)

**Mobile (`@media max-width: 600px`):**
- Label column: 80px (down from current 100px mobile override, matching the tighter desktop proportions)

## Files Changed

| File | Changes |
|------|---------|
| `generate_html.py` (CSS section) | Filter strip background, pill restyle, info grid tightening, scroll-margin-top, `.detail` class, mobile breakpoint update |
| `generate_html.py` (header HTML in `generate_html()`) | Remove subtitle span, restyle contact, reformat `.updated` text |
| `generate_html.py` (build_airfield_card) | Remove web-links section, update info grid labels, add `.detail` span wrapping |
| `generate_html.py` (top-level) | Delete unused `extract_links()` function |

## What Stays the Same

- All filter and sort functionality (same data attributes, same JS logic)
- Card body layout (runways, warnings, notes, diagram, contact, source footer)
- FIR section, TOC, disclaimer, back-to-top
- Source attribution (footers, pill links, ↗ indicators)
- All other renderers (PDF, markdown) — untouched
- Print mode (`@media print`) rules — header is already hidden in print

## Testing

After changes, verify:
- All 8 filters still work (click to activate, click again to deactivate)
- Combined filters narrow results correctly
- Sort buttons (Province, A-Z, Nearest) still work
- Search still filters and shows count
- Download dropdown still opens
- TOC links scroll card into view with header visible (not hidden behind sticky header)
- Direct page load with `#af-2` in URL scrolls correctly
- Contact info still accessible via hover/tap
- Website links appear only in source footer, not duplicated in card body
- Info grid labels are shorter and lighter, values remain legible
- No visual regressions on mobile (390px) or desktop (1280px)
- Print mode: header and filter strip do not appear
