# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Client profile: GCK. NOT SET UP YET.

GCK's sample PDF and loading-order Excel were not available on 2026-10-15, so nothing about GCK has
been guessed. The app shows GCK in the client choice but refuses to build until this profile is
filled in from a real GCK sample and Excel (same names as in bms.py), and READY is set to True.
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
DEFAULT_PRICES = {}
DEFAULT_FREIGHT1 = ""
DEFAULT_FREIGHT2 = ""
