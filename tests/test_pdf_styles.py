"""Tests for PDF styles module."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdf_styles import get_styles, clean_text


def test_get_styles_returns_stylesheet():
    """get_styles() should return a stylesheet with custom styles."""
    styles = get_styles()
    assert styles is not None
    assert styles['FieldName'] is not None
    assert styles['Warning'] is not None
    assert styles['TOCEntry'] is not None


def test_clean_text_removes_emoji():
    """clean_text should replace emoji with text markers."""
    assert '[L]' in clean_text('⬅️ Left')
    assert '[FUEL]' in clean_text('⛽ Available')
    assert '(?)' in clean_text('❓ Unverified')


def test_clean_text_preserves_plain():
    """clean_text should not alter plain text."""
    assert clean_text('Hello World') == 'Hello World'
    assert clean_text('119.3 MHz') == '119.3 MHz'
