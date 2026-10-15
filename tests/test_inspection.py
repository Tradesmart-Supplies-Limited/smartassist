# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Inspection reports: matching, checking, combining and zipping (invented data only)."""
import io
import zipfile
from decimal import Decimal

from core import inspection as insp
from core.clients import bms as layout     # the BMS client profile
from core.pdf_builder import build_pdf, document_values, pymupdf
from core.trucks import Truck

TRUCKS = [Truck(row=6, invoice_no="XX-TEST-288", driver="ONE", horse="AAA101ZM", border="MOKAMBO"),
          Truck(row=7, invoice_no="XX-TEST-289", driver="TWO", horse="AAA102ZM", border="SAKANIA"),
          Truck(row=8, invoice_no="XX-TEST-2880", driver="THREE", horse="AAA103ZM", border="MOKAMBO")]


def report(pages=2, label="Inspection photo"):
    """An invented inspection report with `pages` pages."""
    doc = pymupdf.open()
    for n in range(pages):
        doc.new_page(width=595, height=842).insert_text((72, 72), f"{label} {n + 1}")
    return doc.tobytes()


def documents(template, truck):
    values = document_values(truck, Decimal("40"), Decimal("29"), "14-Oct-26", layout.DEFAULT_PRICES,
                             layout.DEFAULT_FREIGHT1, layout.DEFAULT_FREIGHT2, client=layout)
    return build_pdf(template, values), values


# ---------- matching ----------

def test_match_by_invoice_number_ignoring_case_spaces_dashes_underscores():
    files = [("xx test_288 inspection.PDF", b"a"), ("Report XX-TEST-2880.pdf", b"c")]
    matched, unmatched, missing, sources = insp.match_reports(TRUCKS, files)
    assert matched == {"XX-TEST-288": b"a", "XX-TEST-2880": b"c"}      # 288 is not taken for 2880
    assert sources["XX-TEST-288"] == "xx test_288 inspection.PDF"
    assert unmatched == [] and missing == ["XX-TEST-289"]


def test_match_by_horse_plate():
    matched, unmatched, missing, _ = insp.match_reports(TRUCKS, [("aaa 102 zm.pdf", b"b")])
    assert matched == {"XX-TEST-289": b"b"} and unmatched == []


def test_file_that_fits_two_trucks_is_ambiguous():
    matched, unmatched, _, _ = insp.match_reports(TRUCKS, [("AAA101ZM and AAA102ZM.pdf", b"x")])
    assert matched == {} and unmatched == [("AAA101ZM and AAA102ZM.pdf", b"x")]


def test_two_files_for_one_truck_are_left_for_the_manager():
    files = [("XX-TEST-289 a.pdf", b"1"), ("XX-TEST-289 b.pdf", b"2")]
    matched, unmatched, missing, _ = insp.match_reports(TRUCKS, files)
    assert "XX-TEST-289" not in matched and len(unmatched) == 2 and "XX-TEST-289" in missing


def test_unmatched_file():
    matched, unmatched, missing, _ = insp.match_reports(TRUCKS, [("holiday photos.pdf", b"z")])
    assert matched == {} and unmatched == [("holiday photos.pdf", b"z")] and len(missing) == 3


# ---------- checking ----------

def test_validate_report():
    assert insp.validate_report(report(2)) == (True, 2, "2 page(s)")
    assert insp.validate_report(b"")[0] is False
    assert insp.validate_report(b"not a pdf at all")[0] is False


# ---------- combining ----------

def test_combine_adds_report_pages_and_keeps_the_three_pages(template):
    docs, _values = documents(template, TRUCKS[0])
    combined = pymupdf.open(stream=insp.combine(docs, report(4)), filetype="pdf")
    original = pymupdf.open(stream=docs, filetype="pdf")
    assert len(combined) == 3 + 4
    for n in range(3):
        assert combined[n].get_text() == original[n].get_text()
    assert combined[3].get_text().strip() == "Inspection photo 1"


def test_truck_without_report_still_gets_its_normal_pdf(template):
    docs, values = documents(template, TRUCKS[1])
    results = {"files": [("XX-TEST-289.pdf", docs)], "jobs": [("XX-TEST-289.pdf", values)]}
    for mode in insp.MODES:
        archive = zipfile.ZipFile(io.BytesIO(insp.build_zip(results, {}, mode)))
        assert archive.namelist() == ["XX-TEST-289/XX-TEST-289.pdf"]
        assert archive.read("XX-TEST-289/XX-TEST-289.pdf") == docs


# ---------- ZIP ----------

def test_zip_folders_and_names_for_each_mode(template):
    docs1, values1 = documents(template, TRUCKS[0])
    docs2, values2 = documents(template, TRUCKS[1])
    results = {"files": [("XX-TEST-288.pdf", docs1), ("XX-TEST-289.pdf", docs2)],
               "jobs": [("XX-TEST-288.pdf", values1), ("XX-TEST-289.pdf", values2)]}
    reports = {"XX-TEST-288": report(2)}           # only the first truck has a report

    def names(mode):
        return sorted(zipfile.ZipFile(io.BytesIO(insp.build_zip(results, reports, mode))).namelist())

    assert names(insp.MODE_DOCUMENTS) == ["XX-TEST-288/XX-TEST-288.pdf", "XX-TEST-289/XX-TEST-289.pdf"]
    assert names(insp.MODE_COMBINED) == ["XX-TEST-288/XX-TEST-288_with_inspection.pdf",
                                         "XX-TEST-289/XX-TEST-289.pdf"]
    assert insp.MODES == [insp.MODE_DOCUMENTS, insp.MODE_COMBINED]
