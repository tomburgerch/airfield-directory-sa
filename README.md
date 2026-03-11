# South African Airfield Directory

A printable A5 PDF reference guide for VFR pilots in South Africa. Covers the Western Cape, southern coast (Garden Route through KwaZulu-Natal), and all major controlled aerodromes nationwide.

## Features

- **94 airfields** across 14 geographic groups
- Western Cape airfields (Groups 1–8), Eastern Cape & Garden Route coast (Groups 9–10), KwaZulu-Natal (Group 11), and all major controlled aerodromes (Groups 12–14)
- One-page-per-airfield format with key info, runway data, and aerodrome diagrams
- Clickable table of contents with page numbers
- Frequency quick-reference sheets for Cape Town, Eastern Cape, KZN, and Gauteng areas
- Compact A5 format suitable for kneeboard printing

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate the PDF
python generate_pdf.py
```

The output file `Airfield_Directory_A5.pdf` will be created in the project root.

## Validation

Check data quality and consistency:

```bash
python validate_data.py
```

This validates ICAO codes, coordinates, missing fields, and data freshness.

## Project Structure

```
├── AIRFIELD_DIRECTORY.md    # Source data (markdown)
├── generate_html.py         # Searchable HTML website generator
├── generate_pdf.py          # PDF generation script
├── build.py                 # Vercel build script (HTML + downloads)
├── parse_markdown.py        # Markdown → structured data parser
├── validate_data.py         # Data validation & freshness checks
├── diagrams_util.py         # Aerodrome diagram lookup & embedding
├── diagrams/                # Aerodrome diagram images (PNG)
├── favicon.svg              # Site favicon
├── tests/                   # Test suite
├── requirements.txt         # Python dependencies
└── .github/workflows/       # CI/CD (PDF release automation)
```

## Updating Airfield Information

All airfield data lives in `AIRFIELD_DIRECTORY.md`. To update and republish:

### 1. Edit the source data

Each airfield entry in `AIRFIELD_DIRECTORY.md` follows this structure:

```markdown
### N. AIRFIELD NAME (ICAO)
| Field | Detail |
|---|---|
| **ICAO** | FAXX |
| **Coordinates** | S33°00'00" E18°00'00" |
| **Elevation** | 100 ft AMSL |
| **Frequencies** | **123.4 MHz** |
...
```

### 2. Validate your changes

```bash
python validate_data.py
```

This checks ICAO codes, coordinates, missing fields, and data consistency.

### 3. Run the tests

```bash
python -m pytest tests/ -v
```

### 4. Rebuild the outputs

```bash
# Regenerate the searchable HTML website (for local preview)
python generate_html.py

# Regenerate the printable A5 PDF
python generate_pdf.py

# Or build the full Vercel deployment bundle (HTML with embedded diagrams + downloads)
python build.py
```

The website automatically shows the date it was last built ("Updated DD Mon YYYY") so users know how current the data is.

### 5. Deploy

Push to `main` and Vercel will automatically rebuild and deploy the site. The build runs `python build.py` which parses the markdown, embeds diagrams, and generates a self-contained `index.html`.

## Data Sources

- [SACAA AIP](https://www.caa.co.za/) — official aeronautical information
- [OurAirports](https://ourairports.com/) — community airport database (CC BY-SA 4.0)
- [OpenAIP](https://www.openaip.net/) — open aviation database
- [AirportGuide](https://airportguide.com/) — airport information
- [AvCom Forums](https://www.avcom.co.za/phpBB3/) — South African pilot community

## Disclaimer

**NOT FOR NAVIGATION.** Always verify information against the current SACAA AIP, NOTAMs, and airfield operators before flight. Data marked with ❓ could not be independently verified.

## License

MIT — see [LICENSE](LICENSE). Aerodrome diagrams from SACAA AIP may have separate terms.
