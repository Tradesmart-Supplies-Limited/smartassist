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

VERSION = "1.8"
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _theme():
    """The [theme] colours from .streamlit/config.toml."""
    with open(os.path.join(PROJECT, ".streamlit", "config.toml"), "rb") as f:
        return tomllib.load(f).get("theme", {})


THEME = _theme()
COLORS = {
    "accent": THEME.get("primaryColor", "#2563EB"),
    "text": THEME.get("textColor", "#0F172A"),
    "page": THEME.get("backgroundColor", "#F7FAFF"),
    "card": "#FFFFFF",
    "green": THEME.get("greenColor", "#15803D"),
    "orange": THEME.get("orangeColor", "#985800"),
    "red": THEME.get("redColor", "#B42318"),
    "gray": THEME.get("grayColor", "#475569"),
    "border": THEME.get("borderColor", "#E2E8F0"),
    # Tints from the Figma design (2026-10-20), used only as backgrounds or lines, never as text colours
    "accent2": "#1D4ED8",       # hero gradient end and blue chip text (white text on it 6.7:1)
    "soft": "#EFF6FF",          # selected card / step, blue chip
    "surface": "#F8FAFC",       # upload box, empty step number
    "line": "#CBD5E1",          # outline of empty circles and white buttons
    "muted": "#64748B",         # small secondary text (4.8:1 on white)
    "green_soft": "#ECFDF3",    # the Offline chip
    "cerulean": "#4CA8DC",      # the Tradesmart logo's blue, for the Generate button only (see config.toml)
}

# The truck states in the check table: icon + word, never colour alone.
STATUS = {
    "ready": "✅ Ready",
    "warning": "⚠️ Warning",
    "waiting": "⏳ Waiting",
    "error": "⛔ Error",
}


def _icon(name):
    """One of the design's icons (assets/icons/<name>.svg), embedded in the page itself."""
    with open(os.path.join(PROJECT, "assets", "icons", f"{name}.svg"), "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f'<img class="dl-icon" src="data:image/svg+xml;base64,{data}" alt="">'


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


TITLE = "DocuLoop"
TAGLINE = "Road manifest, commercial invoice and packing list from your Excel sheet"


def header(client_name):
    """The white top bar (name and status chips), then a slot for the blue hero that progress() fills."""
    name = html.escape(client_name)
    st.markdown(
        '<div class="dl-topbar"><div class="dl-brand">'
        # Clicking the logo reloads DocuLoop from the start (a fresh page, like the browser's reload button).
        f'<a class="dl-mark" href="./" target="_self" title="Reload DocuLoop" aria-label="Reload DocuLoop">{_logos()}</a>'
        f'<div class="dl-brand-name">{TITLE}</div></div>'
        '<div class="dl-chips" role="status">'
        f'<span class="dl-chip dl-chip-blue">{_icon("building")} Client: {name}</span>'
        f'<span class="dl-chip dl-chip-green">{_icon("lock")} Offline</span>'
        f'<span class="dl-chip dl-chip-gray">{_icon("info")} v{VERSION}</span>'
        '</div></div>', unsafe_allow_html=True)
    st.session_state["_dl_client_name"] = client_name
    return st.empty()


PROGRESS_STEPS = ["Sample PDF", "Loading-order Excel", "Job details", "Generate"]


def _hero(place, steps_done):
    """The blue hero: where the manager is now and what DocuLoop makes."""
    name = html.escape(st.session_state.get("_dl_client_name", ""))
    current = [f"{name} sample PDF", f"{name} loading-order Excel", "Job details", "Generate"]
    if steps_done < len(current):
        tags = f'<span class="dl-tag">Step {steps_done + 1}</span><span class="dl-tag">{current[steps_done]}</span>'
    else:
        tags = '<span class="dl-tag">✓ All steps done</span>'
    place.markdown(
        f'<div class="dl-hero"><div class="dl-hero-copy"><div class="dl-tags">{tags}</div>'
        f'<p>{TAGLINE}</p></div></div>', unsafe_allow_html=True)


def progress(place, steps_done, hero=None):
    """The Workflow card: done steps get a green tick, the next one is highlighted. Also redraws the hero."""
    if hero is not None:
        _hero(hero, steps_done)
    items = []
    for n, label in enumerate(PROGRESS_STEPS, start=1):
        state = "done" if n <= steps_done else ("current" if n == steps_done + 1 else "todo")
        mark = "✓" if state == "done" else str(n)
        word = {"done": "Done", "current": "Next", "todo": "Waiting"}[state]   # never colour alone
        items.append(f'<div class="dl-pstep dl-{state}" role="listitem"><span class="dl-pnum">{mark}</span>'
                     f'<span class="dl-plabel">{label}<small>{word}</small></span></div>')
    place.markdown(f'<div class="dl-panel"><h4>Workflow</h4><div class="dl-progress" role="list">{"".join(items)}'
                   '</div></div>', unsafe_allow_html=True)


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
