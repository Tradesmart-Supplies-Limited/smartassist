"""The clients DocuLoop serves, and recognising which client a file belongs to.

Recognition uses file CONTENT only (text in the PDF, titles in the Excel), never file names.
"""
import re

from core.clients import bms, gck

_CLIENTS = {c.ID: c for c in (bms, gck)}
MIN_CONFIDENCE = 0.5     # below this, a file is "not recognised"


def get_client(client_id):
    """The profile of one client, e.g. get_client("bms")."""
    return _CLIENTS[client_id]


def list_clients():
    """All client profiles, in the order shown in the app."""
    return list(_CLIENTS.values())


def _simple(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def detect_client_from_pdf(pdf_bytes):
    """(client id or None, confidence 0-1): which ready client's sample this PDF looks like."""
    import pymupdf
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        text = _simple(" ".join(doc[n].get_text() for n in range(min(3, len(doc)))))
    except Exception:
        return None, 0.0
    scores = {c.ID: sum(_simple(s) in text for s in c.PDF_FINGERPRINT) / len(c.PDF_FINGERPRINT)
              for c in list_clients() if c.READY and c.PDF_FINGERPRINT}
    return _best(scores)


def detect_client_from_excel(raw):
    """(client id or None, confidence 0-1) from a raw sheet (all cells as read, no header chosen)."""
    cells = [str(v) for v in raw.head(30).to_numpy().ravel() if v is not None and str(v) != "nan"]
    titles = {_simple(c) for c in cells}
    words = {w for c in cells for w in re.findall(r"[A-Z0-9]+", c.upper())}
    scores = {}
    for c in list_clients():
        if not (c.READY and c.EXCEL_FINGERPRINT):
            continue
        found = sum(_simple(t) in titles for t in c.EXCEL_FINGERPRINT) + sum(w in words for w in c.EXCEL_WORDS)
        scores[c.ID] = found / (len(c.EXCEL_FINGERPRINT) + len(c.EXCEL_WORDS))
    return _best(scores)


def _best(scores):
    if not scores:
        return None, 0.0
    best = max(scores, key=scores.get)
    return (best, scores[best]) if scores[best] >= MIN_CONFIDENCE else (None, scores[best])


def pairing_problem(selected_id, detected_id, what):
    """A plain-language message if a file belongs to another client than the one selected, else None."""
    if detected_id is None or detected_id == selected_id:
        return None
    return (f"This {what} looks like a {get_client(detected_id).NAME} file, but {get_client(selected_id).NAME} "
            f"is selected. Switch to {get_client(detected_id).NAME}, or confirm that you want to use it for "
            f"{get_client(selected_id).NAME}.")
