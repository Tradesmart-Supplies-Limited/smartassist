"""The fields table: where every per-truck value sits in the sample PDF.

Each spot is (page, x, y, key, align).
- page:  0 = road manifest, 1 = commercial invoice, 2 = packing list
- x, y:  top-left corner of the old text in the sample, in PDF points
- key:   which value is written there (see document_values in pdf_builder.py)
- align: "centre" keeps the new text centred on the old one,
         "right" keeps its right edge where the old one ended
"""
from decimal import Decimal

PAGES = 3   # only pages 1-3 of the sample are used; the inspection report is never copied

SPOTS = [
    # ---- Page 1: ROAD MANIFEST ----
    (0, 130.3, 159.2, "invoice_no", "centre"),      # manifest no.
    (0, 288.9, 159.2, "invoice_no", "centre"),      # file ref
    (0, 636.4, 159.2, "date", "centre"),            # loaded date
    (0, 162.0, 272.2, "packages", "centre"),
    (0, 224.4, 272.2, "quantity", "centre"),
    (0, 144.0, 397.8, "border", "centre"),
    (0, 216.5, 397.3, "horse", "centre"),
    (0, 295.8, 397.3, "trailer1", "centre"),
    (0, 447.2, 397.3, "trailer2", "centre"),
    (0, 579.8, 397.3, "driver", "centre"),
    (0, 713.6, 397.3, "passport", "centre"),
    (0, 603.4, 308.3, "agent_contact", "centre"),   # DRC clearance agent, chosen by exit border
    (0, 598.4, 320.3, "agent_mobile", "centre"),
    # ---- Page 2: COMMERCIAL INVOICE ----
    (1, 328.1, 210.4, "date", "centre"),
    (1, 619.1, 210.4, "invoice_no", "centre"),
    (1, 322.5, 231.8, "horse", "centre"),           # top row
    (1, 466.1, 231.8, "trailer1", "centre"),
    (1, 616.2, 231.8, "driver", "centre"),
    (1, 316.2, 296.2, "driver", "centre"),          # truck-detail row
    (1, 429.4, 295.8, "horse", "centre"),
    (1, 503.6, 295.8, "trailer1", "centre"),
    (1, 646.7, 295.8, "trailer2", "centre"),
    (1, 338.1, 338.5, "bags", "centre"),
    (1, 436.6, 338.5, "quantity", "centre"),        # coal line
    (1, 516.7, 338.5, "price_coal", "centre"),
    (1, 629.9, 338.5, "amount_coal", "centre"),
    (1, 111.5, 359.8, "freight1_text", "centre"),   # freight line 1
    (1, 436.6, 359.8, "quantity", "centre"),
    (1, 516.5, 359.8, "price_freight1", "centre"),
    (1, 630.0, 359.8, "amount_freight1", "centre"),
    (1, 114.8, 381.2, "freight2_text", "centre"),   # freight line 2
    (1, 436.6, 381.2, "quantity", "centre"),
    (1, 514.5, 381.2, "price_freight2", "centre"),
    (1, 629.9, 381.2, "amount_freight2", "centre"),
    (1, 436.6, 402.5, "quantity", "centre"),        # insurance line
    (1, 519.4, 402.5, "price_insurance", "centre"),
    (1, 636.9, 402.5, "amount_insurance", "centre"),
    (1, 628.0, 423.9, "total", "centre"),
    # ---- Page 3: PACKING LIST ----
    (2, 338.6, 212.2, "date", "centre"),
    (2, 668.7, 212.2, "invoice_no", "centre"),
    (2, 332.8, 234.1, "horse", "centre"),           # top row
    (2, 449.7, 234.5, "trailer1", "centre"),
    (2, 326.5, 322.1, "driver", "centre"),          # truck-detail row
    (2, 447.2, 321.7, "horse", "centre"),
    (2, 541.7, 321.7, "trailer1", "centre"),
    (2, 697.1, 321.7, "trailer2", "centre"),
    (2, 421.0, 365.9, "packages", "right"),         # sits against the fixed word BAGS
    (2, 558.5, 365.9, "weight", "centre"),          # net weight
    (2, 691.9, 365.9, "weight", "centre"),          # gross weight
]

# The text the sample must show at those spots. If it does not, the uploaded
# PDF is not the expected sample and the app refuses it.
# Driver, passport and registration numbers are NOT listed here (they are private):
# for those the app only checks that the sample shows the same value at every spot.
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

# The sample's own figures as numbers (used for the "differs from the Excel" notice).
SAMPLE_TONNAGE = Decimal("40")
SAMPLE_PACKAGES = Decimal("40")

# Default prices in USD per MT and default freight wording (all editable in the app).
DEFAULT_PRICES = {
    "coal": Decimal("70"),
    "freight1": Decimal("88"),
    "freight2": Decimal("140"),
    "insurance": Decimal("2"),
}
DEFAULT_FREIGHT1 = "Road freight outside DRC"
DEFAULT_FREIGHT2 = "Road freight inside DRC"
