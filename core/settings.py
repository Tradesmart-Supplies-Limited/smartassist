# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Names of the Step 3 settings and the quantity-source texts.

These used to live in core/instructions.py together with the typed-instructions assistant (Ollama),
which was removed from the screen on 2026-10-15 and from the code on 2026-10-20.
"""

KEY_DATE = "doc_date"
KEY_PRICES = {"coal": "price_coal", "freight_1": "price_freight1",
              "freight_2": "price_freight2", "insurance": "price_insurance"}
KEY_LABELS = {"freight_1": "freight1_text", "freight_2": "freight2_text"}
KEY_SOURCE = "source"
SOURCE_CLIENT = "This client's tonnage for every truck, packages from the Excel"
SOURCE_EXCEL = "From the Excel (each truck's own figures)"
SOURCE_FIXED = "Fixed figures for every truck"
KEY_TONNAGE = "fixed_tonnage"
KEY_PACKAGES = "fixed_packages"

ITEM_NAMES = {"coal": "Coal", "freight_1": "Freight line 1", "freight_2": "Freight line 2",
              "insurance": "Insurance"}
