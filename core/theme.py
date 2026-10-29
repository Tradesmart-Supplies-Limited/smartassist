# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""The desktop window's colours and fonts. Colours come only from assets/theme.toml."""
import tomllib

from core.job import resource

with open(resource("assets", "theme.toml"), "rb") as _f:
    COLORS = tomllib.load(_f)["colors"]

FONT = "Segoe UI"                 # Windows' own font: nothing to download or install
VERSION = "2.0"                   # 2.0 = the desktop (Tkinter) version
