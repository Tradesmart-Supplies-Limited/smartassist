"""Shared test helpers. Everything here is invented data, no client data."""
import glob
import os
import sys

import pytest

PROJECT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT)     # lets the tests import the `core` package

from core.clients import bms as layout                   # noqa: E402  (the BMS client profile)
from core.pdf_builder import load_template, pymupdf       # noqa: E402

SAMPLE_PDFS = sorted(glob.glob(os.path.join(PROJECT, "samples", "*.pdf")))

# Invented values for the private fields of the pretend sample.
PRETEND = {"driver": "TEST DRIVER", "passport": "XX000000", "horse": "AAA111ZM",
           "trailer1": "BBB222ZM", "trailer2": "NIL"}


def make_pretend_sample(changes=None):
    """A 3-page PDF with the sample's texts at the sample's spots, plus one junk page 4.
    `changes` replaces some texts, e.g. {"driver": "ANOTHER NAME"}, to pretend another truck."""
    doc = pymupdf.open()
    for _ in range(4):
        doc.new_page(width=842, height=595)
    # Measure how far the middle of a text's box sits above its baseline.
    probe = doc[3]
    probe.insert_text((50, 50), "Inspection photo", fontsize=10)
    box = probe.get_text("dict")["blocks"][0]["lines"][0]["spans"][0]["bbox"]
    lift = 50 - (box[1] + box[3]) / 2
    for page_no, title in enumerate(layout.TITLES):
        doc[page_no].insert_text((300, 40), title, fontsize=14)

    for page_no, x, y, key, align in layout.SPOTS:
        page = doc[page_no]
        text = (changes or {}).get(key) or layout.SAMPLE_VALUES.get(key) or PRETEND[key]
        # x is the middle of the text (or its end for "right"), y the middle of its height.
        width = pymupdf.get_text_length(text, fontsize=10)
        left = x - width if align == "right" else x - width / 2
        page.insert_text((left, y + lift), text, fontsize=10, color=(1, 0, 0))
        # Table lines 15 points left and right of the text, to make a cell.
        for line_x in (left - 15, left + width + 15):
            page.draw_line((line_x, y - 11), (line_x, y + 11))
    return doc.tobytes()


@pytest.fixture(scope="session", params=["pretend", "sample"])
def template(request):
    """The template made from the pretend sample, and from the real one when it is present."""
    if request.param == "pretend":
        return load_template(make_pretend_sample(), layout)
    if not SAMPLE_PDFS:
        pytest.skip("sample PDF not present")
    with open(SAMPLE_PDFS[0], "rb") as f:
        return load_template(f.read(), layout)
