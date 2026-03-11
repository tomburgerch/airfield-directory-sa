"""Tests for the build script and Vercel deployment readiness."""

import json
import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(BASE_DIR, 'public')


class TestBuildScript:
    """Test that build.py produces a valid deployable site."""

    @pytest.fixture(autouse=True, scope='class')
    def run_build(self):
        """Run the build once for all tests in this class."""
        from build import build
        build()
        yield
        # Don't clean up — other tests may want to inspect

    def test_public_dir_created(self):
        assert os.path.isdir(PUBLIC_DIR)

    def test_index_html_exists(self):
        assert os.path.isfile(os.path.join(PUBLIC_DIR, 'index.html'))

    def test_index_html_is_valid(self):
        with open(os.path.join(PUBLIC_DIR, 'index.html'), 'r') as f:
            html = f.read()
        assert html.startswith('<!DOCTYPE html>')
        assert '</html>' in html

    def test_index_has_embedded_diagrams(self):
        with open(os.path.join(PUBLIC_DIR, 'index.html'), 'r') as f:
            html = f.read()
        assert 'data:image/png;base64,' in html
        # Should not reference external diagram files
        assert 'src="diagrams/' not in html

    def test_index_has_download_bar(self):
        with open(os.path.join(PUBLIC_DIR, 'index.html'), 'r') as f:
            html = f.read()
        assert 'header-actions' in html
        assert 'PDF' in html
        assert 'Download Markdown' in html

    def test_pdf_generated(self):
        pdf_path = os.path.join(PUBLIC_DIR, 'Airfield_Directory.pdf')
        assert os.path.isfile(pdf_path)
        assert os.path.getsize(pdf_path) > 50_000  # Should be > 50KB

    def test_markdown_copied(self):
        md_path = os.path.join(PUBLIC_DIR, 'AIRFIELD_DIRECTORY.md')
        assert os.path.isfile(md_path)
        assert os.path.getsize(md_path) > 10_000  # Should be > 10KB

    def test_all_airfields_in_output(self):
        from parse_markdown import parse_airfields
        md_file = os.path.join(BASE_DIR, 'AIRFIELD_DIRECTORY.md')
        airfields = parse_airfields(md_file)
        with open(os.path.join(PUBLIC_DIR, 'index.html'), 'r') as f:
            html = f.read()
        for af in airfields:
            assert f'id="af-{af["number"]}"' in html, f"Airfield #{af['number']} missing from output"


class TestVercelConfig:
    def test_vercel_json_exists(self):
        path = os.path.join(BASE_DIR, 'vercel.json')
        assert os.path.isfile(path)

    def test_vercel_json_valid(self):
        with open(os.path.join(BASE_DIR, 'vercel.json'), 'r') as f:
            config = json.load(f)
        assert 'outputDirectory' in config
        assert config['outputDirectory'] == 'public'
        assert 'buildCommand' in config

    def test_package_json_exists(self):
        path = os.path.join(BASE_DIR, 'package.json')
        assert os.path.isfile(path)

    def test_package_json_valid(self):
        with open(os.path.join(BASE_DIR, 'package.json'), 'r') as f:
            config = json.load(f)
        assert 'name' in config
