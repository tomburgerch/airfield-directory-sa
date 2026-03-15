#!/usr/bin/env python3
"""
Aerodrome diagram lookup and management utilities.
"""

import os
import re

from shared import DIAGRAMS_DIR, get_icao


def find_diagram(airfield):
    """Find a diagram file for this airfield. Returns path or None."""
    icao = get_icao(airfield)

    candidates = []

    # Extract all FA-prefix ICAO codes
    all_codes = []
    if icao:
        fa_codes = re.findall(r'\b(FA[A-Z]{2,4})\b', icao.upper())
        all_codes.extend(fa_codes)
        first_word = re.sub(r'[^A-Z0-9-]', '', icao.upper().split()[0])
        if first_word and len(first_word) >= 4:
            all_codes.append(first_word)

    # Try extracting ICAO from the name
    name_codes = re.findall(r'\b(FA[A-Z]{2,4})\b', airfield['name'].upper())
    all_codes.extend(name_codes)

    # Build candidate filenames
    for code in all_codes:
        candidates.extend([
            f'{code}.png', f'{code}.jpg',
            f'{code}_AD01.png', f'{code}_AD02.png',
            f'{code}_chart.png',
        ])

    # Try by name slug
    name_slug = re.sub(r'[^a-z0-9]', '_', airfield['name'].lower().split('(')[0].strip())
    candidates.extend([f'{name_slug}.png', f'{name_slug}.jpg'])

    for c in candidates:
        path = os.path.join(DIAGRAMS_DIR, c)
        if os.path.exists(path):
            return path

    return None


def download_sacaa_diagrams():
    """Download aerodrome diagrams from SACAA AIP PDFs."""
    import requests

    icao_codes = [
        'FASH', 'FACT', 'FASD', 'FALW', 'FAVR', 'FACI', 'FACW',
        'FAWC', 'FADS', 'FACE', 'FARS', 'FAAS', 'FACG', 'FAOB',
        'FASX', 'FAGG', 'FAMO', 'FAOH', 'FARD', 'FACY', 'FAPG',
        'FABW', 'FAPC', 'FAKA', 'FAAF',
    ]

    base_url = 'https://caasanwebsitestorage.blob.core.windows.net/aerodrone-and-helicompter-directory/'
    os.makedirs(DIAGRAMS_DIR, exist_ok=True)

    downloaded = 0
    for code in icao_codes:
        pdf_path = os.path.join(DIAGRAMS_DIR, f'{code}.pdf')
        if os.path.exists(pdf_path):
            continue

        url = f'{base_url}{code}AD2.pdf'
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(pdf_path, 'wb') as fobj:
                    fobj.write(resp.content)
                downloaded += 1
                print(f"  Downloaded: {code}AD2.pdf ({len(resp.content)} bytes)")
        except Exception:
            pass

    print(f"Downloaded {downloaded} SACAA AIP PDFs")


def extract_diagram_images():
    """Extract aerodrome diagram pages from SACAA PDFs as high-res images.

    Uses pymupdf (fitz) at ~288 DPI for sharp, readable diagrams.
    Falls back to pdftoppm if pymupdf is not available.
    """
    try:
        import fitz
        has_fitz = True
    except ImportError:
        has_fitz = False

    if has_fitz:
        extracted = 0
        for pdf_file in os.listdir(DIAGRAMS_DIR):
            if not pdf_file.endswith('.pdf'):
                continue
            icao = pdf_file.replace('.pdf', '')
            png_path = os.path.join(DIAGRAMS_DIR, f'{icao}.png')
            if os.path.exists(png_path):
                continue
            pdf_path = os.path.join(DIAGRAMS_DIR, pdf_file)
            try:
                doc = fitz.open(pdf_path)
                page = doc[-1]  # Last page (usually the diagram)
                mat = fitz.Matrix(4.0, 4.0)  # ~288 DPI
                pix = page.get_pixmap(matrix=mat)
                pix.save(png_path)
                doc.close()
                extracted += 1
                print(f"  Extracted diagram: {icao}.png ({pix.width}x{pix.height})")
            except Exception:
                pass
        if extracted:
            print(f"  Extracted {extracted} new diagram(s) via pymupdf")
        return

    # Fallback: pdftoppm
    try:
        import subprocess
        result = subprocess.run(['which', 'pdftoppm'], capture_output=True)
        has_pdftoppm = result.returncode == 0
    except Exception:
        has_pdftoppm = False

    if not has_pdftoppm:
        print("No PDF renderer available — skipping diagram extraction")
        return

    import subprocess
    for pdf_file in os.listdir(DIAGRAMS_DIR):
        if not pdf_file.endswith('.pdf'):
            continue
        icao = pdf_file.replace('.pdf', '')
        png_path = os.path.join(DIAGRAMS_DIR, f'{icao}.png')
        if os.path.exists(png_path):
            continue

        pdf_path = os.path.join(DIAGRAMS_DIR, pdf_file)
        try:
            result = subprocess.run(
                ['pdfinfo', pdf_path],
                capture_output=True, text=True, timeout=10
            )
            pages = 1
            for line in result.stdout.split('\n'):
                if line.startswith('Pages:'):
                    pages = int(line.split(':')[1].strip())

            subprocess.run([
                'pdftoppm', '-png', '-r', '300',
                '-f', str(pages), '-l', str(pages),
                '-singlefile',
                pdf_path,
                os.path.join(DIAGRAMS_DIR, icao)
            ], timeout=30, capture_output=True)

            if os.path.exists(png_path):
                print(f"  Extracted diagram: {icao}.png")
        except Exception:
            pass
