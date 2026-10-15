"""Client profiles, recognition from file content, and wrong pairings (invented data only)."""
import glob
import json
import os
from datetime import date

import pandas as pd
import pytest

from conftest import make_pretend_sample
from core import instructions as ins
from core.clients import bms, detect_client_from_excel, detect_client_from_pdf, gck, get_client, list_clients
from core.clients import pairing_problem
from core.pdf_builder import LayoutError, load_template, pymupdf

HERE = os.path.dirname(__file__)
SAMPLE_PDFS = sorted(glob.glob(os.path.join(HERE, "..", "samples", "*.pdf")))
SAMPLE_EXCELS = sorted(glob.glob(os.path.join(HERE, "..", "samples", "*.xlsx")))
GCK_FILES = sorted(glob.glob(os.path.join(HERE, "..", "samples", "GCK", "*")))


def bms_like_sheet():
    """An invented sheet shaped like the BMS loading order."""
    return pd.DataFrame([[None, None, "DESTINATION: BMS"] + [None] * 10, [None] * 13,
                         [None, "S/N", "Driver", "Passport No.", "Horse Reg", "Trailer Reg", "Phone", "PRODUCT",
                          "Tonnage", "No. OF PACKAGES", "ETA", "INVOICE No.", "EXIT BORDER"],
                         [1, 1, "JOHN TEST", "P1", "H1", "T1", "0", "COAL", "42T", 29, None, "XX-1", "MOKAMBO"]],
                        dtype=object)


def test_registry():
    assert [c.ID for c in list_clients()] == ["bms", "gck"]
    assert get_client("bms") is bms and bms.READY
    assert get_client("gck") is gck and not gck.READY        # waiting for GCK's files


def test_gck_cannot_build_until_set_up():
    with pytest.raises(LayoutError, match="not set up yet"):
        load_template(make_pretend_sample(), gck)


# ---------- recognition (content only, never file names) ----------

def test_bms_excel_is_recognised_from_its_titles():
    assert detect_client_from_excel(bms_like_sheet()) == ("bms", 1.0)


def test_unrelated_excel_is_not_recognised():
    sheet = pd.DataFrame([["Name", "Amount"], ["Coffee", 3]], dtype=object)
    assert detect_client_from_excel(sheet)[0] is None


@pytest.mark.skipif(not SAMPLE_PDFS, reason="sample PDF not present")
def test_bms_sample_pdf_is_recognised_from_its_text():
    client_id, confidence = detect_client_from_pdf(open(SAMPLE_PDFS[0], "rb").read())
    assert client_id == "bms" and confidence == 1.0


@pytest.mark.skipif(not SAMPLE_EXCELS, reason="sample Excel not present")
def test_bms_excel_file_is_recognised_whatever_its_name():
    from core.excel_reader import read_raw_sheets
    data = open(SAMPLE_EXCELS[0], "rb").read()
    import io
    raw = list(read_raw_sheets(io.BytesIO(data), "Book1.xlsx").values())[0]      # any name works
    assert detect_client_from_excel(raw)[0] == "bms"


def test_unrelated_or_broken_pdf_is_not_recognised():
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Holiday photos")
    assert detect_client_from_pdf(doc.tobytes())[0] is None
    assert detect_client_from_pdf(b"not a pdf") == (None, 0.0)


# ---------- wrong pairing ----------

def test_gck_selected_with_a_bms_excel_is_blocked_with_a_clear_message():
    detected, _confidence = detect_client_from_excel(bms_like_sheet())
    message = pairing_problem("gck", detected, "Excel sheet")
    assert message and "BMS" in message and "GCK is selected" in message


def test_matching_pair_has_no_problem():
    assert pairing_problem("bms", "bms", "sample PDF") is None
    assert pairing_problem("bms", None, "sample PDF") is None     # not recognised: the layout check decides


@pytest.mark.skipif(not GCK_FILES, reason="GCK sample and Excel not available yet")
def test_gck_pdf_values_match_its_excel():
    pytest.fail("Fill in the GCK profile from its real sample and Excel, then write this test.")


# ---------- the instruction assistant follows the active client ----------

def test_orders_about_fields_the_client_lacks_are_refused():
    answer = json.dumps({"actions": [dict(type="set_price", item="coal", price=75, trucks=None, range_from=None,
                                          range_to=None, date_text=None, line=None, text=None, tonnage=None,
                                          packages=None)], "unsupported": []})
    plan = ins.read_order("coal price is 75", [], date(2026, 10, 15), lambda *a: answer, client=gck)
    assert plan["understood"] == [] and "GCK has no Coal price" in plan["not_done"][0]
    plan = ins.read_order("coal price is 75", [], date(2026, 10, 15), lambda *a: answer, client=bms)
    assert plan["understood"][0]["set"] == {"price_coal": 75.0}
