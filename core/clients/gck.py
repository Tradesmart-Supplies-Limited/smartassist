# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Client profile: GCK (Grande Cimenterie du Katanga, coal from Kitwe to Likasi).

Built on 2026-10-16 from the real GCK sample YS-GCK03-026.pdf and "KITWE TO GCK LOADING ORDER.xlsx".

OWNER'S RULE FOR GCK (2026-10-15): what the Excel and the sample give is what is kept.
- Tonnage and packages are used exactly as the Excel gives them (43T stays 43.00 MT, 28 stays 28):
  no fixed client figures, so CLIENT_TONNAGE / FIXED_* stay None and quantities come from the Excel.
- The DRC clearance agent is printed in black in the sample and is kept exactly as the sample shows it: GCK has no AGENTS table and nothing is swapped by border.
- No other value is changed or rounded; everything is copied or calculated as given.

How GCK differs from BMS: US-Letter pages; the invoice has three lines (coal, freight 1, freight 2) and
no insurance line; the packing list weight is written without "MT" ("42"); the packing list also shows
the border ("Border of Entry"); the invoice has no top row of horse / trailer / driver.

Each spot is (page, x, y, key, align) - see bms.py for the meaning.
"""
from decimal import Decimal

ID = "gck"
NAME = "GCK"
READY = True

# ---- recognition (from file CONTENT only, never from file names) ----
PDF_FINGERPRINT = ["ROAD MANIFEST", "COMMERCIAL INVOICE", "PACKING LIST", "GRANDE CIMENTERIE DU KATANGA",
                   "TOTAL DAP GCK USD, DRC", "Border of Entry"]
EXCEL_FINGERPRINT = ["Driver", "Passport No.", "Horse Reg", "Trailer Reg", "Tonnage", "No. OF PACKAGES",
                     "INVOICE No.", "EXIT BORDER"]
EXCEL_WORDS = ["GCK"]

# ---- the Excel (same columns as BMS) ----
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

# ---- what the (currently hidden) instruction assistant may change ----
PRICE_ITEMS = ["coal", "freight_1", "freight_2"]       # no insurance line for GCK
FREIGHT_LINES = ["freight_1", "freight_2"]
EXAMPLES = ["Coal price is 40"]

PAGE_NAMES = ["Manifest", "Invoice", "Packing list"]
PAGES = 3   # pages 4-6 of the sample (the inspection report) are never copied

SPOTS = [
    (0, 157.4, 159.8, "invoice_no", "centre"),      # manifest no.
    (0, 302.6, 159.8, "invoice_no", "centre"),      # file ref
    (0, 617.9, 159.8, "date", "centre"),      # loaded date
    (0, 157.2, 265.3, "packages", "centre"),
    (0, 230.1, 265.2, "quantity", "centre"),
    (0, 157.5, 383.2, "border", "centre"),
    (0, 230.1, 383.2, "horse", "centre"),
    (0, 302.7, 383.2, "trailer1", "centre"),
    (0, 423.6, 383.2, "trailer2", "centre"),
    (0, 579.8, 383.2, "driver", "centre"),
    (0, 691.8, 383.2, "passport", "centre"),
    (1, 349.1, 215.8, "date", "centre"),
    (1, 649.2, 215.8, "invoice_no", "centre"),
    (1, 349.2, 300.3, "driver", "centre"),      # truck-detail row
    (1, 455.0, 300.3, "horse", "centre"),
    (1, 528.5, 300.3, "trailer1", "centre"),
    (1, 649.2, 300.3, "trailer2", "centre"),
    (1, 349.2, 342.6, "bags", "centre"),
    (1, 455.0, 342.6, "quantity", "centre"),      # coal line
    (1, 528.5, 342.6, "price_coal", "centre"),
    (1, 647.8, 342.6, "amount_coal", "centre"),
    (1, 167.7, 363.2, "freight1_text", "centre"),      # freight line 1
    (1, 455.0, 363.7, "quantity", "centre"),
    (1, 528.5, 363.7, "price_freight1", "centre"),
    (1, 647.8, 363.7, "amount_freight1", "centre"),
    (1, 167.7, 384.3, "freight2_text", "centre"),      # freight line 2
    (1, 455.0, 384.8, "quantity", "centre"),
    (1, 528.5, 384.8, "price_freight2", "centre"),
    (1, 647.8, 384.8, "amount_freight2", "centre"),
    (1, 647.8, 405.9, "total", "centre"),
    (2, 340.6, 207.2, "date", "centre"),
    (2, 657.9, 207.2, "invoice_no", "centre"),
    (2, 446.7, 227.4, "border", "centre"),      # border of entry
    (2, 340.6, 308.6, "driver", "centre"),      # truck-detail row
    (2, 446.6, 308.6, "horse", "centre"),
    (2, 534.2, 308.6, "trailer1", "centre"),
    (2, 658.0, 308.6, "trailer2", "centre"),
    (2, 404.3, 349.1, "packages", "right"),      # sits against the fixed word BAGS
    (2, 534.3, 349.1, "weight", "centre"),      # net weight
    (2, 657.9, 349.1, "weight", "centre"),      # gross weight
]

# What the reference sample (YS-GCK03-026) shows. Driver, passport and plates are not listed (private).
SAMPLE_VALUES = {
    "invoice_no": "YS-GCK03-026",
    "date": "12-Oct-26",
    "packages": "30",
    "quantity": "42.00 MT",
    "border": "MOKAMBO",
    "bags": "30.00",
    "price_coal": "$40.00",
    "amount_coal": "$1,680.00",
    "freight1_text": "Road freight outside DRC",
    "price_freight1": "$120.00",
    "amount_freight1": "$5,040.00",
    "freight2_text": "Road freight inside DRC",
    "price_freight2": "$145.00",
    "amount_freight2": "$6,090.00",
    "total": "$12,810.00",
    "weight": "42",
}

MONEY = r"\$[\d,]+\.\d{2}"
NUMBER = r"\d+(\.\d+)?"
FORMATS = {
    "invoice_no": r"[A-Za-z0-9][A-Za-z0-9/\-]*\d",
    "date": r"\d{1,2}-[A-Z][a-z]{2}-\d{2}",
    "packages": NUMBER,
    "bags": NUMBER,
    "quantity": NUMBER + r" MT",
    "weight": NUMBER,                  # GCK writes the weight without "MT"
    "total": MONEY,
}
for _name in ("coal", "freight1", "freight2"):
    FORMATS["price_" + _name] = MONEY
    FORMATS["amount_" + _name] = MONEY

TITLES = ["ROAD MANIFEST", "COMMERCIAL INVOICE", "PACKING LIST"]
WEIGHT_SUFFIX = ""                     # packing list weight: "42", not "42MT"

AGENTS = {}                            # the agent is kept as the sample shows it (GCK rule)
CLIENT_TONNAGE = None
FIXED_TONNAGE = None                   # GCK keeps the choice of where tonnage and packages come from
FIXED_PACKAGES = None

# Prices in USD per MT, as the GCK sample shows them (coal is editable in the app).
DEFAULT_PRICES = {
    "coal": Decimal("40"),
    "freight1": Decimal("120"),
    "freight2": Decimal("145"),
}
DEFAULT_FREIGHT1 = "Road freight outside DRC"
DEFAULT_FREIGHT2 = "Road freight inside DRC"
