# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Turn the cleaned Excel table into a list of trucks, and check them."""
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import pandas as pd

# Which Excel columns each client has (and their usual titles) is in that client's profile,
# core/clients/<client>.py (FIELDS and OPTIONAL). Column titles are compared in lower case
# with spaces and punctuation removed.

# What people type when there is no second trailer.
NO_TRAILER = {"", "N/A", "NA", "NIL", "NONE", "-"}


@dataclass
class Truck:
    row: int                      # row number in the Excel sheet (first row is 1)
    invoice_no: str = ""
    driver: str = ""
    passport: str = ""
    horse: str = ""
    trailer1: str = ""
    trailer2: str = "NIL"
    border: str = ""
    tonnage_text: str = ""        # exactly what the Excel says, e.g. "42T"
    packages_text: str = ""
    tonnage: Decimal | None = None
    packages: Decimal | None = None
    errors: list = field(default_factory=list)      # the truck is skipped
    warnings: list = field(default_factory=list)    # the truck is still made


def simplify(title):
    """'INVOICE No.' -> 'invoiceno'"""
    return re.sub(r"[^a-z0-9]", "", str(title).lower())


def guess_columns(columns, client):
    """Match each of the client's fields to an Excel column by its title. Returns {key: column or None}."""
    by_simple = {simplify(c): c for c in columns}
    mapping = {}
    for key, (_label, names) in client.FIELDS.items():
        mapping[key] = next((by_simple[n] for n in names if n in by_simple), None)
    return mapping


def cell_text(value):
    """Any Excel cell as clean text. Empty cells give ''."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    if isinstance(value, float) and value == int(value):
        value = int(value)        # 29.0 -> 29
    return " ".join(str(value).split())


def parse_number(text):
    """'29' -> Decimal('29'). Returns None if it is not a number above zero."""
    try:
        number = Decimal(text.replace(",", "."))
    except InvalidOperation:
        return None
    return number if number.is_finite() and number > 0 else None


def parse_tonnage(text):
    """'42T', '42.5 MT' or '42' -> Decimal. Returns None if unreadable."""
    match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(T|MT|TONS?|TONNES?)?", text.strip().upper())
    return parse_number(match.group(1)) if match else None


def read_trucks(df, mapping, header_row):
    """Build one Truck per Excel row. `mapping` is {key: column title or None}."""
    trucks = []
    for i, row in df.iterrows():
        def get(key):
            column = mapping.get(key)
            return cell_text(row[column]) if column else ""

        truck = Truck(row=header_row + 2 + i)
        truck.invoice_no = get("invoice_no")
        truck.driver = get("driver")
        truck.horse = get("horse")
        if not (truck.invoice_no or truck.driver or truck.horse):
            continue              # not a truck row (blank line, totals, notes)
        truck.passport = get("passport")
        truck.trailer1 = get("trailer1")
        trailer2 = get("trailer2")
        truck.trailer2 = "NIL" if trailer2.upper() in NO_TRAILER else trailer2
        truck.border = get("border")
        truck.tonnage_text = get("tonnage")
        truck.packages_text = get("packages")
        truck.tonnage = parse_tonnage(truck.tonnage_text)
        truck.packages = parse_number(truck.packages_text)
        trucks.append(truck)
    return trucks


def check_trucks(trucks, figures_from_excel=True, tonnage_from_excel=None):
    """Fill in each truck's errors and warnings.

    figures_from_excel=False means the user chose fixed figures for every truck,
    so the Excel tonnage and packages are not used and not checked.
    tonnage_from_excel=False means only the Excel tonnage is not used (this client's 40 MT rule).
    """
    if tonnage_from_excel is None:
        tonnage_from_excel = figures_from_excel
    invoice_count, horse_count = {}, {}
    for t in trucks:
        invoice_count[t.invoice_no] = invoice_count.get(t.invoice_no, 0) + 1
        horse_count[t.horse] = horse_count.get(t.horse, 0) + 1

    for t in trucks:
        t.errors, t.warnings = [], []
        if not t.invoice_no:
            t.errors.append("Invoice No. is empty")
        elif invoice_count[t.invoice_no] > 1:
            t.errors.append(f"Invoice No. {t.invoice_no} appears more than once")
        if not t.driver:
            t.errors.append("Driver is empty")
        if not t.horse:
            t.errors.append("Horse Reg is empty")
        elif horse_count[t.horse] > 1:
            t.warnings.append(f"Horse {t.horse} appears more than once")
        if tonnage_from_excel and t.tonnage is None:
            t.errors.append(f"Tonnage cannot be read: '{t.tonnage_text}'")
        if figures_from_excel:
            if t.packages is None:
                t.errors.append(f"No. of packages cannot be read: '{t.packages_text}'")
        if not t.passport:
            t.warnings.append("Passport No. is empty")
        if not t.border:
            t.warnings.append("Exit border is empty")
