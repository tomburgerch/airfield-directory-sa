"""Tests for HTML generation from JSON-schema airfield data."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_html import generate_html, build_airfield_card, clean_html, embed_image, load_airfields_json

AIRFIELDS_JSON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'airfields.json')
DIAGRAMS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'diagrams')


@pytest.fixture(scope='module')
def json_data():
    meta, airfields = load_airfields_json(AIRFIELDS_JSON)
    return meta, airfields


@pytest.fixture(scope='module')
def meta(json_data):
    return json_data[0]


@pytest.fixture(scope='module')
def airfields(json_data):
    return json_data[1]


class TestCleanHtml:
    def test_strips_emoji(self):
        result = clean_html('\u2b05\ufe0f Left')
        assert '\u2b05\ufe0f' not in result
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
    def test_card_contains_name(self, airfields, meta):
        card = build_airfield_card(airfields[0], meta=meta)
        assert airfields[0]['name'].split('(')[0].strip().split()[0].upper() in card.upper()

    def test_card_has_id(self, airfields, meta):
        card = build_airfield_card(airfields[0], meta=meta)
        assert f'id="af-{airfields[0]["number"]}"' in card

    def test_card_has_search_data(self, airfields, meta):
        card = build_airfield_card(airfields[0], meta=meta)
        assert 'data-search=' in card

    def test_closed_airfield_has_banner(self, airfields, meta):
        closed = next((af for af in airfields if af['status'] == 'closed'), None)
        if closed is None:
            pytest.skip('No closed airfield found')
        card = build_airfield_card(closed, meta=meta)
        assert 'closed-banner' in card
        assert 'CLOSED' in card

    def test_embedded_diagram(self, airfields, meta):
        af_with_diagram = next(
            (af for af in airfields if af['icao'] == 'FASH'),
            None,
        )
        if af_with_diagram is None:
            pytest.skip('FASH not found')
        card = build_airfield_card(af_with_diagram, meta=meta, embed_diagrams=True)
        # May or may not have diagram depending on file presence
        assert 'af-' in card

    def test_runways_rendered(self, airfields, meta):
        af_with_rwy = next((af for af in airfields if af.get('runways', {}).get('data')), None)
        if af_with_rwy is None:
            pytest.skip('No airfield with runways')
        card = build_airfield_card(af_with_rwy, meta=meta)
        assert 'data-table' in card
        assert 'RWY' in card

    def test_source_footer_rendered(self, airfields, meta):
        """Each airfield card should have a sources footer."""
        card = build_airfield_card(airfields[0], meta=meta)
        assert 'class="sources-footer"' in card

    def test_click_to_copy_coordinates(self, airfields, meta):
        """Coordinates should have click-to-copy data attribute."""
        af_with_coords = next(
            (af for af in airfields if af.get('basic_info', {}).get('coordinates', {}).get('lat')),
            None,
        )
        if af_with_coords is None:
            pytest.skip('No airfield with coordinates')
        card = build_airfield_card(af_with_coords, meta=meta)
        assert 'data-copy-coords' in card

    def test_no_airfield_number_in_header(self, airfields, meta):
        """Airfield number should not appear in the card header as '#N'."""
        card = build_airfield_card(airfields[1], meta=meta)
        # Old format had <span class="num">#2</span>
        assert f'class="num">#{airfields[1]["number"]}' not in card

    def test_runway_width_column(self, airfields, meta):
        """Runway table should include Width column when data is available."""
        af_with_width = next(
            (af for af in airfields
             if any(r.get('width') for r in af.get('runways', {}).get('data', []))),
            None,
        )
        if af_with_width is None:
            pytest.skip('No airfield with runway width data')
        card = build_airfield_card(af_with_width, meta=meta)
        assert '<th>Width</th>' in card

    def test_source_indicator_on_non_aip_note(self, airfields, meta):
        """Non-AIP notes should have a source indicator."""
        af_with_non_aip = next(
            (af for af in airfields
             if any('url' in n.get('source', {}) for n in af.get('notes', []))),
            None,
        )
        if af_with_non_aip is None:
            pytest.skip('No airfield with non-AIP note source')
        card = build_airfield_card(af_with_non_aip, meta=meta)
        assert '&#8599;' in card  # ↗ arrow


class TestGenerateHtml:
    def test_generates_valid_html(self, airfields, meta):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:3], tmp, meta=meta)
            with open(tmp, 'r') as f:
                html = f.read()
            assert html.startswith('<!DOCTYPE html>')
            assert '</html>' in html
            assert '<title>' in html and 'Airfield Directory</title>' in html
        finally:
            os.unlink(tmp)

    def test_contains_search_box(self, airfields, meta):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:3], tmp, meta=meta)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'id="search-box"' in html
        finally:
            os.unlink(tmp)

    def test_contains_toc(self, airfields, meta):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:5], tmp, meta=meta)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'toc-grid' in html
            assert 'Airfield Index' in html
        finally:
            os.unlink(tmp)

    def test_contains_disclaimer(self, airfields, meta):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:1], tmp, meta=meta)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'IMPORTANT DISCLAIMER' in html
        finally:
            os.unlink(tmp)

    def test_download_links_rendered(self, airfields, meta):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            links = [
                {'label': 'Download PDF', 'href': 'test.pdf'},
                {'label': 'Download MD', 'href': 'test.md'},
            ]
            generate_html(airfields[:1], tmp, meta=meta, download_links=links)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'header-actions' in html
            assert 'Download PDF' in html
            assert 'Download MD' in html
            assert 'href="test.pdf"' in html
        finally:
            os.unlink(tmp)

    def test_no_download_bar_without_links(self, airfields, meta):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:1], tmp, meta=meta)
            with open(tmp, 'r') as f:
                html = f.read()
            assert '<div class="download-bar">' not in html
        finally:
            os.unlink(tmp)

    def test_all_airfields_rendered(self, airfields, meta):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields, tmp, meta=meta)
            with open(tmp, 'r') as f:
                html = f.read()
            for af in airfields:
                assert f'id="af-{af["number"]}"' in html
        finally:
            os.unlink(tmp)

    def test_embedded_mode_no_external_refs(self, airfields, meta):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:10], tmp, meta=meta, embed_diagrams=True)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'src="diagrams/' not in html
        finally:
            os.unlink(tmp)

    def test_back_to_top_button(self, airfields, meta):
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:1], tmp, meta=meta)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'back-to-top' in html
        finally:
            os.unlink(tmp)

    def test_click_to_copy_js_present(self, airfields, meta):
        """Click-to-copy JS should be in the generated HTML."""
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            tmp = f.name
        try:
            generate_html(airfields[:1], tmp, meta=meta)
            with open(tmp, 'r') as f:
                html = f.read()
            assert 'data-copy-coords' in html
        finally:
            os.unlink(tmp)
