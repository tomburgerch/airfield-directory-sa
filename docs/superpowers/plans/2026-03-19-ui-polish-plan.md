# UI Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the airfield directory header lighter, fix scroll offset for TOC links, remove duplicate website links, and tighten the info grid inside cards.

**Architecture:** All changes are in `generate_html.py` — CSS updates, HTML restructuring in the `generate_html()` function, and info grid changes in `build_airfield_card()`. No JS changes needed. Single file, four independent visual improvements.

**Tech Stack:** Python (string-based HTML generation), inline CSS

**Spec:** `docs/superpowers/specs/2026-03-19-ui-polish-design.md`

**Note:** Line numbers reference the file state before any changes. Always locate code by content matching, not line numbers.

---

## File Structure

### Modified files
| File | Responsibility |
|------|---------------|
| `generate_html.py` | All changes — CSS block, header HTML, card builder, dead code removal |
| `tests/test_html.py` | Update tests for removed web-links and new labels |

---

## Task 1: Update CSS — filter strip, info grid, scroll offset

**Files:**
- Modify: `generate_html.py:76-84` (`.site-header` — remove bottom padding)
- Modify: `generate_html.py:89-90` (`.site-header h1` — remove subtitle rule)
- Modify: `generate_html.py:194-240` (`.header-bottom` — light background, new pill styles)
- Modify: `generate_html.py:364-371` (`.airfield-card` — add scroll-margin-top)
- Modify: `generate_html.py:419-430` (`.info-grid` — tighten grid)
- Modify: `generate_html.py:641-653` (`@media max-width: 600px` — update breakpoint)
- Add new: `.detail` class for parenthetical text

- [ ] **Step 1: Update `.site-header` padding**

In the CSS string, change:
```css
/* Old */
.site-header {
    background: var(--navy);
    color: white;
    padding: 10px 0 8px;
    position: sticky;
    top: 0;
    z-index: 1100;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

/* New */
.site-header {
    background: var(--navy);
    color: white;
    padding: 10px 0 0;
    position: sticky;
    top: 0;
    z-index: 1100;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
```

- [ ] **Step 2: Remove subtitle CSS rule**

Delete this line from the CSS:
```css
.site-header h1 span { font-weight: 400; font-size: 11px; color: rgba(255,255,255,0.6); display: block; }
```

- [ ] **Step 3: Restyle `.header-bottom` as light filter strip**

Replace the entire `.header-bottom` block (lines 194–240) with:

```css
.header-bottom {
    display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
    max-width: 900px; margin: 0 auto; padding: 8px 16px;
    background: #f5f3ee;
    border-bottom: 1px solid #e5e0d5;
}
.header-bottom .filter-label {
    font-size: 10px;
    font-weight: 600;
    color: #8a8480;
    margin-right: 2px;
}
.header-bottom .filter-btn {
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 14px;
    border: 1px solid #d4cfc5;
    background: white;
    color: #6b6560;
    cursor: pointer;
    transition: all 0.15s;
    font-weight: 500;
}
.header-bottom .filter-btn:hover { border-color: #1a1a1a; color: #1a1a1a; }
.header-bottom .filter-btn.active {
    background: #1a1a1a;
    color: white;
    border-color: #1a1a1a;
    font-weight: 700;
}
.header-bottom .filter-sep {
    width: 1px;
    height: 14px;
    background: #d4cfc5;
}
#search-count {
    font-size: 10px; color: #8a8480;
    margin-left: auto;
}
#filter-count {
    font-size: 10px;
    color: #8a8480;
}
.header-bottom .updated {
    font-size: 10px; color: #a09890;
    margin-left: auto;
}
```

- [ ] **Step 4: Add `scroll-margin-top` to `.airfield-card`**

In the `.airfield-card` CSS rule (around line 364), add:
```css
.airfield-card {
    background: white;
    border-radius: 8px;
    margin: 14px 0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    overflow: hidden;
    transition: box-shadow 0.2s;
    scroll-margin-top: 100px;
}
```

