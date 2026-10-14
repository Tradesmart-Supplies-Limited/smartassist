"""Optional inspection reports: match one PDF per truck, combine, and pack into a ZIP.

Reports are never changed: their pages are copied as they are, after the truck's 3 pages.
Nothing here uses Streamlit, so it can be tested on its own.
"""
import io
import os
import re
import zipfile

try:
    import pymupdf
except ImportError:          # older installs call the package "fitz"
    import fitz as pymupdf

# What the manager can choose to download.
MODE_DOCUMENTS = "Documents only"
MODE_SEPARATE = "Documents + inspection report (separate files)"
MODE_COMBINED = "Combined single PDF per truck (documents then report)"
MODES = [MODE_DOCUMENTS, MODE_SEPARATE, MODE_COMBINED]


def _key(text):
    """'YS-BMS10 288_report.pdf' -> 'ysbms10288report' (lower case, no spaces, '-' or '_')."""
    return re.sub(r"[\s\-_]", "", os.path.splitext(str(text))[0].lower())


def _found_in(value, name_key):
    """True if `value` appears in the file name, not glued to other digits ('288' is not in '2880')."""
    value_key = _key(value)
    if not value_key:
        return False
    return re.search(r"(?<!\d)" + re.escape(value_key) + r"(?!\d)", name_key) is not None


def match_reports(trucks, files):
    """Match uploaded reports to trucks by their file names.

    trucks: objects with .invoice_no and .horse. files: list of (file name, PDF bytes).
    Order: invoice number in the file name, then horse plate. A file that fits two trucks, or a
    truck that gets two files, is left for the manager to assign by hand.
    Returns (matched {invoice_no: bytes}, unmatched [(name, bytes)], missing [invoice_no],
             sources {invoice_no: file name}).
    """
    claims = {}          # invoice_no -> list of (name, bytes) that point at it
    unmatched = []
    for name, data in files:
        name_key = _key(name)
        found = [t for t in trucks if _found_in(t.invoice_no, name_key)]
        if not found:
            found = [t for t in trucks if _found_in(t.horse, name_key)]
        if len(found) == 1:
            claims.setdefault(found[0].invoice_no, []).append((name, data))
        else:
            unmatched.append((name, data))       # no truck, or ambiguous
    matched, sources = {}, {}
    for invoice_no, picks in claims.items():
        if len(picks) == 1:
            sources[invoice_no], matched[invoice_no] = picks[0]
        else:
            unmatched.extend(picks)               # two files for one truck: let the manager choose
    missing = [t.invoice_no for t in trucks if t.invoice_no not in matched]
    return matched, unmatched, missing, sources


def validate_report(data):
    """(ok, page count, message) for an uploaded report."""
    if not data:
        return False, 0, "the file is empty"
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        return False, 0, "this is not a readable PDF"
    if doc.needs_pass:
        return False, 0, "the PDF is password-protected"
    if len(doc) == 0:
        return False, 0, "the PDF has no pages"
    return True, len(doc), f"{len(doc)} page(s)"


def combine(doc_pdf_bytes, report_bytes):
    """The truck's 3 pages first, then every report page, copied unchanged."""
    combined = pymupdf.open(stream=doc_pdf_bytes, filetype="pdf")
    combined.insert_pdf(pymupdf.open(stream=report_bytes, filetype="pdf"))
    # The documents' fonts are already subset by the builder. The report's own fonts and images
    # are left exactly as they are; only unused objects are removed and streams compressed.
    return combined.tobytes(garbage=3, deflate=True)


def safe_name(invoice_no):
    """An invoice number usable as a file or folder name."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", invoice_no)


def build_zip(results, reports, mode):
    """One folder per truck, named by invoice number, with the files for the chosen mode.

    results: the app's generated results ({"files": [(name, bytes)], "jobs": [(name, values)]}).
    reports: {invoice_no: report bytes}. A truck without a report gets its documents only.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for (file_name, documents), (_name, values) in zip(results["files"], results["jobs"]):
            invoice_no = values["invoice_no"]
            folder = safe_name(invoice_no)
            report = reports.get(invoice_no)
            if mode == MODE_COMBINED and report:
                archive.writestr(f"{folder}/{folder}_with_inspection.pdf", combine(documents, report))
                continue
            archive.writestr(f"{folder}/{file_name}", documents)
            if mode == MODE_SEPARATE and report:
                archive.writestr(f"{folder}/{folder}_inspection_report.pdf", report)
    return buffer.getvalue()
