"""Small helpers for DocuLoop's look. UI only: nothing here changes a figure or a document.

All colours come from the [theme] block of .streamlit/config.toml (the one place to change them).
Everything is local: system fonts, inline SVG and Streamlit's own bundled icons.
"""
import base64
import html
import os
import tomllib

import streamlit as st

VERSION = "1.5"
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


def _logos():
    """The Tradesmart Supplies and OGEFREM logos (assets/logos.png), embedded in the page itself."""
    path = os.path.join(PROJECT, "assets", "logos.png")
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f'<img class="dl-logos" src="data:image/png;base64,{data}" alt="Tradesmart Supplies Limited and OGEFREM">'


def apply_style():
    """Load assets/style.css once per page, with the theme colours as CSS variables."""
    with open(os.path.join(PROJECT, "assets", "style.css"), encoding="utf-8") as f:
        css = f.read()
    variables = "".join(f"--dl-{name}:{value};" for name, value in COLORS.items())
    st.html(f"<style>:root{{{variables}}}\n{css}</style>")


def header(assistant_ok, model):
    """The top band: logo, name, subtitle, and the assistant status on the right."""
    left, right = st.columns([5, 2], vertical_alignment="center")
    left.markdown(
        f'<div class="dl-header" style="color:{COLORS["accent"]}">{LOGO}<div>'
        '<h1>DocuLoop</h1><p>Road manifest, commercial invoice and packing list from your Excel sheet</p>'
        f'</div>{_logos()}</div>', unsafe_allow_html=True)
    with right:
        if assistant_ok:
            st.badge("Assistant ready", icon=":material/smart_toy:", color="green")
        else:
            st.badge("Assistant offline", icon=":material/cloud_off:", color="gray")
        st.badge(f"Model {model}", icon=":material/memory:", color="blue")
        st.badge("Works offline", icon=":material/lock:", color="gray")


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
    st.markdown(f'<div class="dl-footer">Built with Llama · DocuLoop v{VERSION} · '
                'works on this computer only</div>', unsafe_allow_html=True)
