# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Small helpers for DocuLoop's look. UI only: nothing here changes a figure or a document.

All colours come from the [theme] block of .streamlit/config.toml (the one place to change them).
Everything is local: system fonts, inline SVG and Streamlit's own bundled icons.
"""
import base64
import html
import os
import tomllib

import streamlit as st

VERSION = "1.7"
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _theme():
    """The [theme] colours from .streamlit/config.toml."""
    with open(os.path.join(PROJECT, ".streamlit", "config.toml"), "rb") as f:
        return tomllib.load(f).get("theme", {})


THEME = _theme()
COLORS = {
    "accent": THEME.get("primaryColor", "#1F4E79"),
    "text": THEME.get("textColor", "#1B2533"),
    "page": THEME.get("backgroundColor", "#F5F7FA"),
    "card": "#FFFFFF",
    "green": THEME.get("greenColor", "#1E7A46"),
    "orange": THEME.get("orangeColor", "#985800"),
    "red": THEME.get("redColor", "#B42318"),
    "gray": THEME.get("grayColor", "#5A6676"),
    "border": THEME.get("borderColor", "#D3DCE6"),
    "accent2": "#2A6AA3",       # header gradient end: a brighter navy (white text on it 5.7:1)
    "cerulean": "#4CA8DC",      # the Tradesmart logo's blue, for the Generate button only (see config.toml)
}

# The truck states in the check table: icon + word, never colour alone.
STATUS = {
    "ready": "✅ Ready",
    "warning": "⚠️ Warning",
    "waiting": "⏳ Waiting",
    "error": "⛔ Error",
    "excluded": "➖ Excluded",
}

# A simple truck logo, drawn in code (no image file, no download).
LOGO = """<svg width="40" height="40" viewBox="0 0 40 40" aria-hidden="true">
<rect x="2" y="12" width="22" height="14" rx="2" fill="#FFFFFF"/>
<path d="M24 16h7l5 5v5H24z" fill="#FFFFFF" opacity="0.85"/>
<circle cx="10" cy="29" r="3.5" fill="#FFFFFF"/><circle cx="30" cy="29" r="3.5" fill="#FFFFFF"/>
<path d="M7 19h12M7 22h8" stroke="currentColor" stroke-width="2"/></svg>"""


# A tiny truck facing left (cab in front) that pulls the status line along, drawn in code.
TICKER_TRUCK = """<svg class="dl-ticker-truck" width="30" height="13" viewBox="0 0 30 13" aria-hidden="true">
<path d="M1 10V6l2.5-4H9v8z" fill="var(--dl-accent)"/><rect x="3.5" y="3" width="3.5" height="2.5" fill="#FFFFFF"/>
<rect x="10" y="1" width="19" height="9" rx="1" fill="var(--dl-accent)"/><rect x="9" y="8" width="2" height="1.5" fill="var(--dl-gray)"/>
<circle cx="5" cy="11" r="1.8" fill="var(--dl-text)"/><circle cx="20" cy="11" r="1.8" fill="var(--dl-text)"/>
<circle cx="25" cy="11" r="1.8" fill="var(--dl-text)"/></svg>"""


def _logos():
    """The Tradesmart Supplies logo (assets/logos.png), embedded in the page itself."""
    path = os.path.join(PROJECT, "assets", "logos.png")
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f'<img class="dl-logos" src="data:image/png;base64,{data}" alt="Tradesmart Supplies Limited">'


def splash():
    """The opening screen: the logo beats twice, then the screen fades away to the app."""
    st.markdown(f'<div class="dl-splash" aria-hidden="true">{_logos()}<div class="dl-splash-name">DocuLoop</div></div>',
                unsafe_allow_html=True)


def apply_style():
    """Load assets/style.css once per page, with the theme colours as CSS variables."""
    with open(os.path.join(PROJECT, "assets", "style.css"), encoding="utf-8") as f:
        css = f.read()
    variables = "".join(f"--dl-{name}:{value};" for name, value in COLORS.items())
    st.html(f"<style>:root{{{variables}}}\n{css}</style>")


def header(client_name):
    """The top: the navy band running into the logos, and a small status ticker under it."""
    status = (f"Client: {html.escape(client_name)} · 🔒 Works offline, nothing leaves this computer · "
              f"DocuLoop v{VERSION}")
    st.markdown(
        '<div class="dl-top">'
        f'<div class="dl-header" style="color:{COLORS["accent"]}">{LOGO}<div>'
        '<h1>DocuLoop</h1><p>Road manifest, commercial invoice and packing list from your Excel sheet</p>'
        f'</div></div><div class="dl-logo-tile">{_logos()}</div></div>'
        f'<div class="dl-ticker" role="status"><span>{TICKER_TRUCK} {status}</span></div>',
        unsafe_allow_html=True)


PROGRESS_STEPS = ["Sample PDF", "Loading-order Excel", "Job details", "Generate"]


def progress(place, steps_done):
    """The progress tracker under the header: done steps get a green tick, the next one is highlighted."""
    items = []
    for n, label in enumerate(PROGRESS_STEPS, start=1):
        state = "done" if n <= steps_done else ("current" if n == steps_done + 1 else "todo")
        mark = "✓" if state == "done" else str(n)
        word = {"done": "Done", "current": "Next", "todo": "Waiting"}[state]   # never colour alone
        items.append(f'<div class="dl-pstep dl-{state}"><span class="dl-pnum">{mark}</span>'
                     f'<span class="dl-plabel">{label}<small>{word}</small></span></div>')
    place.markdown(f'<div class="dl-progress" role="list">{"".join(items)}</div>', unsafe_allow_html=True)


def step_header(place, number, title, done=False, summary=""):
    """A numbered step title (a tick when done), with an optional one-line summary under it."""
    mark = "✓" if done else str(number)
    text = (f'<div class="dl-step{" dl-done" if done else ""}"><span class="dl-num">{mark}</span>'
            f'<h3>Step {number} · {html.escape(title)}</h3></div>')
    if summary:
        safe = html.escape(summary).replace("$", "&#36;")    # a plain $, not the start of maths
        text += f'<p class="dl-summary">{"✓ " if done else ""}{safe}</p>'
    place.markdown(text, unsafe_allow_html=True)


def status_of(text):
    """Turn the data check's status text into one of the STATUS states."""
    if text.startswith("Excluded"):
        return "excluded"
    if text.startswith("SKIPPED"):
        return "error"
    if text.startswith("WAITING"):
        return "waiting"
    if text.startswith("Warning"):
        return "warning"
    return "ready"


def footer():
    st.markdown(f'<div class="dl-footer">© 2026 Tradesmart Supplies Limited. All rights reserved.<br>'
                f'Developed by Tradesmart Supplies Limited · DocuLoop v{VERSION} · '
                'Works within the Tradesmart Supplies Limited Network</div>', unsafe_allow_html=True)