- [ ] **Step 5: Tighten `.info-grid` CSS**

Replace the info-grid CSS block with:
```css
/* ── Info grid ── */
.info-grid {
    display: grid;
    grid-template-columns: 90px 1fr;
    gap: 1px 8px;
    font-size: 12.5px;
    margin-bottom: 10px;
}
.info-grid .label { font-size: 11px; font-weight: 500; color: #8a8480; }
.info-grid .value { color: #1a1a1a; }
.info-grid .value.freq { color: var(--blue); font-weight: 700; }
.info-grid .value.elev { font-weight: 700; }
.detail { font-size: 11px; color: #8a8480; }
```

- [ ] **Step 6: Update mobile breakpoint**

In `@media (max-width: 600px)`, change:
```css
/* Old */
.info-grid { grid-template-columns: 100px 1fr; font-size: 12px; }
.site-header h1 { font-size: 14px; }
.site-header h1 span { font-size: 10px; }

/* New */
.info-grid { grid-template-columns: 80px 1fr; font-size: 12px; }
.site-header h1 { font-size: 14px; }
```

Also in the same `@media` block, remove this rule (the updated text is now useful on mobile with the light strip):
```css
/* Delete this line: */
.header-bottom .updated { display: none; }
```

- [ ] **Step 7: Build and visually verify CSS changes**

```bash
source .venv/bin/activate && python build.py
```

Open `http://localhost:8091` (or start a local server) and verify the filter strip is now light-colored, pills are white with subtle borders, and the header looks slimmer.

- [ ] **Step 8: Commit**

```bash
git add generate_html.py
git commit -m "style: restyle header as slim dark + light filter strip, tighten info grid"
```

---

## Task 2: Update header HTML — remove subtitle, restyle contact, reformat updated text

**Files:**
- Modify: `generate_html.py:1453-1498` (header HTML in `generate_html()`)

- [ ] **Step 1: Remove subtitle from `<h1>`**

Change line 1456 from:
```python
html += '<h1><a href="https://wagyuwings.com" style="color:#FFD700;text-decoration:none">Wagyu Wings</a> <span>SA Airfield Directory</span></h1>\n'
```
to:
```python
html += '<h1><a href="https://wagyuwings.com" style="color:#FFD700;text-decoration:none">Wagyu Wings</a></h1>\n'
```

- [ ] **Step 2: Restyle contact as icon**

Change the contact-tip HTML (line 1471) from:
```python
html += '  <span class="contact-tip">Contact<span class="contact-tooltip">...'
```
to:
```python
html += '  <span class="contact-tip" title="Contact">?<span class="contact-tooltip"><span class="contact-tooltip-inner">Bug report or feedback?<br><a href="mailto:info@cedricwaldburger.com">info@cedricwaldburger.com</a></span></span></span>\n'
```

- [ ] **Step 3: Remove "Filter:" label, keep "Sort:" label**

Change the filter bar HTML. Remove the first filter-label line:
```python
# Remove this line:
html += '<span class="filter-label">Filter:</span>\n'
```

Keep the "Sort:" label line as-is:
```python
html += '<span class="filter-label">Sort:</span>\n'
```

- [ ] **Step 4: Reformat the `.updated` span**

Change line 1496 from:
```python
html += f'<span class="updated">Updated {build_date}</span>\n'
```
to:
```python
html += f'<span class="updated">{len(airfields)} airfields &middot; {build_date}</span>\n'
```

- [ ] **Step 5: Build and verify**

```bash
source .venv/bin/activate && python build.py
```

Open in browser. Verify: no subtitle, contact shows as "?", no "Filter:" label, "Sort:" label remains, count + date shown in filter strip.

- [ ] **Step 6: Commit**

```bash
git add generate_html.py
git commit -m "style: remove subtitle, restyle contact as icon, reformat filter strip"
```

