"""Tests for HTML generation."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parse_markdown import parse_airfields
from generate_html import generate_html, build_airfield_card, clean_html, embed_image

MD_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'AIRFIELD_DIRECTORY.md')
DIAGRAMS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'diagrams')


@pytest.fixture(scope='module')
def airfields():
    return parse_airfields(MD_FILE)


class TestCleanHtml:
    def test_strips_emoji(self):
        result = clean_html('⬅️ Left')
        assert '⬅️' not in result
        assert 'Left' in result

    def test_preserves_plain_text(self):
        assert clean_html('Hello World') == 'Hello World'

    def test_strips_whitespace(self):
        assert clean_html('  spaced  ') == 'spaced'


class TestEmbedImage:
    def test_returns_empty_for_missing_file(self):
        assert embed_image('/nonexistent/file.png') == ''

    def test_returns_empty_for_none(self):
        assert embed_image(None) == ''

    def test_embeds_real_diagram(self):
        png_files = [f for f in os.listdir(DIAGRAMS_DIR) if f.endswith('.png')]
        if not png_files:
            pytest.skip('No diagram PNGs available')
        path = os.path.join(DIAGRAMS_DIR, png_files[0])
        result = embed_image(path)
        assert 'data:image/png;base64,' in result
        assert '<img' in result
        assert 'alt="Aerodrome diagram"' in result

    def test_respects_max_width(self):
        png_files = [f for f in os.listdir(DIAGRAMS_DIR) if f.endswith('.png')]
        if not png_files:
            pytest.skip('No diagram PNGs available')
        path = os.path.join(DIAGRAMS_DIR, png_files[0])
        result = embed_image(path, max_width=300)
        assert 'max-width:300px' in result


class TestBuildAirfieldCard:
    def test_card_contains_name(self, airfields):
        card = build_airfield_card(airfields[0])
        assert 'MORNINGSTAR' in card.upper()

    def test_card_has_id(self, airfields):
        card = build_airfield_card(airfields[0])
        assert 'id="af-1"' in card

    def test_card_has_search_data(self, airfields):
        card = build_airfield_card(airfields[0])
        assert 'data-search=' in card

    def test_closed_airfield_has_banner(self, airfields):
        closed = next((af for af in airfields if '[X]' in af['name'] or 'CLOSED' in af['name'].upper()), None)
        if closed is None:
            pytest.skip('No closed airfield found')
        card = build_airfield_card(closed)
        assert 'closed-banner' in card
        assert 'CLOSED' in card

    def test_embedded_diagram(self, airfields):
        af_with_diagram = next(
            (af for af in airfields if 'FASH' in af['fields'].get('ICAO', '')),
            None,
        )
        if af_with_diagram is None:
            pytest.skip('FASH not found')
        card = build_airfield_card(af_with_diagram, embed_diagrams=True)
        assert 'data:image/png;base64,' in card
        assert 'diagram-caption' in card

    def test_external_diagram(self, airfields):
        af_with_diagram = next(
            (af for af in airfields if 'FASH' in af['fields'].get('ICAO', '')),
            None,
        )
        if af_with_diagram is None:
            pytest.skip('FASH not found')
        card = build_airfield_card(af_with_diagram, embed_diagrams=False)
        assert 'src="diagrams/' in card
        assert 'data:image/png;base64,' not in card

    def test_runways_rendered(self, airfields):
        af_with_rwy = next((af for af in airfields if af['runways']), None)
        if af_with_rwy is None:
            pytest.skip('No airfield with runways')
        card = build_airfield_card(af_with_rwy)
        assert 'data-table' in card
        assert 'RWY' in card


class TestGenerateHtml:
    def test_generates_valid_html(self, airfields):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:3], tmp)
            with open(tmp, 'r') as f:
                html = f.read()
            assert html.startswith('<!DOCTYPE html>')
            assert '</html>' in html
            assert '<title>' in html and 'Airfield Directory</title>' in html
        finally:
            os.unlink(tmp)

    def test_contains_search_box(self, airfields):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:3], tmp)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'id="search-box"' in html
        finally:
            os.unlink(tmp)

    def test_contains_toc(self, airfields):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:5], tmp)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'toc-grid' in html
            assert 'Airfield Index' in html
        finally:
            os.unlink(tmp)

    def test_contains_disclaimer(self, airfields):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:1], tmp)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'IMPORTANT DISCLAIMER' in html
        finally:
            os.unlink(tmp)

    def test_download_links_rendered(self, airfields):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            links = [
                {'label': 'Download PDF', 'href': 'test.pdf'},
                {'label': 'Download MD', 'href': 'test.md'},
            ]
            generate_html(airfields[:1], tmp, download_links=links)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'header-actions' in html
            assert 'Download PDF' in html
            assert 'Download MD' in html
            assert 'href="test.pdf"' in html
        finally:
            os.unlink(tmp)

    def test_no_download_bar_without_links(self, airfields):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:1], tmp)
            with open(tmp, 'r') as f:
                html = f.read()
            assert '<div class="download-bar">' not in html
        finally:
            os.unlink(tmp)

    def test_all_airfields_rendered(self, airfields):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields, tmp)
            with open(tmp, 'r') as f:
                html = f.read()
            for af in airfields:
                assert f'id="af-{af["number"]}"' in html
        finally:
            os.unlink(tmp)

    def test_embedded_mode_no_external_refs(self, airfields):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:10], tmp, embed_diagrams=True)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'src="diagrams/' not in html
        finally:
            os.unlink(tmp)

    def test_back_to_top_button(self, airfields):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:1], tmp)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'back-to-top' in html
        finally:
            os.unlink(tmp)
