# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Figures, date format and PDF building (invented data only)."""
import time
from datetime import date
from decimal import Decimal

import openpyxl
import pytest

from core.clients import bms as layout     # the BMS client profile
from core.excel_reader import clean_sheet, detect_header_row, read_raw_sheets
from core.pdf_builder import (LayoutError, build_pdf, document_values,
                              format_date, load_template, pymupdf)
from core.trucks import Truck, check_trucks, guess_columns, read_trucks


def money(text):
    return Decimal(text.replace("$", "").replace(",", ""))


def values_for(truck, tonnage, packages=Decimal("40")):
    return document_values(truck, Decimal(tonnage), packages, "12-Oct-26", layout.DEFAULT_PRICES,
                           layout.DEFAULT_FREIGHT1, layout.DEFAULT_FREIGHT2, client=layout)


TRUCK = Truck(row=6, invoice_no="XX-TEST-001", driver="JOHN TEST", passport="P0000001",
              horse="HRS001ZM", trailer1="TRL001ZM", trailer2="NIL", border="Sakania")


@pytest.mark.parametrize("tonnage, total", [("40", "$12,000.00"), ("42", "$12,600.00"),
                                            ("42.5", "$12,750.00")])
def test_total_is_the_sum_of_the_four_amounts(tonnage, total):
    v = values_for(TRUCK, tonnage)
    amounts = [money(v["amount_" + name]) for name in ("coal", "freight1", "freight2", "insurance")]
    assert sum(amounts) == money(v["total"])
    assert v["total"] == total


def test_formats():
    v = values_for(TRUCK, "42.5", Decimal("29"))
    assert (v["quantity"], v["weight"], v["packages"], v["bags"]) == ("42.50 MT", "42.5MT", "29", "29.00")
    assert values_for(TRUCK, "42")["weight"] == "42MT"
    assert (v["price_coal"], v["amount_coal"]) == ("$70.00", "$2,975.00")


def test_amounts_round_half_up():
    v = document_values(TRUCK, Decimal("1.005"), Decimal("1"), "12-Oct-26",
                        {"coal": Decimal("1"), "freight1": Decimal("0"), "freight2": Decimal("0"),
                         "insurance": Decimal("0")}, "a", "b", client=layout)
    assert v["amount_coal"] == "$1.01"


def test_date_format_is_english():
    assert format_date(date(2026, 10, 12)) == "12-Oct-26"
    assert format_date(date(2027, 3, 5)) == "05-Mar-27"


def test_wrong_pdf_is_refused():
    blank = pymupdf.open()
    for _ in range(3):
        blank.new_page()
    with pytest.raises(LayoutError):
        load_template(blank.tobytes(), layout)
    with pytest.raises(LayoutError):
        load_template(b"this is not a pdf", layout)


def test_output_has_three_pages_and_the_new_values(template):
    doc = pymupdf.open(stream=build_pdf(template, values_for(TRUCK, "42.5")), filetype="pdf")
    assert len(doc) == 3
    text = [page.get_text() for page in doc]
    assert "XX-TEST-001" in text[0] and "JOHN TEST" in text[0] and "P0000001" in text[0]
    assert "$12,750.00" in text[1] and "42.50 MT" in text[1]
    assert "42.5MT" in text[2]
    # nothing of the sample's own truck is left behind
    assert layout.SAMPLE_VALUES["invoice_no"] not in "".join(text)
    assert template["sample"]["driver"] not in "".join(text)


def test_long_values_stay_inside_their_cells(template):
    long_truck = Truck(row=6, invoice_no="XX-TEST-LONG-INVOICE-0001",
                       driver="ABCDEFGHIJ KLMNOPQRST UVWXYZABCD",       # 30 characters
                       passport="P000000000001", horse="HRS0000001ZM", trailer1="TRL0000001ZM",
                       trailer2="TRL0000002ZM", border="A VERY LONG BORDER NAME")
    values = document_values(long_truck, Decimal("42.5"), Decimal("1000"), "12-Oct-26",
                             layout.DEFAULT_PRICES, "Road freight outside DRC with extra long wording",
                             "Road freight inside DRC with extra long wording",
                             agent={"name": "A VERY LONG AGENT NAME FOR TESTING", "mobile": "+000 000 000 000 000"},
                             client=layout)
    doc = pymupdf.open(stream=build_pdf(template, values), filetype="pdf")
    for spot in template["spots"]:
        text = values[spot["key"]]
        left, right = spot["cell"]
        # the places where this text appears on this spot's own line, inside this spot's cell
        boxes = [b for b in doc[spot["page"]].search_for(text)
                 if left <= (b.x0 + b.x1) / 2 <= right and b.y0 < spot["baseline"] < b.y1 + 3]
        assert boxes, f"'{text}' not found in its cell"
        assert all(b.x0 >= left and b.x1 <= right for b in boxes), f"'{text}' overflows its cell"