---

## Task 3: Remove duplicate website links and dead code

**Files:**
- Modify: `generate_html.py:42-46` (delete `extract_links()`)
- Modify: `generate_html.py:500-510` (delete `.web-links` CSS)
- Modify: `generate_html.py:1251-1259` (delete web-links rendering in `build_airfield_card()`)

- [ ] **Step 1: Delete `extract_links()` function**

Remove lines 42–46:
```python
def extract_links(raw_value):
    """Extract markdown links from a raw field value, return list of (label, url)."""
    if not raw_value:
        return []
    return re.findall(r'\[([^\]]+)\]\(([^)]+)\)', raw_value)
```

- [ ] **Step 2: Delete `.web-links` CSS**

Remove these CSS rules:
```css
.web-links {
    font-size: 12px;
    margin-bottom: 8px;
    display: flex; flex-wrap: wrap; gap: 4px 14px;
}
.web-links a {
    color: var(--blue);
    text-decoration: none;
    font-weight: 600;
}
.web-links a:hover { text-decoration: underline; }
```

- [ ] **Step 3: Delete web-links rendering from `build_airfield_card()`**

Remove these lines from the card builder:
```python
    # Website links from JSON
    websites = airfield.get('links', {}).get('websites', [])
    if websites:
        html += '    <div class="web-links">\n'
        for site in websites:
            label = site.get('label', site.get('url', ''))
            url = site.get('url', '')
            html += f'      <a href="{escape(url)}" target="_blank" rel="noopener">{escape(clean_html(label))}</a>\n'
        html += '    </div>\n'
```

- [ ] **Step 4: Build and verify links only in footer**

```bash
source .venv/bin/activate && python build.py
```

Search for "Stellenbosch" in the HTML output and verify website links appear only in the source footer pills, not duplicated in the card body.

- [ ] **Step 5: Commit**

```bash
git add generate_html.py
git commit -m "refactor: remove duplicate website links and dead extract_links() code"
```

---

## Task 4: Tighten info grid labels and add parenthetical styling

**Files:**
- Modify: `generate_html.py:1209-1249` (info grid in `build_airfield_card()`)

- [ ] **Step 1: Add a helper function for parenthetical detail wrapping**

Add this right before `build_airfield_card()`:

```python
def _style_parens(value):
    """Wrap parenthetical text in a <span class="detail"> for muted styling."""
    return re.sub(r'\(([^)]+)\)', r'<span class="detail">(\1)</span>', value)
```

- [ ] **Step 2: Update info grid labels and add detail wrapping**

Replace the info grid section in `build_airfield_card()` with shortened labels and `_style_parens()` calls:

