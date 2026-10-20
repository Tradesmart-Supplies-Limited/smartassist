# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Client profile: BMS (Brother Mining SASU, coal from Kitwe). Everything SmartAssist needs to know about
this client lives here: how to recognise its files, its Excel columns, where every per-truck value sits
in its sample PDF, and its default job settings.

The fields table: where every per-truck value sits in the sample PDF.

Each spot is (page, x, y, key, align).
- page:  0 = road manifest, 1 = commercial invoice, 2 = packing list
- x:     the middle of the text across (for "right": where the text ends), in PDF points
- y:     the middle of the text from top to bottom
  Centred texts keep their middle whatever their length, so any truck's PDF of this format matches.
- key:   which value is written there (see document_values in pdf_builder.py)
- align: "centre" keeps the new text centred on the old one,
         "right" keeps its right edge where the old one ended
"""
from decimal import Decimal

ID = "bms"
NAME = "BMS"
DESCRIPTION = "Kitwe → BMS · 40.00 MT and 40 packages per truck · agent by border"
READY = True            # this profile is complete and can build documents

# ---- recognition (from file CONTENT only, never from file names) ----
# Texts expected in the sample PDF's first 3 pages (spaces do not matter).
PDF_FINGERPRINT = ["ROAD MANIFEST", "COMMERCIAL INVOICE", "PACKING LIST", "BROTHER MINING SASU",
                   "TOTAL CIP BMS USD, DRC", "DRC Clearance Agent"]
# Column titles expected in the Excel (compared in lower case without spaces or punctuation),
# and words expected somewhere in its title rows.
EXCEL_FINGERPRINT = ["Driver", "Passport No.", "Horse Reg", "Trailer Reg", "Tonnage", "No. OF PACKAGES",
                     "INVOICE No.", "EXIT BORDER"]
EXCEL_WORDS = ["BMS"]

# ---- the Excel: field key -> (label shown in the app, usual column titles, simplified) ----
FIELDS = {
    "invoice_no": ("Invoice No.", ["invoiceno", "invoicenumber", "invoice"]),
    "driver": ("Driver", ["driver", "drivername"]),
    "passport": ("Passport No.", ["passportno", "passport"]),
    "horse": ("Horse Reg", ["horsereg", "horse"]),
    "trailer1": ("Trailer 1 Reg", ["trailerreg", "trailer1reg", "trailer1", "trailer"]),
    "trailer2": ("Trailer 2 Reg (optional)", ["trailer2reg", "trailer2"]),
    "tonnage": ("Tonnage", ["tonnage", "tonnagemt", "tons"]),
    "packages": ("No. of packages", ["noofpackages", "packages", "noofbags", "bags"]),
    "border": ("Exit border", ["exitborder", "border"]),
}
OPTIONAL = {"trailer2"}

# ---- the typed-instruction assistant: what it may change for this client ----
PRICE_ITEMS = ["coal", "freight_1", "freight_2", "insurance"]
FREIGHT_LINES = ["freight_1", "freight_2"]
EXAMPLES = ["Coal price is 75"]

# Names of the 3 pages, in order (used for the preview tabs).
PAGE_NAMES = ["Manifest", "Invoice", "Packing list"]

PAGES = 3   # only pages 1-3 of the sample are used; the inspection report is never copied

SPOTS = [
    # ---- Page 1: ROAD MANIFEST ----
    (0, 168.3, 165.3, "invoice_no", "centre"),      # manifest no.
    (0, 326.9, 165.3, "invoice_no", "centre"),      # file ref
    (0, 661.4, 165.3, "date", "centre"),            # loaded date
    (0, 168.3, 278.2, "packages", "centre"),
    (0, 247.6, 278.2, "quantity", "centre"),
    (0, 168.3, 403.3, "border", "centre"),
    (0, 247.6, 403.3, "horse", "centre"),
    (0, 326.9, 403.3, "trailer1", "centre"),
    (0, 455.2, 403.3, "trailer2", "centre"),
    (0, 620.9, 403.3, "driver", "centre"),
    (0, 739.7, 403.3, "passport", "centre"),
    (0, 661.4, 314.3, "agent_contact", "centre"),   # DRC clearance agent, chosen by exit border
    (0, 661.4, 326.4, "agent_mobile", "centre"),
    # ---- Page 2: COMMERCIAL INVOICE ----
    (1, 351.2, 216.0, "date", "centre"),
    (1, 654.1, 216.0, "invoice_no", "centre"),
    (1, 351.2, 237.3, "horse", "centre"),           # top row
    (1, 494.8, 237.3, "trailer1", "centre"),
    (1, 654.0, 237.3, "driver", "centre"),
    (1, 351.1, 301.4, "driver", "centre"),          # truck-detail row
    (1, 458.0, 301.4, "horse", "centre"),
    (1, 532.3, 301.4, "trailer1", "centre"),
    (1, 654.1, 301.4, "trailer2", "centre"),
    (1, 351.1, 344.1, "bags", "centre"),
    (1, 458.0, 344.1, "quantity", "centre"),        # coal line
    (1, 532.3, 344.1, "price_coal", "centre"),
    (1, 654.0, 344.1, "amount_coal", "centre"),
    (1, 167.9, 365.4, "freight1_text", "centre"),   # freight line 1
    (1, 458.0, 365.4, "quantity", "centre"),
    (1, 532.3, 365.4, "price_freight1", "centre"),
    (1, 654.1, 365.4, "amount_freight1", "centre"),
    (1, 167.9, 386.8, "freight2_text", "centre"),   # freight line 2
    (1, 458.0, 386.8, "quantity", "centre"),
    (1, 532.3, 386.8, "price_freight2", "centre"),
    (1, 654.0, 386.8, "amount_freight2", "centre"),
    (1, 458.0, 408.1, "quantity", "centre"),        # insurance line
    (1, 532.3, 408.1, "price_insurance", "centre"),
    (1, 654.0, 408.1, "amount_insurance", "centre"),
    (1, 654.0, 429.5, "total", "centre"),
    # ---- Page 3: PACKING LIST ----
    (2, 362.3, 217.9, "date", "centre"),
    (2, 704.7, 217.9, "invoice_no", "centre"),
    (2, 362.3, 239.8, "horse", "centre"),           # top row
    (2, 476.8, 239.8, "trailer1", "centre"),
    (2, 362.3, 327.4, "driver", "centre"),          # truck-detail row
    (2, 476.8, 327.4, "horse", "centre"),
    (2, 571.2, 327.4, "trailer1", "centre"),
    (2, 704.8, 327.4, "trailer2", "centre"),
    (2, 432.7, 371.2, "packages", "right"),         # sits against the fixed word BAGS
    (2, 571.3, 371.2, "weight", "centre"),          # net weight
    (2, 704.8, 371.2, "weight", "centre"),          # gross weight
]

# What the reference sample (YS-BMS10-288) shows at those spots: used as the example in error
# messages and by the tests. Any truck's PDF of this format is accepted as the sample, as long as
# every spot holds a text in the right FORMAT (below) and repeated values agree everywhere.
# Driver, passport and registration numbers are NOT listed here (they are private).
SAMPLE_VALUES = {
    "invoice_no": "YS-BMS10-288",
    "date": "12-Oct-26",
    "packages": "40",
    "quantity": "40.00 MT",
    "border": "MOKAMBO",
    "bags": "40.00",
    "price_coal": "$70.00",
    "amount_coal": "$2,800.00",
    "freight1_text": "Road freight outside DRC",
    "price_freight1": "$88.00",
    "amount_freight1": "$3,520.00",
    "freight2_text": "Road freight inside DRC",
    "price_freight2": "$140.00",
    "amount_freight2": "$5,600.00",
    "price_insurance": "$2.00",
    "amount_insurance": "$80.00",
    "total": "$12,000.00",
    "weight": "40MT",
    "agent_contact": "Contact person :Pacafic",
    "agent_mobile": "Mobile :+243 995 527 463",
}

# DRC clearance agent per exit border (border written in capitals, as in the Excel).
# These two business contacts are allowed in git on the owner's request (2026-10-14).
# A border not listed here must be confirmed by the manager in the app before its PDFs are made.
AGENTS = {
    "MOKAMBO": {"name": "Pacafic", "mobile": "+243 995 527 463"},
    "SAKANIA": {"name": "Oscar Levite", "mobile": "+243 997 595 381"},
}

# This client's rule: every truck is printed at 40 MT (packages still come from the Excel).
# The manager can switch to the Excel's own tonnage or to fixed figures in Step 3.
CLIENT_TONNAGE = Decimal("40")

# Owner's rule (2026-10-16): BMS figures NEVER change. Every truck is printed at 40.00 MT and 40 packages,
# whatever the Excel says, and the app offers no other choice for BMS.
FIXED_TONNAGE = Decimal("40")
FIXED_PACKAGES = Decimal("40")

# The shape each value must have in an uploaded sample (regular expressions, whole text).
MONEY = r"\$[\d,]+\.\d{2}"
NUMBER = r"\d+(\.\d+)?"
FORMATS = {
    "invoice_no": r"[A-Za-z0-9][A-Za-z0-9/\-]*\d",
    "date": r"\d{1,2}-[A-Z][a-z]{2}-\d{2}",
    "packages": NUMBER,
    "bags": NUMBER,
    "quantity": NUMBER + r" MT",
    "weight": NUMBER + r"MT",
    "total": MONEY,
    "agent_contact": r"Contact person :.+",
    "agent_mobile": r"Mobile :.+",
}
for _name in ("coal", "freight1", "freight2", "insurance"):
    FORMATS["price_" + _name] = MONEY
    FORMATS["amount_" + _name] = MONEY
# Every other field (names, plates, border, freight wording) only has to be present.

# The fixed page titles that show it is this client's 3-page format.
TITLES = ["ROAD MANIFEST", "COMMERCIAL INVOICE", "PACKING LIST"]

# Default prices in USD per MT and default freight wording (all editable in the app).
DEFAULT_PRICES = {
    "coal": Decimal("70"),
    "freight1": Decimal("88"),
    "freight2": Decimal("140"),
    "insurance": Decimal("2"),
}
DEFAULT_FREIGHT1 = "Road freight outside DRC"
DEFAULT_FREIGHT2 = "Road freight inside DRC"
