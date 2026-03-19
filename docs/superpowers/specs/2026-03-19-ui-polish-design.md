# UI Polish — Design Spec

## Problem

The airfield directory header is visually heavy — two dense dark rows with 8 filter pills, 3 sort buttons, labels, and separators all competing for attention. The info grid inside cards feels like a spreadsheet. TOC links scroll cards behind the sticky header. Website links are shown redundantly in both the card body and source footer.

## Changes

### 1. Slim Header + Light Filter Strip

**Current:** Two dark rows — logo/search/actions on top, filters/sort/date below. Everything dark background, lots of visual weight.

**New:** Split into two visually distinct sections:

**Dark header row (top):**
- Logo text "Wagyu Wings" (gold, bold) — no subtitle ("SA Airfield Directory" is in `<title>`)
- Search box (same styling, takes more horizontal space now)
- Single compact download button ("↓ PDF" or dropdown trigger)
- Contact moves to a small icon/tooltip or footer — not a header button

**Light filter strip (below header):**
- Background: `#f5f3ee` (warm cream, matches page background)
- Bottom border: `1px solid #e5e0d5`
- Filter pills: white background, `1px solid #d4cfc5` border, `border-radius: 14px`, muted text (`#6b6560`)
- Active filter pill: dark background (`#1a1a1a`), white text
- Sort buttons: same pill style, active sort gets dark fill
- Separator between filters and sort: thin vertical line
- Right-aligned: count + date ("276 airfields · Mar 2026") in small muted text
- No category labels ("Filter:", "Sort:") — the grouping is self-evident

Both rows remain `position: sticky; top: 0` together (wrapped in the same `<header>`).

**Mobile:** Pills wrap naturally. The light strip takes less visual space than the current dark second row.

### 2. Scroll Offset Fix

Add CSS `scroll-margin-top` to `.airfield-card` to account for the sticky header height. Value should be ~100px (header + filter strip + small gap). This ensures TOC anchor links and any `#af-N` hash navigation positions the card header visibly below the sticky header.

```css
.airfield-card { scroll-margin-top: 100px; }
```

### 3. Remove Duplicate Website Links

Remove the `.web-links` div from `build_airfield_card()`. These links (flying club websites, AIP PDFs) are already rendered as pill links in the source footer at the bottom of each card. Showing them twice adds clutter without value.

The `extract_links()` function and related code can be removed from `generate_html.py`.

### 4. Tighten Info Grid

**Label column:**
- Width: 90px (down from 120px)
- Font size: 11px (down from 13px)
- Color: `#8a8480` (lighter than current `#6b6560`)
- Font weight: 500
- Shorter text: "Coords" not "Coordinates", "Joining" not "Joining Alt", "Circuit" not "Circuit Alt"

**Value column:**
- Font size: 12.5px (down from 13px)
- Color: `#1a1a1a` (full contrast — unchanged)
- Elevation stays bold
- Frequency stays gold bold (`#b8860b`)

**Parenthetical details:**
- Inline after the value, not on their own
- Style: 11px, color `#8a8480` — visually subordinate
- Examples: "1800 ft AMSL *(overhead join from east)*", "AVGAS 100LL *(SFC: +27 21 880)*"

**Spacing:**
- Row gap: 1px (down from 3px)
- Padding: 10px 14px (down from 12px 14px)

## Files Changed

| File | Changes |
|------|---------|
| `generate_html.py` (CSS section) | New filter strip styles, updated info grid styles, scroll-margin-top |
| `generate_html.py` (header HTML) | Restructure header into slim dark + light strip |
| `generate_html.py` (build_airfield_card) | Remove web-links section, update info grid labels/classes |
| `generate_html.py` (JS) | No changes needed — filter/sort JS works on data attributes, not DOM structure |

## What Stays the Same

- All filter and sort functionality (same data attributes, same JS logic)
- Card body layout (runways, warnings, notes, diagram, contact, source footer)
- FIR section, TOC, disclaimer, back-to-top
- Source attribution (footers, pill links, ↗ indicators)
- Mobile responsiveness (existing breakpoints still apply)
- All other renderers (PDF, markdown) — untouched

## Testing

After changes, verify:
- All 8 filters still work (click to activate, click again to deactivate)
- Combined filters narrow results correctly
- Sort buttons (Province, A-Z, Nearest) still work
- Search still filters and shows count
- Download dropdown still opens
- TOC links scroll card into view (not behind header)
- Contact info still accessible
- No visual regressions on mobile (390px) or desktop (1280px)
