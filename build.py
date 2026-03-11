#!/usr/bin/env python3
"""
Build script for Vercel deployment.

Generates a self-contained static site in public/ with:
  - index.html: Searchable airfield directory with base64-embedded diagrams
  - Airfield_Directory_A5.pdf: Printable PDF for download
  - AIRFIELD_DIRECTORY.md: Markdown source for download
"""

import os
import shutil

from parse_markdown import parse_airfields
from generate_html import generate_html
from generate_pdf import generate_pdf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, 'public')
MD_FILE = os.path.join(BASE_DIR, 'AIRFIELD_DIRECTORY.md')


def build():
    """Build the static site into public/."""
    print("=" * 50)
    print("Building SA Airfield Directory for deployment")
    print("=" * 50)

    # Clean and create output directory
    if os.path.exists(PUBLIC_DIR):
        shutil.rmtree(PUBLIC_DIR)
    os.makedirs(PUBLIC_DIR)

    # Copy downloadable files
    download_links = []

    if os.path.exists(MD_FILE):
        shutil.copy2(MD_FILE, os.path.join(PUBLIC_DIR, 'AIRFIELD_DIRECTORY.md'))
        download_links.append({
            'label': 'Download Markdown',
            'href': 'AIRFIELD_DIRECTORY.md',
        })
        print(f"  Copied Markdown ({os.path.getsize(MD_FILE) / 1024:.0f} KB)")

    # Parse airfield data
    print("\nParsing airfield data...")
    airfields = parse_airfields(MD_FILE)
    print(f"  Found {len(airfields)} airfields")

    # Generate compact PDF
    pdf_path = os.path.join(PUBLIC_DIR, 'Airfield_Directory.pdf')
    print("\nGenerating compact PDF...")
    generate_pdf(airfields, pdf_path)
    pdf_size = os.path.getsize(pdf_path) / 1024
    print(f"  PDF: {pdf_size:.0f} KB")
    download_links.insert(0, {
        'label': 'Download PDF (Offline)',
        'href': 'Airfield_Directory.pdf',
    })

    # Generate HTML with embedded diagrams
    output_html = os.path.join(PUBLIC_DIR, 'index.html')
    print("\nGenerating HTML with embedded diagrams...")
    generate_html(
        airfields,
        output_html,
        embed_diagrams=True,
        download_links=download_links,
    )

    file_size = os.path.getsize(output_html) / 1024 / 1024
    print(f"  index.html: {file_size:.1f} MB")

    # Summary
    print(f"\nBuild complete! Output: {PUBLIC_DIR}/")
    files = os.listdir(PUBLIC_DIR)
    for f in sorted(files):
        size = os.path.getsize(os.path.join(PUBLIC_DIR, f))
        print(f"  {f} ({size / 1024:.0f} KB)")


if __name__ == '__main__':
    build()
