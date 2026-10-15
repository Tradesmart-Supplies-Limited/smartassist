"""Builds BMS PDFs for 4 invented trucks and lists every word with its position.

Used by test_bms_regression.py to prove that BMS output never changes. The reference file
bms_reference.json was made with the code as it was before the multi-client change (2026-10-15).
"""
import hashlib
import json
from decimal import Decimal

from core.pdf_builder import build_pdf, document_values, pymupdf
from core.trucks import Truck

PRICES = {"coal": Decimal("70"), "freight1": Decimal("88"), "freight2": Decimal("140"), "insurance": Decimal("2")}

# (truck, tonnage, packages, date, freight line 1, freight line 2) - all invented
CASES = [
    (Truck(row=6, invoice_no="XX-TEST-001", driver="JOHN TEST", passport="P0000001", horse="HRS001ZM",
           trailer1="TRL001ZM", trailer2="NIL", border="MOKAMBO"), "40", "29", "12-Oct-26",
     "Road freight outside DRC", "Road freight inside DRC"),
    (Truck(row=7, invoice_no="XX-TEST-002", driver="MARY EXAMPLE", passport="P0000002", horse="HRS002ZM",
           trailer1="TRL002ZM", trailer2="TRL003ZM", border="Sakania"), "42.5", "1000", "05-Jan-27",
     "Road freight Kitwe to Kasumbalesa", "Road freight inside DRC"),
    (Truck(row=8, invoice_no="XX-TEST-LONG-INVOICE-0003", driver="ABCDEFGHIJ KLMNOPQRST UVWXYZABCD",
           passport="P000000000003", horse="HRS0000003ZM", trailer1="TRL0000003ZM", trailer2="NIL",
           border="MOKAMBO"), "42", "40", "31-Dec-26", "Road freight outside DRC", "Road freight inside DRC"),
    (Truck(row=9, invoice_no="XX-TEST-004", driver="A B", passport="", horse="H4", trailer1="T4",
           trailer2="NIL", border="SAKANIA"), "0.5", "1", "01-Feb-27", "x", "y"),
]


def words_of(pdf_bytes):
    """Every word on every page: [page, text, x0, y0, x1, y1] rounded to 0.01 point."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    return [[n, w[4]] + [round(v, 2) for v in w[:4]] for n, page in enumerate(doc) for w in page.get_text("words")]


def snapshot(template, make_values=None):
    """The words of the 4 invented trucks' PDFs. make_values(truck, tonnage, packages, date, f1, f2)."""
    make_values = make_values or (lambda t, ton, pk, d, f1, f2: document_values(
        t, Decimal(ton), Decimal(pk), d, PRICES, f1, f2))
    return [words_of(build_pdf(template, make_values(*case))) for case in CASES]


def digest(words):
    """A fingerprint of the words, so text from the real sample is never stored in git."""
    return hashlib.sha256(json.dumps(words).encode("utf-8")).hexdigest()
