"""DocuLoop: one 3-page PDF per truck, made from the sample PDF and the loading-order Excel."""
import io
import re
import zipfile
from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from core import layout
from core.excel_reader import clean_sheet, detect_header_row, read_raw_sheets
from core.pdf_builder import (LayoutError, build_pdf, document_values, format_date,
                              load_template, pymupdf, two_decimals)
from core.trucks import FIELDS, OPTIONAL, check_trucks, guess_columns, read_trucks

NO_COLUMN = "(none)"

st.set_page_config(page_title="DocuLoop", layout="wide")
st.title("DocuLoop")
st.caption("Makes the road manifest, commercial invoice and packing list for every truck.")

# ---------------- Step 1: sample PDF ----------------
st.header("Step 1: Sample PDF")
pdf_file = st.file_uploader("Upload the sample PDF (the finished look)", type=["pdf"], key="pdf")
if not pdf_file:
    st.info("Upload the sample PDF to begin.")
    st.stop()

# Check the sample only once per uploaded file, and remember the result.
pdf_id = (pdf_file.name, pdf_file.size)
if st.session_state.get("pdf_id") != pdf_id:
    st.session_state.pdf_id = pdf_id
    st.session_state.pop("results", None)
    try:
        st.session_state.template = load_template(pdf_file.getvalue())
        st.session_state.template_error = None
    except LayoutError as error:
        st.session_state.template = None
        st.session_state.template_error = str(error)

if st.session_state.template_error:
    st.error(st.session_state.template_error)
    st.stop()
template = st.session_state.template
sample = template["sample"]
st.success(f"Layout check passed: all {len(template['spots'])} fields were found on pages 1-3 "
           f"(sample invoice {sample['invoice_no']}). Any later pages are ignored.")

# ---------------- Step 2: Excel ----------------
st.header("Step 2: Loading-order Excel")
xl_file = st.file_uploader("Upload the client's Excel sheet", type=["xlsx", "xlsm"], key="xl")
if not xl_file:
    st.info("Upload the Excel sheet to continue.")
    st.stop()

try:
    raw_sheets = read_raw_sheets(io.BytesIO(xl_file.getvalue()), xl_file.name)
except Exception as error:
    st.error(f"This Excel file cannot be read ({error}).")
    st.stop()

sheet_name = st.selectbox("Sheet", list(raw_sheets))
raw = raw_sheets[sheet_name]
if len(raw) < 2:
    st.warning("This sheet is empty.")
    st.stop()

header_row = st.number_input(
    "Row that contains the column titles (the first row is 1)",
    min_value=1, max_value=len(raw), value=detect_header_row(raw) + 1,
    key=f"header_{xl_file.name}_{sheet_name}",
) - 1
table = clean_sheet(raw, int(header_row))
columns = list(table.columns)
st.caption(f"{len(table)} rows found under the titles: {', '.join(columns)}")

guess = guess_columns(columns)
mapping = {}
missing = [FIELDS[k][0] for k in FIELDS if guess[k] is None and k not in OPTIONAL]
with st.expander("Column matching (open to correct it)", expanded=bool(missing)):
    cols = st.columns(3)
    for n, (key, (label, _names)) in enumerate(FIELDS.items()):
        options = [NO_COLUMN] + columns
        start = options.index(guess[key]) if guess[key] in options else 0
        choice = cols[n % 3].selectbox(label, options, index=start,
                                       key=f"col_{key}_{sheet_name}_{header_row}")
        mapping[key] = None if choice == NO_COLUMN else choice

missing = [FIELDS[k][0] for k in FIELDS if mapping[k] is None and k not in OPTIONAL]
if missing:
    st.error("Choose a column for: " + ", ".join(missing))
    st.stop()

# ---------------- Step 3: job details ----------------
st.header("Step 3: Job details")
c1, c2, c3 = st.columns(3)
doc_date = c1.date_input("Date on the documents", value=date.today(), format="DD/MM/YYYY")
date_text = format_date(doc_date)
c1.caption(f"Will be written as {date_text}")
freight1 = c2.text_input("Freight line 1 wording", value=layout.DEFAULT_FREIGHT1).strip()
freight2 = c3.text_input("Freight line 2 wording", value=layout.DEFAULT_FREIGHT2).strip()

st.subheader("Prices (USD per MT)")
price_labels = {"coal": "Coal", "freight1": "Freight line 1", "freight2": "Freight line 2",
                "insurance": "Insurance"}
prices = {}
for col, (name, label) in zip(st.columns(4), price_labels.items()):
    typed = col.number_input(label, min_value=0.0, value=float(layout.DEFAULT_PRICES[name]),
                             step=1.0, format="%.2f", key=f"price_{name}")
    prices[name] = Decimal(f"{typed:.2f}")

st.subheader("Quantities")
source = st.radio("Where do the tonnage and number of packages come from?",
                  ["From the Excel (each truck's own figures)", "Fixed figures for every truck"],
                  key="source")
