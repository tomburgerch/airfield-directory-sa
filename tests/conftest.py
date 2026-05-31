"""Shared pytest fixtures.

The diagram PNGs in ``diagrams/`` are derived artifacts: the committed
``*.pdf`` SACAA charts are the source of truth, and ``extract_diagram_images``
renders them to PNG (via pymupdf, a declared dependency). The PNGs are
gitignored, so a fresh checkout (including the release-tag CI job that runs
pytest) has only the PDFs. Generate the PNGs once per session before any test
so ``find_diagram`` and the HTML build have something to resolve.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diagrams_util import extract_diagram_images


@pytest.fixture(scope="session", autouse=True)
def ensure_diagram_images():
    """Render the committed PDF charts to PNG before the suite runs."""
    extract_diagram_images()
    yield
