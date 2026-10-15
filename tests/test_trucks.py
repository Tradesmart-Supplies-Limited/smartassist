# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Excel reading, column matching, parsing and validation (invented data only)."""
from decimal import Decimal

import pandas as pd

from core.clients import bms as layout     # the BMS client profile
from core.excel_reader import clean_sheet, detect_header_row
from core.trucks import Truck, check_trucks, guess_columns, parse_tonnage, read_trucks

TITLES = [None, "S/N", "Driver", "Passport No.", "Horse Reg", "Trailer Reg", "Phone", "PRODUCT",
          "Tonnage", "No. OF PACKAGES", "ETA", "INVOICE No.", "EXIT BORDER"]


def raw_sheet(data_rows):
    """A sheet like the client's: four title rows, the column titles on row 5, then the trucks."""
    top = [[None, None, "LOADING POINT: SOMEWHERE"] + [None] * 10,
           [None, None, "DESTINATION: ELSEWHERE"] + [None] * 10,
           [None] * 13,
           [None, None, "DATE:01.01.2030"] + [None] * 10]
    return pd.DataFrame(top + [TITLES] + data_rows, dtype=object)


def truck_row(n, tonnage="42T", invoice=None, driver="JOHN TEST", horse=None):
    return [n, n, driver, f"P{n:07d}", horse or f"HRS{n:03d}ZM", f"TRL{n:03d}ZM", "000", "BAGGED COAL",
            tonnage, 29, "2030-01-05", invoice or f"XX-TEST-{n:03d}", "BORDERTOWN"]


def load(data_rows):
    raw = raw_sheet(data_rows)
    header = detect_header_row(raw)
    table = clean_sheet(raw, header)
    trucks = read_trucks(table, guess_columns(table.columns, layout), header)
    check_trucks(trucks)
    return header, trucks


def test_header_row_and_columns_are_found():
    header, trucks = load([truck_row(1), truck_row(2)])
    assert header == 4                      # row 5 in Excel
    assert [t.row for t in trucks] == [6, 7]
    first = trucks[0]
    assert (first.invoice_no, first.driver, first.horse) == ("XX-TEST-001", "JOHN TEST", "HRS001ZM")
    assert (first.trailer1, first.trailer2, first.border) == ("TRL001ZM", "NIL", "BORDERTOWN")
    assert (first.tonnage, first.packages) == (Decimal("42"), Decimal("29"))
    assert first.errors == [] and first.warnings == []


def test_parse_tonnage():
    assert parse_tonnage("42T") == Decimal("42")
    assert parse_tonnage("42.5 t") == Decimal("42.5")
    assert parse_tonnage("40MT") == Decimal("40")
    assert parse_tonnage("42") == Decimal("42")
    for bad in ["", "T", "about 42", "0T", "-5T"]:
        assert parse_tonnage(bad) is None


def test_errors_skip_the_truck():
    _header, trucks = load([
        truck_row(1, invoice="XX-SAME"), truck_row(2, invoice="XX-SAME"),   # duplicate invoice
        truck_row(3, tonnage="heavy"),                                      # unreadable tonnage
        truck_row(4, driver=None),                                          # empty driver
    ])
    assert all(t.errors for t in trucks)
    assert "more than once" in trucks[0].errors[0]
    assert "Tonnage" in trucks[2].errors[0]
    assert trucks[3].errors == ["Driver is empty"]


def test_warnings_do_not_skip_the_truck():
    trucks = [Truck(row=6, invoice_no="A-1", driver="D ONE", horse="H1", tonnage=Decimal("40"),
                    packages=Decimal("40")),
              Truck(row=7, invoice_no="A-2", driver="D TWO", horse="H1", passport="P2", border="B",
                    tonnage=Decimal("40"), packages=Decimal("40"))]
    check_trucks(trucks)
    assert trucks[0].errors == [] and trucks[1].errors == []
    assert len(trucks[0].warnings) == 3     # duplicate horse, empty passport, empty border
    assert trucks[1].warnings == ["Horse H1 appears more than once"]


def test_client_rule_does_not_need_excel_tonnage_but_needs_packages():
    trucks = [Truck(row=6, invoice_no="A-1", driver="D", horse="H", passport="P", border="B",
                    tonnage_text="heavy", packages=Decimal("29")),
              Truck(row=7, invoice_no="A-2", driver="D", horse="H2", passport="P", border="B",
                    tonnage_text="heavy", packages_text="many")]
    check_trucks(trucks, figures_from_excel=True, tonnage_from_excel=False)
    assert trucks[0].errors == []
    assert trucks[1].errors == ["No. of packages cannot be read: 'many'"]


def test_fixed_figures_do_not_need_excel_tonnage():
    trucks = [Truck(row=6, invoice_no="A-1", driver="D", horse="H", passport="P", border="B")]
    check_trucks(trucks, figures_from_excel=True)
    assert trucks[0].errors
    check_trucks(trucks, figures_from_excel=False)
    assert trucks[0].errors == []
