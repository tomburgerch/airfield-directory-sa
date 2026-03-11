# Western Cape Airfield Directory

A printable A5 PDF reference guide for VFR pilots in the Western Cape, South Africa. Compiled for pilots flying from Morningstar Airfield (ZA-0120).

## Features

- **70 airfields** across 8 geographic groups
- One-page-per-airfield format with key info, runway data, and aerodrome diagrams
- Clickable table of contents with page numbers
- Frequency quick-reference sheet for the Cape Town area
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
├── generate_pdf.py          # PDF generation script
├── validate_data.py         # Data validation & freshness checks
├── diagrams/                # Aerodrome diagram images (PNG)
├── tests/                   # Test suite
├── requirements.txt         # Python dependencies
└── .github/workflows/       # CI/CD (PDF release automation)
```

## Adding or Updating Airfields

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

After editing, run `python validate_data.py` to check for issues, then `python generate_pdf.py` to rebuild the PDF.

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
