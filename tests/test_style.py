# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""The style file must never contain a less-than sign: the page's safety filter would then drop the
whole style and SmartAssist would lose its look (this happened once, 2026-10-16)."""
import os

STYLE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")


def test_style_file_has_no_less_than_sign():
    assert "<" not in open(STYLE, encoding="utf-8").read()
