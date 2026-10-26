# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Show SmartAssist's truck icon and title from the very first moment the page opens.

Streamlit's own starting page (inside .venv) carries the Streamlit icon and the title "Streamlit"
until the app has started. This script puts SmartAssist's icon and title in those two places.
start_smartassist.bat runs it at every start, so it comes back even after Streamlit is reinstalled.
It changes only streamlit/static/favicon.png and the <title> in streamlit/static/index.html
(owner's OK, 2026-10-16), and keeps one copy of Streamlit's originals next to them.
Run it by hand once (.venv\\Scripts\\python brand_streamlit.py) if you start SmartAssist from VS Code.
"""
import os
import re
import shutil

import streamlit

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(os.path.dirname(streamlit.__file__), "static")
OUR_ICON = os.path.join(HERE, "assets", "favicon.png")
TITLE = "SmartAssist"


def main():
    icon = os.path.join(STATIC, "favicon.png")
    page = os.path.join(STATIC, "index.html")
    # Keep Streamlit's originals once, so the change can always be undone.
    for path in (icon, page):
        original = path + ".streamlit-original"
        if not os.path.exists(original):
            shutil.copyfile(path, original)
    # The icon: SmartAssist's truck in the Tradesmart colours.
    shutil.copyfile(OUR_ICON, icon)
    # The title: only the text between <title> and </title> changes.
    with open(page, encoding="utf-8") as f:
        html = f.read()
    new_html = re.sub(r"(?s)<title>.*?</title>", f"<title>{TITLE}</title>", html, count=1)
    if new_html != html:
        with open(page, "w", encoding="utf-8", newline="") as f:
            f.write(new_html)


if __name__ == "__main__":
    try:
        main()
    except OSError as error:      # never stop SmartAssist from starting because of the icon
        print(f"Note: could not set SmartAssist's tab icon ({error}). SmartAssist starts normally.")
