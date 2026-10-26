# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Client profiles, recognition from file content, and wrong pairings (invented data only)."""
import glob
import os

import pandas as pd
import pytest

from conftest import make_pretend_sample
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
    assert get_client("gck") is gck and gck.READY            # set up from GCK's real sample (2026-10-16)


def test_a_bms_sample_is_refused_by_the_gck_layout_check():
    with pytest.raises(LayoutError, match="does not match"):
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


GCK_PDFS = [f for f in GCK_FILES if f.lower().endswith(".pdf") and "-4-6" not in f]
GCK_EXCELS = [f for f in GCK_FILES if f.lower().endswith(".xlsx")]
needs_gck = pytest.mark.skipif(not (GCK_PDFS and GCK_EXCELS), reason="GCK sample and Excel not present")


@needs_gck
def test_gck_files_are_recognised_as_gck():
    from core.excel_reader import read_raw_sheets
    import io
    assert detect_client_from_pdf(open(GCK_PDFS[0], "rb").read())[0] == "gck"
    raw = list(read_raw_sheets(io.BytesIO(open(GCK_EXCELS[0], "rb").read()), "Book1.xlsx").values())[0]
    assert detect_client_from_excel(raw)[0] == "gck"
    assert pairing_problem("bms", "gck", "Excel sheet")          # a GCK file with BMS selected is flagged


@needs_gck
def test_gck_sample_rebuilds_its_own_truck_identically():
    from decimal import Decimal
    from core.pdf_builder import build_pdf, document_values
    from core.trucks import Truck
    data = open(GCK_PDFS[0], "rb").read()
    template = load_template(data, gck)
    s = template["sample"]
    truck = Truck(row=0, invoice_no=s["invoice_no"], driver=s["driver"], passport=s["passport"], horse=s["horse"],
                  trailer1=s["trailer1"], trailer2=s["trailer2"], border=s["border"])
    values = document_values(truck, Decimal(s["weight"]), Decimal(s["packages"]), s["date"], gck.DEFAULT_PRICES,
                             s["freight1_text"], s["freight2_text"], client=gck)
    new = pymupdf.open(stream=build_pdf(template, values), filetype="pdf")
    old = pymupdf.open(stream=data, filetype="pdf")
    words = lambda page: sorted(w[4] for w in page.get_text("words"))
    assert len(new) == 3
    for n in range(3):
        assert words(new[n]) == words(old[n]), f"page {n + 1} differs"


@needs_gck
def test_gck_pdf_values_match_its_excel():
    """GCK rule: tonnage, packages and every value are kept exactly as the Excel gives them."""
    import io
    from decimal import Decimal
    from core.excel_reader import clean_sheet, detect_header_row, read_raw_sheets
    from core.pdf_builder import build_pdf, document_values
    from core.trucks import check_trucks, guess_columns, read_trucks
    raw = list(read_raw_sheets(io.BytesIO(open(GCK_EXCELS[0], "rb").read()), "x.xlsx").values())[0]
    header = detect_header_row(raw)
    table = clean_sheet(raw, header)
    trucks = read_trucks(table, guess_columns(table.columns, gck), header)
    check_trucks(trucks)
    truck = next(t for t in trucks if not t.errors)
    template = load_template(open(GCK_PDFS[0], "rb").read(), gck)
    values = document_values(truck, truck.tonnage, truck.packages, "16-Oct-26", gck.DEFAULT_PRICES,
                             gck.DEFAULT_FREIGHT1, gck.DEFAULT_FREIGHT2, client=gck)
    pages = [" ".join(p.get_text().split()) for p in pymupdf.open(stream=build_pdf(template, values), filetype="pdf")]
    tonnage = f"{truck.tonnage:.2f} MT"                           # e.g. 43T in the Excel -> "43.00 MT"
    assert tonnage in pages[0] and tonnage in pages[1]
    for value in (truck.invoice_no, truck.driver.strip(), truck.passport, truck.horse, truck.border):
        assert value in pages[0], value
    total = truck.tonnage * (Decimal("40") + Decimal("120") + Decimal("145"))
    assert f"${total:,.2f}" in pages[1]                            # three lines, no insurance
    sample_page1 = " ".join(pymupdf.open(GCK_PDFS[0])[0].get_text().split())
    agent_line = sample_page1[sample_page1.index("Contact person :"):][:30]
    assert agent_line in pages[0]                                  # agent kept as the sample shows it
