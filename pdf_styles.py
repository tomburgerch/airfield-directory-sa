#!/usr/bin/env python3
"""
PDF styles and constants for the Airfield Directory A5 generator.
"""

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ── Page dimensions ──
A5_WIDTH, A5_HEIGHT = A5
MARGIN = 8 * mm
CONTENT_WIDTH = A5_WIDTH - 2 * MARGIN
CONTENT_HEIGHT = A5_HEIGHT - 2 * MARGIN

# ── Color palette ──
COLOR_HEADER_BG = HexColor('#1a365d')   # Dark navy
COLOR_HEADER_FG = white
COLOR_ACCENT = HexColor('#2b6cb0')      # Blue accent
COLOR_WARNING = HexColor('#c53030')     # Red for warnings
COLOR_CLOSED = HexColor('#9b2c2c')      # Dark red for closed
COLOR_MILITARY = HexColor('#2d3748')    # Dark gray for military
COLOR_ROW_ALT = HexColor('#f7fafc')     # Light gray alternating rows
COLOR_BORDER = HexColor('#e2e8f0')      # Light border

# ── Emoji replacements for PDF rendering ──
# Tags [L]/[R] kept for circuit direction; [!]/[X] kept for warnings.
# Status emojis stripped — field labels already provide context.
EMOJI_MAP = {
    '⬅️': '[L]', '➡️': '[R]',
    '🌙': '', '🚫': '', '🔒': '', '✈️': '', '🪖': '', '⛽': '',
    '❓': '(?)', '📅': '', '⚠️': '[!]', '⛔': '[X]',
    '🏠': '', '🛩️': '', '🔴': '', '🟢': '', '🟡': '',
}


def clean_text(text):
    """Remove or replace emoji that can't render in standard PDF fonts."""
    for emoji, replacement in EMOJI_MAP.items():
        text = text.replace(emoji, replacement)
    return text


def get_styles():
    """Create and return all PDF paragraph styles."""
    styles = getSampleStyleSheet()

    style_defs = [
        ('FieldName', {'fontSize': 11, 'leading': 13, 'textColor': white,
                       'fontName': 'Helvetica-Bold', 'alignment': TA_LEFT}),
        ('FieldCode', {'fontSize': 8, 'leading': 10, 'textColor': HexColor('#bee3f8'),
                       'fontName': 'Helvetica', 'alignment': TA_LEFT}),
        ('SectionTitle', {'fontSize': 7.5, 'leading': 9, 'textColor': COLOR_ACCENT,
                          'fontName': 'Helvetica-Bold', 'spaceBefore': 3, 'spaceAfter': 1}),
        ('FieldValue', {'fontSize': 6.5, 'leading': 8, 'fontName': 'Helvetica'}),
        ('FieldLabel', {'fontSize': 6.5, 'leading': 8, 'textColor': HexColor('#4a5568'),
                        'fontName': 'Helvetica-Bold'}),
        ('SmallNote', {'fontSize': 6, 'leading': 7.5, 'textColor': HexColor('#4a5568'),
                       'fontName': 'Helvetica'}),
        ('FreqValue', {'fontSize': 7.5, 'leading': 9, 'textColor': COLOR_ACCENT,
                       'fontName': 'Helvetica-Bold'}),
        ('Warning', {'fontSize': 6.5, 'leading': 8, 'textColor': COLOR_WARNING,
                     'fontName': 'Helvetica-Bold'}),
        ('StatusClosed', {'fontSize': 8, 'leading': 10, 'textColor': white,
                          'fontName': 'Helvetica-Bold', 'alignment': TA_CENTER}),
        ('GroupTitle', {'fontSize': 9, 'leading': 11, 'textColor': COLOR_HEADER_BG,
                        'fontName': 'Helvetica-Bold', 'alignment': TA_CENTER,
                        'spaceBefore': 6, 'spaceAfter': 3}),
        ('PageNum', {'fontSize': 6, 'leading': 7, 'textColor': HexColor('#a0aec0'),
                     'fontName': 'Helvetica', 'alignment': TA_CENTER}),
        ('RunwayHeader', {'fontSize': 6, 'leading': 7, 'textColor': white,
                          'fontName': 'Helvetica-Bold', 'alignment': TA_CENTER}),
        ('RunwayCell', {'fontSize': 6, 'leading': 7, 'fontName': 'Helvetica',
                        'alignment': TA_CENTER}),
        ('TOCTitle', {'fontSize': 11, 'leading': 14, 'textColor': COLOR_HEADER_BG,
                      'fontName': 'Helvetica-Bold', 'alignment': TA_CENTER,
                      'spaceBefore': 2, 'spaceAfter': 4}),
        ('TOCGroupHeader', {'fontSize': 7, 'leading': 9, 'textColor': COLOR_ACCENT,
                            'fontName': 'Helvetica-Bold', 'spaceBefore': 3, 'spaceAfter': 1}),
        ('TOCEntry', {'fontSize': 6.5, 'leading': 8.5, 'fontName': 'Helvetica'}),
        ('TOCEntryCode', {'fontSize': 5.5, 'leading': 8.5, 'textColor': HexColor('#718096'),
                          'fontName': 'Helvetica'}),
        ('TOCPageNum', {'fontSize': 6.5, 'leading': 8.5, 'textColor': COLOR_ACCENT,
                        'fontName': 'Helvetica-Bold', 'alignment': TA_RIGHT}),
    ]

    for name, kwargs in style_defs:
        styles.add(ParagraphStyle(name, parent=styles['Normal'], **kwargs))

    return styles
