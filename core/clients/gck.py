# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Client profile: GCK. NOT SET UP YET.

GCK's sample PDF and loading-order Excel were not available on 2026-10-15, so nothing about GCK has
been guessed. The app shows GCK in the client choice but refuses to build until this profile is
filled in from a real GCK sample and Excel (same names as in bms.py), and READY is set to True.

OWNER'S RULE FOR GCK (2026-10-15): what the Excel and the sample give is what is kept.
- Tonnage is used exactly as the Excel gives it (42 stays 42, 43 stays 43): no fixed client
  tonnage like BMS's 40 MT, so CLIENT_TONNAGE stays None and quantities come from the Excel.
- The person named for the border (clearance agent or contact) is kept as the sample / Excel
  shows it. It is NOT replaced by exit border like BMS's AGENTS table, unless the owner instructs it.
- No other value is changed or rounded; everything is copied as given.
"""
from decimal import Decimal

ID = "gck"
NAME = "GCK"
READY = False           # waiting for GCK's sample PDF and Excel

PDF_FINGERPRINT = []
EXCEL_FINGERPRINT = []
EXCEL_WORDS = []
FIELDS = {}
OPTIONAL = set()
PRICE_ITEMS = []
FREIGHT_LINES = []
EXAMPLES = []
PAGE_NAMES = ["Page 1", "Page 2", "Page 3"]
PAGES = 3
SPOTS = []
SAMPLE_VALUES = {}
FORMATS = {}
TITLES = []
AGENTS = {}
CLIENT_TONNAGE = None
FIXED_TONNAGE = None        # GCK keeps the choice of where tonnage and packages come from
FIXED_PACKAGES = None
DEFAULT_PRICES = {}
DEFAULT_FREIGHT1 = ""
DEFAULT_FREIGHT2 = ""
