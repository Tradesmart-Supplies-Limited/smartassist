"""Figures, date format and PDF building (invented data only)."""
import time
from datetime import date
from decimal import Decimal

import openpyxl
import pytest

from core import layout
from core.excel_reader import clean_sheet, detect_header_row, read_raw_sheets
from core.pdf_builder import (LayoutError, build_pdf, document_values, format_date,
                              load_template, pymupdf)
from core.trucks import Truck, check_trucks, guess_columns, read_trucks


def money(text):
    return Decimal(text.replace("$", "").replace(",", ""))


def values_for(truck, tonnage, packages=Decimal("40")):
    return document_values(truck, Decimal(tonnage), packages, "12-Oct-26", layout.DEFAULT_PRICES,
                           layout.DEFAULT_FREIGHT1, layout.DEFAULT_FREIGHT2)


TRUCK = Truck(row=6, invoice_no="XX-TEST-001", driver="JOHN TEST", passport="P0000001",
              horse="HRS001ZM", trailer1="TRL001ZM", trailer2="NIL", border="BORDERTOWN")


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
                         "insurance": Decimal("0")}, "a", "b")
    assert v["amount_coal"] == "$1.01"


def test_date_format_is_english():
    assert format_date(date(2026, 10, 12)) == "12-Oct-26"
    assert format_date(date(2027, 3, 5)) == "05-Mar-27"


def test_wrong_pdf_is_refused():
    blank = pymupdf.open()
    for _ in range(3):
        blank.new_page()
    with pytest.raises(LayoutError):
        load_template(blank.tobytes())
    with pytest.raises(LayoutError):
        load_template(b"this is not a pdf")


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
                             "Road freight inside DRC with extra long wording")
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
                      "BAGGED COAL", "42T", 29, None, f"XX-TEST-{n:03d}", "BORDERTOWN"])
    path = tmp_path / "sixty.xlsx"
    book.save(path)

    start = time.time()
    raw = list(read_raw_sheets(str(path), "sixty.xlsx").values())[0]
    header = detect_header_row(raw)
    assert header == 4
    table = clean_sheet(raw, header)
    trucks = read_trucks(table, guess_columns(table.columns), header)
    check_trucks(trucks)
    assert len(trucks) == 60 and not any(t.errors for t in trucks)
    pdfs = [build_pdf(template, values_for(t, t.tonnage, t.packages)) for t in trucks]
    assert time.time() - start < 60

    for pdf in pdfs:
        assert len(pymupdf.open(stream=pdf, filetype="pdf")) == 3
        assert len(pdf) < 300_000