```python
    # Info grid
    grid_items = []

    # Coordinates with click-to-copy
    if coord_dms:
        coord_decimal = f"{lat}, {lon}" if lat is not None else ""
        if coord_decimal:
            grid_items.append(f'    <div class="label">Coords</div><div class="value"><span class="copy-coords" data-copy-coords="{escape(coord_decimal)}" title="Click to copy decimal coordinates">{escape(clean_html(coord_dms))}</span></div>\n')
        else:
            grid_items.append(f'    <div class="label">Coords</div><div class="value">{escape(clean_html(coord_dms))}</div>\n')

    if basic.get('elevation'):
        grid_items.append(f'    <div class="label">Elevation</div><div class="value elev">{escape(clean_html(basic["elevation"]))}</div>\n')

    if comms.get('primary_freq'):
        grid_items.append(f'    <div class="label">Freq</div><div class="value freq">{escape(clean_html(comms["primary_freq"]))}</div>\n')

    if ops.get('joining_alt'):
        grid_items.append(f'    <div class="label">Joining</div><div class="value">{_style_parens(escape(clean_html(ops["joining_alt"])))}</div>\n')

    if ops.get('circuit_alt'):
        grid_items.append(f'    <div class="label">Circuit</div><div class="value">{_style_parens(escape(clean_html(ops["circuit_alt"])))}</div>\n')

    night_val = ops.get('night_ops')
    if night_val is not None and night_val is not False:
        night_str = str(night_val) if night_val is not True else 'Yes'
        grid_items.append(f'    <div class="label">Night</div><div class="value">{escape(clean_html(night_str))}</div>\n')

    if ops.get('fuel'):
        grid_items.append(f'    <div class="label">Fuel</div><div class="value">{_style_parens(escape(clean_html(ops["fuel"])))}</div>\n')

    if ops.get('hours'):
        grid_items.append(f'    <div class="label">Hours</div><div class="value">{_style_parens(escape(clean_html(ops["hours"])))}</div>\n')

    # Tower phone from JSON
    tower_phone = comms.get('tower_phone')
    if tower_phone and has_tower:
        phone_link = f'<a href="tel:{tower_phone}" style="color:var(--green);font-weight:700;text-decoration:none">{escape(tower_phone)}</a>'
        grid_items.append(f'    <div class="label">Tower</div><div class="value">{phone_link}</div>\n')

    if grid_items:
        html += '    <div class="info-grid">\n' + ''.join(grid_items) + '    </div>\n'
```

- [ ] **Step 3: Build and verify**

```bash
source .venv/bin/activate && python build.py
```

Open in browser. Check that labels are shorter ("Coords", "Freq", "Joining", "Circuit", "Night", "Tower") and parenthetical text appears in lighter/smaller styling.

- [ ] **Step 4: Commit**

```bash
git add generate_html.py
git commit -m "style: tighten info grid labels and add parenthetical detail styling"
```

---

## Task 5: Update tests and final verification

**Files:**
- Modify: `tests/test_html.py`

- [ ] **Step 1: Update test for shortened labels**

In `tests/test_html.py`, the existing tests reference card content. No tests explicitly check for label text like "Coordinates" or "Joining Alt", so no test changes are needed for labels. However, verify there are no tests checking for `.web-links` or `extract_links`:

```bash
source .venv/bin/activate && grep -n "web.links\|extract_links" tests/test_html.py
```

Expected: no matches (these were already removed when tests were rewritten for JSON).

- [ ] **Step 2: Run full test suite**

```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short
```

Expected: 115+ passed, 5 pre-existing diagram failures, 2 skipped. No new failures.

- [ ] **Step 3: Run programmatic HTML verification**

Run the 25-check verification script (see memory: `feedback_testing_process.md`). Key checks:
- All 276 airfield cards present
- Source footers on all cards
- Click-to-copy coords present
- No airfield numbers in headers
- `data-copy-coords` attributes present

- [ ] **Step 4: Visual testing — desktop (1280px)**

Start local server and open in browser at desktop width:
```bash
cd public && python3 -m http.server 8091
```

Verify:
- Slim dark header with just logo + search + download + "?" contact
- Light filter strip with white pills below
- "Sort:" label visible, no "Filter:" label
- Airfield count + date at right end of filter strip
- All filters and sort buttons work
- Download dropdown opens
- TOC links scroll to correct position (card not hidden behind header)
- Info grid has tight labels, parenthetical details in muted text
- No website links in card body (only in source footer)

- [ ] **Step 5: Visual testing — mobile (390x844)**

Resize browser to 390x844 and verify:
- Header wraps cleanly
- Filter strip wraps pills naturally on light background
- Cards are readable with tighter info grid
- Search works, shows count
- "?" contact icon accessible

- [ ] **Step 6: Test scroll offset with hash URL**

Navigate directly to `http://localhost:8091/#af-2` and verify the FASH card header is visible below the sticky header, not hidden behind it.

- [ ] **Step 7: Commit any test updates if needed**

```bash
git add tests/test_html.py
git commit -m "test: update tests for UI polish changes"
```
