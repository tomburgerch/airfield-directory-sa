#!/usr/bin/env python3
"""
Build script for Vercel deployment.

Generates a self-contained static site in public/ with:
  - index.html: Searchable airfield directory with base64-embedded diagrams
  - Airfield_Directory_A5.pdf: Printable PDF for download
  - AIRFIELD_DIRECTORY.md: Markdown source for download
"""

import json
import os
import shutil

from generate_html import generate_html, load_airfields_json
from generate_pdf import generate_pdf
from generate_markdown import generate_markdown
from shared import BASE_DIR, MD_FILE, AIRFIELDS_JSON
from generate_airfield_pdfs import generate_airfield_pdfs
from fetch_notams import fetch_all_notams

PUBLIC_DIR = os.path.join(BASE_DIR, 'public')


def build():
    """Build the static site into public/."""
    print("=" * 50)
    print("Building SA Airfield Directory for deployment")
    print("=" * 50)

    # Clean and create output directory
    if os.path.exists(PUBLIC_DIR):
        shutil.rmtree(PUBLIC_DIR)
    os.makedirs(PUBLIC_DIR)

    # Copy favicon files
    for favicon in ['favicon.ico', 'favicon.png', 'apple-touch-icon.png', 'favicon-192.png', 'favicon-512.png']:
        src = os.path.join(BASE_DIR, favicon)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(PUBLIC_DIR, favicon))
    print("  Copied favicons")

    # Copy downloadable files
    download_links = []

    download_links.append({
        'label': 'Download Markdown',
        'href': 'AIRFIELD_DIRECTORY.md',
    })

    # Load airfield data from JSON
    print("\nLoading airfield data from JSON...")
    meta, airfields = load_airfields_json()
    print(f"  Found {len(airfields)} airfields")

    freq_tables = meta.get('frequency_tables', [])
    print(f"  Found {len(freq_tables)} frequency tables")

    # Fetch NOTAMs (graceful on failure)
    try:
        notams = fetch_all_notams(airfields)
        if notams:
            for af in airfields:
                icao = af.get('icao', '')
                if icao in notams:
                    af['notams'] = notams[icao]
            print(f"  Fetched NOTAMs for {len(notams)} airfield(s)")
        else:
            print("  No NOTAMs available (API not configured)")
    except Exception as e:
        print(f"  NOTAM fetch failed (non-fatal): {e}")

    # Generate compact PDF
    pdf_path = os.path.join(PUBLIC_DIR, 'Airfield_Directory.pdf')
    print("\nGenerating compact PDF...")
    generate_pdf(airfields, pdf_path, meta=meta)
    pdf_size = os.path.getsize(pdf_path) / 1024
    print(f"  PDF: {pdf_size:.0f} KB")
    download_links.insert(0, {
        'label': 'Download PDF (Offline)',
        'href': 'Airfield_Directory.pdf',
    })

    # Generate individual airfield PDFs
    airfield_pdf_dir = os.path.join(PUBLIC_DIR, 'airfield-pdfs')
    print("\nGenerating individual airfield PDFs...")
    pdf_mapping = generate_airfield_pdfs(airfields, airfield_pdf_dir, meta=meta)

    # Generate HTML with embedded diagrams
    output_html = os.path.join(PUBLIC_DIR, 'index.html')
    print("\nGenerating HTML with embedded diagrams...")
    generate_html(
        airfields,
        output_html,
        meta=meta,
        embed_diagrams=True,
        download_links=download_links,
        freq_tables=freq_tables,
        pdf_mapping=pdf_mapping,
    )

    file_size = os.path.getsize(output_html) / 1024 / 1024
    print(f"  index.html: {file_size:.1f} MB")

    # Generate markdown from JSON
    print("\nGenerating markdown from JSON...")
    md_output = generate_markdown(airfields, meta)
    md_path = os.path.join(PUBLIC_DIR, 'AIRFIELD_DIRECTORY.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_output)
    print(f"  Markdown: {os.path.getsize(md_path) / 1024:.0f} KB")

    # Summary
    print(f"\nBuild complete! Output: {PUBLIC_DIR}/")
    for f in sorted(os.listdir(PUBLIC_DIR)):
        full = os.path.join(PUBLIC_DIR, f)
        if os.path.isdir(full):
            count = len(os.listdir(full))
            total = sum(os.path.getsize(os.path.join(full, x)) for x in os.listdir(full))
            print(f"  {f}/ ({count} files, {total / 1024:.0f} KB)")
        else:
            print(f"  {f} ({os.path.getsize(full) / 1024:.0f} KB)")


if __name__ == '__main__':
    build()
