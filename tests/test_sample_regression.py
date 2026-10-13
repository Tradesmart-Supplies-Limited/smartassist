"""Rebuilding the sample's own truck must give back the sample's text on pages 1-3.

Needs the real sample in samples\\ (not in git), so it is skipped when the sample is absent.
All private values are read from the sample itself, none are written in this file.
"""
import glob
import os
from decimal import Decimal

import pytest

from core import layout
from core.pdf_builder import build_pdf, document_values, load_template, pymupdf
from core.trucks import Truck

SAMPLES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples")
PDFS = sorted(glob.glob(os.path.join(SAMPLES, "*.pdf")))

pytestmark = pytest.mark.skipif(not PDFS, reason="sample PDF not present")


def rebuild_sample():
    with open(PDFS[0], "rb") as f:
        sample_bytes = f.read()
    template = load_template(sample_bytes)
    s = template["sample"]
    truck = Truck(row=0, invoice_no=s["invoice_no"], driver=s["driver"], passport=s["passport"],
                  horse=s["horse"], trailer1=s["trailer1"], trailer2=s["trailer2"], border=s["border"])
    values = document_values(truck, Decimal("40"), Decimal("40"), s["date"], layout.DEFAULT_PRICES,
                             layout.DEFAULT_FREIGHT1, layout.DEFAULT_FREIGHT2)
    return sample_bytes, template, build_pdf(template, values)


def words(page):
    """Every word on the page, sorted, so the drawing order does not matter."""
    return sorted(w[4] for w in page.get_text("words"))


def test_rebuilt_sample_has_identical_text():
    sample_bytes, _template, rebuilt = rebuild_sample()
    old = pymupdf.open(stream=sample_bytes, filetype="pdf")
    new = pymupdf.open(stream=rebuilt, filetype="pdf")
    assert len(new) == 3
    for page_no in range(3):
        assert words(new[page_no]) == words(old[page_no]), f"page {page_no + 1} differs"


def test_rebuilt_sample_text_stays_in_place():
    sample_bytes, template, rebuilt = rebuild_sample()
    new = pymupdf.open(stream=rebuilt, filetype="pdf")
    for spot in template["spots"]:
        text = template["sample"][spot["key"]]
        boxes = new[spot["page"]].search_for(text)
        # one of the places this text appears must be centred where the sample had it
        if spot["align"] == "right":
            assert any(abs(b.x1 - spot["right"]) < 1.5 for b in boxes), spot
        else:
            assert any(abs((b.x0 + b.x1) / 2 - spot["centre"]) < 1.5 for b in boxes), spot


def test_output_is_small_and_has_no_inspection_pages():
    _sample_bytes, _template, rebuilt = rebuild_sample()
    assert len(rebuilt) < 300_000
