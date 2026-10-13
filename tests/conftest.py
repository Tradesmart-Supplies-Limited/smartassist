"""Shared test helpers. Everything here is invented data, no client data."""
import glob
import os
import sys

import pytest

PROJECT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT)     # lets the tests import the `core` package

from core import layout                                   # noqa: E402
from core.pdf_builder import load_template, pymupdf       # noqa: E402

SAMPLE_PDFS = sorted(glob.glob(os.path.join(PROJECT, "samples", "*.pdf")))

# Invented values for the private fields of the pretend sample.
PRETEND = {"driver": "TEST DRIVER", "passport": "XX000000", "horse": "AAA111ZM",
           "trailer1": "BBB222ZM", "trailer2": "NIL"}


def make_pretend_sample():
    """A 3-page PDF with the sample's texts at the sample's spots, plus one junk page 4."""
    doc = pymupdf.open()
    for _ in range(4):
        doc.new_page(width=842, height=595)
    # Measure how far below the top of its box a text's baseline sits.
    probe = doc[3]
    probe.insert_text((50, 50), "Inspection photo", fontsize=10)
    rise = (50 - probe.get_text("dict")["blocks"][0]["lines"][0]["spans"][0]["bbox"][1]) / 10

    for page_no, x, y, key, _align in layout.SPOTS:
        page = doc[page_no]
        text = layout.SAMPLE_VALUES.get(key) or PRETEND[key]
        page.insert_text((x, y + rise * 10), text, fontsize=10, color=(1, 0, 0))
        # Table lines 15 points left and right of the text, to make a cell.
        width = pymupdf.get_text_length(text, fontsize=10)
        for line_x in (x - 15, x + width + 15):
            page.draw_line((line_x, y - 5), (line_x, y + 17))
    return doc.tobytes()


@pytest.fixture(scope="session", params=["pretend", "sample"])
def template(request):
    """The template made from the pretend sample, and from the real one when it is present."""
    if request.param == "pretend":
        return load_template(make_pretend_sample())
    if not SAMPLE_PDFS:
        pytest.skip("sample PDF not present")
    with open(SAMPLE_PDFS[0], "rb") as f:
        return load_template(f.read())