def test_sixty_trucks_in_under_sixty_seconds(template, tmp_path):
    # An invented 60-truck sheet shaped like the client's.
    book = openpyxl.Workbook()
    sheet = book.active
    sheet["C1"], sheet["C2"], sheet["C4"] = "LOADING POINT: SOMEWHERE", "DESTINATION: ELSEWHERE", "DATE:01.01.2030"
    sheet.append([None, "S/N", "Driver", "Passport No.", "Horse Reg", "Trailer Reg", "Phone", "PRODUCT",
                  "Tonnage", "No. OF PACKAGES", "ETA", "INVOICE No.", "EXIT BORDER"])
    for n in range(1, 61):
        sheet.append([n, n, f"DRIVER NUMBER {n}", f"P{n:07d}", f"HRS{n:03d}ZM", f"TRL{n:03d}ZM", "000",
                      "BAGGED COAL", "42T", 29, None, f"XX-TEST-{n:03d}", "MOKAMBO"])
    path = tmp_path / "sixty.xlsx"
    book.save(path)

    start = time.time()
    raw = list(read_raw_sheets(str(path), "sixty.xlsx").values())[0]
    header = detect_header_row(raw)
    assert header == 4
    table = clean_sheet(raw, header)
    trucks = read_trucks(table, guess_columns(table.columns, layout), header)
    check_trucks(trucks)
    assert len(trucks) == 60 and not any(t.errors for t in trucks)
    pdfs = [build_pdf(template, values_for(t, t.tonnage, t.packages)) for t in trucks]
    assert time.time() - start < 60

    for pdf in pdfs:
        assert len(pymupdf.open(stream=pdf, filetype="pdf")) == 3
        assert len(pdf) < 300_000


def test_clearance_agent_stays_as_the_sample_shows(template):
    # Owner's rule (2026-10-29): the DRC clearance agent is copied from the sample, never replaced by border.
    assert layout.AGENTS == {}
    values = values_for(TRUCK, "40")                    # TRUCK's border is Sakania
    assert "agent_contact" not in values and "agent_mobile" not in values
    assert not any(spot["key"].startswith("agent") for spot in template["spots"])
    sample_page1 = pymupdf.open(stream=template["base"], filetype="pdf")[0].get_text()
    if "Contact person" not in sample_page1:
        return                                          # the pretend sample has no agent text to compare
    text = " ".join(pymupdf.open(stream=build_pdf(template, values), filetype="pdf")[0].get_text().split())
    assert "Contact person :Pacafic" in text and "Oscar Levite" not in text   # what the real sample shows


def test_both_bms_looks_are_recognised():
    from conftest import make_pretend_sample
    a4 = load_template(make_pretend_sample(), layout)
    letter = load_template(make_pretend_sample(spots=layout.SPOTS_LETTER, size=(792, 612)), layout)
    assert (a4["layout"], letter["layout"]) == ("A4", "US Letter")
    assert len(letter["spots"]) == len(layout.SPOTS_LETTER)
    page3 = {spot["key"] for spot in letter["spots"] if spot["page"] == 2}
    assert "border" in page3                            # the new look shows "Border of Entry" on the packing list


def test_new_look_is_filled_and_keeps_its_own_layout():
    from conftest import make_pretend_sample
    letter = load_template(make_pretend_sample(spots=layout.SPOTS_LETTER, size=(792, 612)), layout)
    doc = pymupdf.open(stream=build_pdf(letter, values_for(TRUCK, "40")), filetype="pdf")
    assert len(doc) == 3 and doc[0].rect.width == 792
    assert "XX-TEST-001" in doc[0].get_text() and "JOHN TEST" in doc[0].get_text()
    assert "Sakania" in doc[0].get_text() and "Sakania" in doc[2].get_text()   # border also on the packing list
    assert "XX-TEST-001" in doc[1].get_text() and "$12,000.00" in doc[1].get_text()


def test_highlights_on_the_sample_are_not_copied():
    from conftest import make_pretend_sample
    marked = pymupdf.open(stream=make_pretend_sample(), filetype="pdf")
    marked[0].add_highlight_annot(pymupdf.Rect(100, 100, 300, 120))
    template = load_template(marked.tobytes(), layout)
    doc = pymupdf.open(stream=build_pdf(template, values_for(TRUCK, "40")), filetype="pdf")
    assert not any(list(page.annots()) for page in doc)


def test_another_truck_of_the_same_format_is_accepted_as_sample():
    from conftest import make_pretend_sample
    other = load_template(make_pretend_sample({"invoice_no": "XX-TEST-1234", "driver": "ANOTHER DRIVER NAME",
                                               "date": "03-Nov-26", "packages": "29", "weight": "42MT"}), layout)
    assert other["sample"]["invoice_no"] == "XX-TEST-1234"
    assert other["sample"]["driver"] == "ANOTHER DRIVER NAME"
    assert len(other["spots"]) == len(layout.SPOTS)


def test_a_value_in_the_wrong_format_is_refused():
    from conftest import make_pretend_sample
    with pytest.raises(LayoutError, match="quantity"):
        load_template(make_pretend_sample({"quantity": "forty tonnes"}), layout)