from_excel = source.startswith("From the Excel")
fixed_tonnage = fixed_packages = None
if not from_excel:
    f1, f2, _ = st.columns(3)
    fixed_tonnage = Decimal(f"{f1.number_input('Tonnage (MT) for every truck', min_value=0.01, value=40.0, step=0.5, format='%.2f'):.2f}")
    fixed_packages = Decimal(int(f2.number_input("Packages for every truck", min_value=1, value=40, step=1)))

# ---------------- Data check ----------------
st.subheader("Data check")
trucks = read_trucks(table, mapping, int(header_row))
check_trucks(trucks, figures_from_excel=from_excel)
if not trucks:
    st.warning("No trucks were found in this sheet. Check the title row and the column matching.")
    st.stop()

jobs = []       # (file name, values) for every truck that can be made
rows = []       # the table shown to the manager
for truck in trucks:
    tonnage = truck.tonnage if from_excel else fixed_tonnage
    packages = truck.packages if from_excel else fixed_packages
    total = ""
    if truck.errors:
        status = "SKIPPED: " + "; ".join(truck.errors)
    else:
        values = document_values(truck, tonnage, packages, date_text, prices, freight1, freight2)
        file_name = re.sub(r"[^A-Za-z0-9._-]", "_", truck.invoice_no) + ".pdf"
        jobs.append((file_name, values))
        total = values["total"]
        status = "Warning: " + "; ".join(truck.warnings) if truck.warnings else "OK"
    rows.append({
        "Excel row": truck.row, "Invoice No.": truck.invoice_no, "Driver": truck.driver,
        "Passport": truck.passport, "Horse": truck.horse, "Trailer 1": truck.trailer1,
        "Trailer 2": truck.trailer2, "Border": truck.border,
        "Tonnage": two_decimals(tonnage) if tonnage is not None else truck.tonnage_text,
        "Packages": str(packages) if packages is not None else truck.packages_text,
        "Invoice total": total, "Status": status,
    })
st.dataframe(pd.DataFrame(rows), hide_index=True)

skipped = sum(1 for t in trucks if t.errors)
warned = sum(1 for t in trucks if t.warnings and not t.errors)
st.write(f"**{len(jobs)} trucks ready**, {warned} with warnings, {skipped} skipped because of errors.")
if skipped:
    st.error("Skipped trucks get no PDF. Correct them in the Excel and upload it again.")

# Tell the manager when the sample shows other figures than the Excel for the same invoice.
if from_excel:
    for truck in trucks:
        if truck.invoice_no == sample["invoice_no"] and not truck.errors and (
                truck.tonnage != layout.SAMPLE_TONNAGE or truck.packages != layout.SAMPLE_PACKAGES):
            st.info(f"Notice: for {truck.invoice_no} the sample PDF shows {layout.SAMPLE_TONNAGE} MT and "
                    f"{layout.SAMPLE_PACKAGES} packages, but the Excel says {truck.tonnage} MT and "
                    f"{truck.packages} packages. The Excel figures will be used. "
                    "Choose 'Fixed figures for every truck' above if the sample's figures are the right ones.")

# ---------------- Step 4: generate ----------------
st.header("Step 4: Generate")
if st.button("Generate PDFs", type="primary", disabled=not jobs):
    bar = st.progress(0.0, text="Starting...")
    files = []
    for n, (file_name, values) in enumerate(jobs, start=1):
        files.append((file_name, build_pdf(template, values)))
        bar.progress(n / len(jobs), text=f"{n} of {len(jobs)}: {file_name}")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_name, data in files:
            archive.writestr(file_name, data)
    bar.empty()
    # Keep the results, so they stay on screen after a download click.
    st.session_state.results = {"files": files, "zip": zip_buffer.getvalue(),
                                "jobs": jobs, "date": date_text}

results = st.session_state.get("results")
if results:
    files = results["files"]
    if results["jobs"] != jobs:
        st.warning("The data or settings changed after these PDFs were made. "
                   "Click 'Generate PDFs' again to update them.")
    st.success(f"{len(files)} PDFs ready, 3 pages each.")
    st.download_button("Download all as one ZIP", results["zip"],
                       file_name=f"DocuLoop_{results['date']}.zip", mime="application/zip",
                       key="download_zip")

    with st.expander("Download one truck at a time"):
        cols = st.columns(4)
        for n, (file_name, data) in enumerate(files):
            cols[n % 4].download_button(file_name, data, file_name=file_name,
                                        mime="application/pdf", key=f"download_{n}")

    st.subheader("Preview")
    names = [file_name for file_name, _data in files]
    chosen = st.selectbox("Truck to preview", names, key="preview_choice")
    preview = pymupdf.open(stream=dict(files)[chosen], filetype="pdf")
    for page, tab in zip(preview, st.tabs(["Road manifest", "Commercial invoice", "Packing list"])):
        tab.image(page.get_pixmap(dpi=110).tobytes("png"))
