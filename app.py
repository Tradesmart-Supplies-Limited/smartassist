# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""DocuLoop: one 3-page PDF per truck, made from a client's sample PDF and loading-order Excel."""
import hashlib
import io
import os
import re
import traceback
import zipfile
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import streamlit as st

from core import inspection as insp
from core import instructions as ins
from core import llm, ui
from core.clients import detect_client_from_excel, detect_client_from_pdf, get_client, list_clients, pairing_problem
from core.excel_reader import clean_sheet, detect_header_row, read_raw_sheets
from core.pdf_builder import (LayoutError, agent_for_border, build_pdf, document_values, format_date,
                              load_template, pymupdf, two_decimals)
from core.trucks import cell_text, check_trucks, guess_columns, read_trucks, simplify

NO_COLUMN = "(none)"
HERE = os.path.dirname(os.path.abspath(__file__))
ERROR_LOG = os.path.join(HERE, "output", "error_log.txt")

st.set_page_config(page_title="DocuLoop", page_icon=":material/local_shipping:", layout="wide")
ui.apply_style()

# The opening screen with the beating logo, once per visit (not on every click).
if not st.session_state.get("splash_shown"):
    ui.splash()
    st.session_state.splash_shown = True


def log_error(where):
    """Write the technical details of an unexpected problem to output/error_log.txt (never on screen)."""
    try:
        os.makedirs(os.path.dirname(ERROR_LOG), exist_ok=True)
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now().isoformat(timespec='seconds')} {where}\n{traceback.format_exc()}\n")
    except OSError:
        pass


def file_kind(data):
    """What a file really is, from its first bytes (never from its name)."""
    if not data:
        return "empty"
    if data[:4] == b"%PDF":
        return "pdf"
    if data[:2] == b"PK":
        return "excel"                    # .xlsx / .xlsm are zip files
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "old excel"                # .xls (the older Excel format)
    return "other"


@st.cache_data(ttl=60, show_spinner=False)
def reader_status():
    """Is Ollama there? Checked at most once a minute (the check is slow when Ollama is off)."""
    return llm.status()


reader_ok, reader_message = reader_status()
ui.header(reader_ok, llm.MODEL)

# ---------------- Client choice (remembered in this browser session only) ----------------
CLIENT_IDS = [c.ID for c in list_clients()]
st.session_state.setdefault("active_client", CLIENT_IDS[0])
st.session_state.setdefault("client", st.session_state.active_client)
SETTING_KEYS = [ins.KEY_DATE, ins.KEY_SOURCE, ins.KEY_TONNAGE, ins.KEY_PACKAGES, *ins.KEY_LABELS.values(),
                *ins.KEY_PRICES.values()]


def switch_client(new_id):
    """Use another client: everything loaded for the previous one is cleared."""
    st.session_state.active_client = new_id
    st.session_state.client = new_id
    for key in ["template", "template_error", "pdf_id", "results", "xl_id", "pending", "reports",
                "client_switch_pending", ins.KEY_EXCLUDED, ins.KEY_ONLY, ins.KEY_ACTIVE, *SETTING_KEYS]:
        st.session_state.pop(key, None)
    st.session_state.upload_round = st.session_state.get("upload_round", 0) + 1   # empties the upload boxes


def on_client_change():
    """Client choice changed: ask first if PDFs were already made, otherwise switch now."""
    new_id = st.session_state.client
    if new_id == st.session_state.active_client:
        return
    if st.session_state.get("results"):
        st.session_state.client_switch_pending = new_id
        st.session_state.client = st.session_state.active_client      # stay until confirmed
    else:
        switch_client(new_id)


with st.container(border=True):
    st.radio("Client", CLIENT_IDS, key="client", horizontal=True, on_change=on_client_change,
             format_func=lambda client_id: get_client(client_id).NAME)
    pending_switch = st.session_state.get("client_switch_pending")
    if pending_switch:
        st.warning(f"Switching to {get_client(pending_switch).NAME} clears the sample, the Excel and the PDFs "
                   f"already made for {get_client(st.session_state.active_client).NAME}.", icon=":material/warning:")
        b1, b2, _ = st.columns([1, 1, 3])
        b1.button(f"Switch to {get_client(pending_switch).NAME}", key="confirm_client_switch", type="primary",
                  on_click=switch_client, args=(pending_switch,))
        b2.button(f"Stay on {get_client(st.session_state.active_client).NAME}", key="cancel_client_switch",
                  on_click=lambda: st.session_state.pop("client_switch_pending", None))

client = get_client(st.session_state.active_client)
upload_round = st.session_state.get("upload_round", 0)
round_suffix = "" if upload_round == 0 else f"_{upload_round}"
if not client.READY:
    st.info(f"{client.NAME} is not set up yet: DocuLoop is waiting for a {client.NAME} sample PDF and "
            f"loading-order Excel to learn its layout. Choose another client to work now.",
            icon=":material/construction:")
    st.stop()


def blocked_by_pairing(detected_id, what, override_key):
    """Show a mismatch warning with a switch button. True while the manager has not resolved it."""
    problem = pairing_problem(client.ID, detected_id, what)
    if not problem:
        return False
    st.warning(problem, icon=":material/swap_horiz:")
    c1, c2 = st.columns([1, 2])
    c1.button(f"Switch to {get_client(detected_id).NAME}", key=f"switch_from_{override_key}",
              on_click=switch_client, args=(detected_id,))
    confirmed = c2.checkbox(f"I confirm: use this {what} for {client.NAME} anyway", key=override_key)
    return not confirmed


# ---------------- Step 1: sample PDF ----------------
with st.container(border=True):
    step1 = st.empty()
    ui.step_header(step1, 1, f"{client.NAME} sample PDF")
    pdf_file = st.file_uploader(f"Upload the {client.NAME} sample PDF (the finished look)",
                                type=["pdf", "xlsx", "xlsm", "xls"], key="pdf" + round_suffix)
    if not pdf_file:
        st.info(f"Waiting for the {client.NAME} sample PDF: drop any finished {client.NAME} truck PDF in the box "
                "above. Its file name does not matter.", icon=":material/upload_file:")
        st.stop()

    pdf_bytes = pdf_file.getvalue()
    kind = file_kind(pdf_bytes)
    if kind == "empty":
        st.error("This file is empty. Upload the sample PDF again.", icon=":material/error:")
        st.stop()
    if kind in ("excel", "old excel"):
        st.error("This is an Excel sheet, not the sample PDF. Put it in Step 2 (the Excel box), and put a "
                 f"finished {client.NAME} truck PDF here.", icon=":material/error:")
        st.stop()
    if kind != "pdf":
        st.error(f"This file is not a PDF. Upload a finished {client.NAME} truck PDF here.", icon=":material/error:")
        st.stop()
    if blocked_by_pairing(detect_client_from_pdf(pdf_bytes)[0], "sample PDF", "override_pdf" + round_suffix):
        st.stop()

    # Check the sample only once per file content, and remember the result.
    pdf_id = (client.ID, hashlib.sha256(pdf_bytes).hexdigest())
    if st.session_state.get("pdf_id") != pdf_id:
        st.session_state.pdf_id = pdf_id
        st.session_state.pop("results", None)
        try:
            st.session_state.template = load_template(pdf_bytes, client)
            st.session_state.template_error = None
        except LayoutError as error:
            st.session_state.template = None
            st.session_state.template_error = str(error)
        except Exception:
            log_error("reading the sample PDF")
            st.session_state.template = None
            st.session_state.template_error = (f"This file could not be read. Check that it is a {client.NAME} "
                                               "sample PDF.")

    if st.session_state.template_error:
        st.error(st.session_state.template_error, icon=":material/error:")
        st.stop()
    template = st.session_state.template
    sample = template["sample"]
    ui.step_header(step1, 1, f"{client.NAME} sample PDF", done=True,
                   summary=f"Sample recognised: {pdf_file.name} · all {len(template['spots'])} fields found on "
                           f"pages 1-3 (sample invoice {sample['invoice_no']}). Any later pages are ignored.")

# ---------------- Step 2: Excel ----------------
with st.container(border=True):
    step2 = st.empty()
    ui.step_header(step2, 2, f"{client.NAME} loading-order Excel")
    xl_file = st.file_uploader(f"Upload the {client.NAME} Excel sheet", type=["xlsx", "xlsm", "xls", "pdf"],
                               key="xl" + round_suffix)
    if not xl_file:
        st.info(f"Waiting for the {client.NAME} loading-order Excel: drop the sheet in the box above. "
                "Its file name does not matter.", icon=":material/upload_file:")
        st.stop()

    xl_bytes = xl_file.getvalue()
    kind = file_kind(xl_bytes)
    if kind == "empty":
        st.error("This file is empty. Upload the Excel sheet again.", icon=":material/error:")
        st.stop()
    if kind == "pdf":
        st.error("This is a PDF, not the Excel sheet. Put the sample PDF in Step 1, and the "
                 f"{client.NAME} loading-order Excel here.", icon=":material/error:")
        st.stop()
    if kind == "old excel":
        st.error("This Excel file is in the old .xls format. Open it in Excel, choose Save As, "
                 "'Excel Workbook (.xlsx)', and upload that file.", icon=":material/error:")
        st.stop()
    if kind != "excel":
        st.error(f"This file is not an Excel sheet. Upload the {client.NAME} loading-order Excel here.",
                 icon=":material/error:")
        st.stop()
    try:
        raw_sheets = read_raw_sheets(io.BytesIO(xl_bytes), "sheet.xlsx")      # the real name is never used
    except Exception:
        log_error("reading the Excel")
        st.error(f"This file could not be read. Check that it is the {client.NAME} Excel sheet.",
                 icon=":material/error:")
        st.stop()

    try:
        sheet_name = st.selectbox("Sheet", list(raw_sheets))
        raw = raw_sheets[sheet_name]
        if len(raw) < 2:
            st.warning("This sheet is empty. Choose another sheet or another file.", icon=":material/warning:")
            st.stop()
        if blocked_by_pairing(detect_client_from_excel(raw)[0], "Excel sheet", "override_xl" + round_suffix):
            st.stop()

        # The row with the column titles is found automatically. The manual choice is inside the
        # closed "Column matching" box, which opens by itself when a column cannot be found.
        detected_columns = list(clean_sheet(raw, detect_header_row(raw)).columns)
        detected_missing = any(v is None for k, v in guess_columns(detected_columns, client).items()
                               if k not in client.OPTIONAL)
        matching = st.expander("Column matching (open to correct it)", expanded=detected_missing,
                               icon=":material/view_column:")
        header_row = matching.number_input(
            "Row that contains the column titles (the first row is 1)",
            min_value=1, max_value=len(raw), value=detect_header_row(raw) + 1,
            key=f"header_{xl_file.name}_{sheet_name}",
        ) - 1
        table = clean_sheet(raw, int(header_row))
        columns = list(table.columns)
        matching.caption(f"{len(table)} rows found under the titles: {', '.join(columns)}")

        guess = guess_columns(columns, client)
        mapping = {}
        with matching:
            cols = st.columns(3)
            for n, (key, (label, _names)) in enumerate(client.FIELDS.items()):
                options = [NO_COLUMN] + columns
                start = options.index(guess[key]) if guess[key] in options else 0
                choice = cols[n % 3].selectbox(label, options, index=start,
                                               key=f"col_{key}_{sheet_name}_{header_row}")
                mapping[key] = None if choice == NO_COLUMN else choice
    except Exception:
        log_error("reading the Excel sheet")
        st.error(f"This file could not be read. Check that it is the {client.NAME} Excel sheet.",
                 icon=":material/error:")
        st.stop()

    missing = [client.FIELDS[k][0] for k in client.FIELDS if mapping[k] is None and k not in client.OPTIONAL]
    if missing:
        st.error("These columns were not found: " + ", ".join(missing) + f". Check that this is the {client.NAME} "
                 "Excel, or choose the columns in 'Column matching'.", icon=":material/error:")
        st.stop()
    ui.step_header(step2, 2, f"{client.NAME} loading-order Excel", done=True,
                   summary=f"{xl_file.name} · sheet '{sheet_name}' · titles on row {int(header_row) + 1} · "
                           f"{len(table)} rows read")

# The summary tiles appear here; they are filled in once the trucks have been checked.
tiles = st.container()

# ---------------- Step 3: job details ----------------
step3_card = st.container(border=True)
with step3_card:
    step3 = st.empty()
    ui.step_header(step3, 3, "Job details")

    # Trucks are read here already, so that typed orders can find them.
    trucks = read_trucks(table, mapping, int(header_row))
    if not trucks:
        st.warning("No trucks were found in this sheet. Check the title row and the column matching.",
                   icon=":material/warning:")
        st.stop()
sn_column = next((c for c in columns if simplify(c) in ("sn", "serialno", "serialnumber")), None)


def serial_no(truck):
    """The truck's S/N from the Excel ('' if the sheet has no S/N column)."""
    return cell_text(table.iloc[truck.row - int(header_row) - 2][sn_column]) if sn_column else ""


# A different Excel (or sheet, or title row) means earlier truck orders no longer apply.
xl_id = (xl_file.name, xl_file.size, sheet_name, int(header_row))
if st.session_state.get("xl_id") != xl_id:
    st.session_state.xl_id = xl_id
    for key in (ins.KEY_EXCLUDED, ins.KEY_ONLY, ins.KEY_ACTIVE, "pending", "reports"):
        st.session_state.pop(key, None)

# Every Step 3 setting has a key, so an applied order can change it. These are the defaults.
DEFAULTS = {
    ins.KEY_DATE: date.today(),
    ins.KEY_LABELS["freight_1"]: client.DEFAULT_FREIGHT1,
    ins.KEY_LABELS["freight_2"]: client.DEFAULT_FREIGHT2,
    ins.KEY_SOURCE: ins.SOURCE_CLIENT,
    ins.KEY_TONNAGE: 40.0,
    ins.KEY_PACKAGES: 40,
}
PRICE_NAMES = {"coal": "coal", "freight_1": "freight1", "freight_2": "freight2", "insurance": "insurance"}
for item, name in PRICE_NAMES.items():
    DEFAULTS[ins.KEY_PRICES[item]] = float(client.DEFAULT_PRICES[name])
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

def md(text):
    """Show $ signs as $ (Streamlit would otherwise read them as maths)."""
    return text.replace("$", "\\$")


with step3_card:
    st.markdown("##### :material/event: Date and freight wording")
    c1, c2, c3 = st.columns(3)
    doc_date = c1.date_input("Date on the documents", format="DD/MM/YYYY", key=ins.KEY_DATE)
    date_text = format_date(doc_date)
    c1.caption(f"Will be written as {date_text}")
    freight1 = c2.text_input("Freight line 1 wording", key=ins.KEY_LABELS["freight_1"]).strip()
    freight2 = c3.text_input("Freight line 2 wording", key=ins.KEY_LABELS["freight_2"]).strip()

    st.markdown("##### :material/payments: Coal price (USD per MT)")
    prices = {}
    coal_column, _ = st.columns([1, 3])
    for item, name in PRICE_NAMES.items():
        if item == "coal":
            typed_price = coal_column.number_input(ins.ITEM_NAMES[item], min_value=0.0, step=1.0, format="%.2f",
                                                   key=ins.KEY_PRICES[item])
        else:
            # Not shown to the manager: the default price, or one changed by a typed instruction.
            typed_price = st.session_state[ins.KEY_PRICES[item]]
        prices[name] = Decimal(f"{typed_price:.2f}")

    st.markdown("##### :material/scale: Quantities")
    source = st.radio("Where do the tonnage and number of packages come from?",
                      [ins.SOURCE_CLIENT, ins.SOURCE_EXCEL, ins.SOURCE_FIXED], key=ins.KEY_SOURCE)
    tonnage_from_excel = source == ins.SOURCE_EXCEL
    packages_from_excel = source in (ins.SOURCE_EXCEL, ins.SOURCE_CLIENT)
    fixed_tonnage = client.CLIENT_TONNAGE if source == ins.SOURCE_CLIENT else None
    fixed_packages = None
    if source == ins.SOURCE_CLIENT:
        st.caption(f"Every {client.NAME} truck is printed at {client.CLIENT_TONNAGE} MT; "
                   "the Excel's tonnage column is not used.")
    if source == ins.SOURCE_FIXED:
        f1, f2, _ = st.columns(3)
        fixed_tonnage = Decimal(f"{f1.number_input('Tonnage (MT) for every truck', min_value=0.01, step=0.5, format='%.2f', key=ins.KEY_TONNAGE):.2f}")
        fixed_packages = Decimal(int(f2.number_input("Packages for every truck", min_value=1, step=1,
                                                     key=ins.KEY_PACKAGES)))
    ui.step_header(step3, 3, "Job details", done=True,
                   summary=f"Date {date_text} · coal ${prices['coal']} · {source.split(' (')[0]}")

# ---------------- Data check ----------------
check_trucks(trucks, figures_from_excel=packages_from_excel, tonnage_from_excel=tonnage_from_excel)
excluded_rows = set(st.session_state.get(ins.KEY_EXCLUDED, []))
only_rows = st.session_state.get(ins.KEY_ONLY)


def left_out(truck):
    return truck.row in excluded_rows or bool(only_rows and truck.row not in only_rows)


with st.container(border=True):
    st.markdown("### :material/fact_check: Data check")

    # The DRC clearance agent follows the exit border. For any other border the manager must
    # choose the agent here; until then those trucks wait and get no PDF.
    AGENT_CHOICES = {f"{a['name']} ({a['mobile']}), as for {border.title()}": a for border, a in client.AGENTS.items()}
    CHOOSE = "(choose the agent)"
    confirmed_agents = {}
    unknown_borders = sorted({t.border for t in trucks
                              if not t.errors and not left_out(t) and agent_for_border(t.border, client) is None})
    if unknown_borders:
        with st.container(border=True):
            st.warning("Please confirm the DRC clearance agent: these exit borders have no agent on file. "
                       "Choose one for each border, or correct the border in the Excel.", icon=":material/warning:")
            for border in unknown_borders:
                pick = st.selectbox(f"Clearance agent for exit border '{border or '(empty)'}'",
                                    [CHOOSE] + list(AGENT_CHOICES), key=f"agent_for_{border}")
                if pick != CHOOSE:
                    confirmed_agents[border] = AGENT_CHOICES[pick]

    jobs = []       # (file name, values) for every truck that will be made
    rows = []       # the table shown to the manager
    statuses = []   # the status text of every truck, used for the counts
    for truck in trucks:
        tonnage = truck.tonnage if tonnage_from_excel else fixed_tonnage
        packages = truck.packages if packages_from_excel else fixed_packages
        total = ""
        agent = agent_for_border(truck.border, client) or confirmed_agents.get(truck.border)
        if left_out(truck):
            status = "Excluded by instruction"
        elif truck.errors:
            status = "SKIPPED: " + "; ".join(truck.errors)
        elif agent is None:
            status = "WAITING: confirm the clearance agent above"
        else:
            values = document_values(truck, tonnage, packages, date_text, prices, freight1, freight2, agent,
                                     client=client)
            file_name = f"{client.NAME}_" + re.sub(r"[^A-Za-z0-9._-]", "_", truck.invoice_no) + ".pdf"
            jobs.append((file_name, values))
            total = values["total"]
            status = "Warning: " + "; ".join(truck.warnings) if truck.warnings else "OK"
        statuses.append(status)
        rows.append({
            "Status": ui.STATUS[ui.status_of(status)],
            "Excel row": truck.row, "S/N": serial_no(truck), "Invoice No.": truck.invoice_no,
            "Driver": truck.driver, "Passport": truck.passport, "Horse": truck.horse,
            "Trailer 1": truck.trailer1, "Trailer 2": truck.trailer2, "Border": truck.border,
            "Clearance agent": agent["name"] if agent else "",
            "Tonnage": two_decimals(tonnage) if tonnage is not None else truck.tonnage_text,
            "Packages": str(packages) if packages is not None else truck.packages_text,
            "Invoice total": total, "Details": "" if status == "OK" else status,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, column_config={
        "Status": st.column_config.TextColumn("Status", width="small"),
        "Excel row": st.column_config.NumberColumn("Row", width="small"),
        "S/N": st.column_config.TextColumn("S/N", width="small"),
        "Trailer 2": st.column_config.TextColumn("Trailer 2", width="small"),
        "Details": st.column_config.TextColumn("Details", width="large"),
    })

    skipped = sum(s.startswith("SKIPPED") for s in statuses)
    warned = sum(s.startswith("Warning") for s in statuses)
    excluded = statuses.count("Excluded by instruction")
    waiting = sum(s.startswith("WAITING") for s in statuses)
    st.write(f"**{len(jobs)} trucks ready**, {warned} with warnings, {skipped} skipped because of errors, "
             f"{excluded} excluded by instruction, {waiting} waiting for the clearance agent.")

    # Errors and warnings as one compact list (icon + word, never colour alone).
    issues = [(row, s) for row, s in zip(rows, statuses) if s != "OK"]
    if issues:
        st.markdown("**Points to check**")
        st.markdown("\n".join(f"- {row['Status']} · row {row['Excel row']} · {row['Invoice No.'] or '(no invoice no.)'}"
                              f" · {md(s)}" for row, s in issues))
    if skipped:
        st.error("Skipped trucks get no PDF. Correct them in the Excel and upload it again.", icon=":material/error:")

    # Tell the manager when the sample shows other figures than the Excel for the same invoice.
    sample_tonnage = Decimal(sample["weight"][:-2])        # "40MT" -> 40
    sample_packages = Decimal(sample["packages"])
    for truck in trucks:
        if truck.invoice_no != sample["invoice_no"] or truck.errors:
            continue
        differences = []
        if tonnage_from_excel and truck.tonnage != sample_tonnage:
            differences.append(f"{truck.tonnage} MT (the sample shows {sample_tonnage} MT)")
        if packages_from_excel and truck.packages != sample_packages:
            differences.append(f"{truck.packages} packages (the sample shows {sample_packages})")
        if differences:
            st.info(f"Notice: for {truck.invoice_no} the Excel says " + " and ".join(differences) +
                    ". The Excel figures will be used. Choose 'Fixed figures for every truck' above "
                    "if the sample's figures are the right ones.", icon=":material/info:")

# Summary tiles (drawn above Step 3, in the space kept for them).
with tiles:
    t1, t2, _ = st.columns([1, 1, 3])
    t1.metric("Trucks found", len(trucks), border=True)
    t2.metric("Ready", len(jobs), border=True)

# ---------------- Step 4: generate ----------------
with st.container(border=True):
    step4 = st.empty()
    ui.step_header(step4, 4, "Generate")
    if st.button("Generate PDFs", type="primary", disabled=not jobs, width="stretch",
                 icon=":material/picture_as_pdf:"):
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
                                    "jobs": jobs, "date": date_text, "client": client.ID}

    results = st.session_state.get("results")
    if not results:
        st.caption("Click Generate to make one 3-page PDF per ready truck.")
    else:
        files = results["files"]
        ui.step_header(step4, 4, "Generate", done=True,
                       summary=f"{client.NAME}: {len(files)} PDFs made for {results['date']}")
        if results["jobs"] != jobs:
            st.warning("The data or settings changed after these PDFs were made. "
                       "Click 'Generate PDFs' again to update them.", icon=":material/warning:")
        st.success(f"{client.NAME}: {len(files)} PDFs ready, 3 pages each · {skipped} skipped · {excluded} excluded · "
                   f"{waiting} waiting", icon=":material/task_alt:")
        st.download_button("Download everything (ZIP)", results["zip"],
                           file_name=f"DocuLoop_{client.NAME}_{results['date']}.zip", mime="application/zip",
                           key="download_zip", type="primary", icon=":material/download:")

        with st.expander("Download one truck at a time", icon=":material/description:"):
            head = st.columns([2, 3, 2, 2])
            for col, title in zip(head, ["Invoice No.", "Driver", "Invoice total", ""]):
                col.markdown(f"**{title}**")
            for n, ((file_name, data), (_name, values)) in enumerate(zip(files, results["jobs"])):
                c1, c2, c3, c4 = st.columns([2, 3, 2, 2], vertical_alignment="center")
                c1.write(values["invoice_no"])
                c2.write(values["driver"])
                c3.write(md(values["total"]))
                c4.download_button(file_name, data, file_name=file_name,
                                   mime="application/pdf", key=f"download_{n}", icon=":material/download:")

        with st.container(border=True):
            st.markdown("**:material/preview: Preview**")
            names = [file_name for file_name, _data in files]
            chosen = st.selectbox("Truck to preview", names, key="preview_choice")
            preview = pymupdf.open(stream=dict(files)[chosen], filetype="pdf")
            for page, tab in zip(preview, st.tabs(client.PAGE_NAMES)):
                tab.image(page.get_pixmap(dpi=110).tobytes("png"))

# ---------------- Inspection report (optional, uploaded once) ----------------
# One inspection report is used for every truck. It is kept on this computer, so the manager
# uploads it once and only again when the client sends a new one. It is never changed.
REPORT_PATH = os.path.join(HERE, "output", f"inspection_report_{client.NAME}.pdf")
OLD_REPORT_PATH = os.path.join(HERE, "output", "inspection_report.pdf")      # saved before there were 2 clients
if client.ID == "bms" and not os.path.exists(REPORT_PATH) and os.path.exists(OLD_REPORT_PATH):
    REPORT_PATH = OLD_REPORT_PATH       # keep using the BMS report saved earlier


def save_report():
    """Uploader callback: check the new report and keep it on this computer."""
    upload = st.session_state.get(f"inspection_upload_{st.session_state.get('report_round', 0)}")
    if upload is None:
        return
    ok, _pages, message = insp.validate_report(upload.getvalue())
    if not ok:
        st.session_state.report_error = f"{upload.name} was not saved: {message}."
        return
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "wb") as f:
        f.write(upload.getvalue())
    st.session_state.report_error = None
    st.session_state.report_round = st.session_state.get("report_round", 0) + 1   # empties the upload box


def remove_report():
    """Remove button: stop using the saved report."""
    if os.path.exists(REPORT_PATH):
        os.remove(REPORT_PATH)


with st.container(border=True):
    st.markdown("### :material/assignment: Inspection report (optional)")
    st.caption("Upload the inspection report once. It is kept on this computer and added to every truck "
               "until you replace or remove it. The report itself is never changed.")
    report = None
    if os.path.exists(REPORT_PATH):
        with open(REPORT_PATH, "rb") as f:
            report = f.read()
    if st.session_state.get("report_error"):
        st.error(st.session_state.report_error, icon=":material/error:")

    upload_label = "Replace the inspection report" if report else "Upload the inspection report (PDF)"
    if report:
        _ok, pages, _message = insp.validate_report(report)
        saved_on = date.fromtimestamp(os.path.getmtime(REPORT_PATH)).strftime("%d %b %Y")
        c1, c2 = st.columns([4, 1], vertical_alignment="center")
        c1.success(f"Saved inspection report: {pages} page(s), saved on {saved_on}. It is used for every truck.",
                   icon=":material/task_alt:")
        c2.button("Remove it", key="remove_report", on_click=remove_report, icon=":material/delete:")
        with st.expander("Replace it (only when the client sends a new report)", icon=":material/upload_file:"):
            st.file_uploader(upload_label, type=["pdf"], key=f"inspection_upload_{st.session_state.get('report_round', 0)}",
                             on_change=save_report)
    else:
        st.file_uploader(upload_label, type=["pdf"], key=f"inspection_upload_{st.session_state.get('report_round', 0)}",
                         on_change=save_report)

    # Every truck that is made gets the same report.
    reports = {values["invoice_no"]: report for _name, values in jobs} if report else {}
    st.session_state["reports"] = reports       # keyed by invoice number

    @st.cache_data(show_spinner=False, max_entries=200)
    def combined_pdf(documents, report):
        """Documents then report, made once per pair and remembered."""
        return insp.combine(documents, report)

    @st.cache_data(show_spinner=False, max_entries=6)
    def zip_for(files, jobs, reports, mode, prefix):
        """The batch ZIP, made once per choice and remembered between clicks."""
        return insp.build_zip({"files": files, "jobs": jobs}, reports, mode, prefix)

    if not report:
        pass                              # no report: the app works exactly as before
    elif not results:
        include = st.radio("What to include", insp.MODES, key="inspection_mode")
        st.info("Click 'Generate PDFs' above to get the downloads with the inspection report.", icon=":material/info:")
    else:
        include = st.radio("What to include", insp.MODES, key="inspection_mode")
        with st.spinner("Preparing the ZIP..."):
            batch = zip_for(results["files"], results["jobs"],
                            {values["invoice_no"]: report for _name, values in results["jobs"]}, include,
                            f"{client.NAME}_")
        st.download_button(f"Download ZIP: {include}", batch,
                           file_name=f"DocuLoop_{client.NAME}_{results['date']}_with_inspection.zip",
                           mime="application/zip", key="download_inspection_zip", type="primary",
                           icon=":material/download:")
        with st.expander("Download per truck (documents or combined)", icon=":material/description:"):
            for n, ((file_name, documents), (_name, values)) in enumerate(zip(results["files"], results["jobs"])):
                invoice_no = values["invoice_no"]
                c1, c2, c3 = st.columns([2, 1, 1], vertical_alignment="center")
                c1.write(f"{invoice_no} · {values['driver']}")
                c2.download_button("Documents", documents, file_name=file_name, mime="application/pdf",
                                   key=f"insp_documents_{n}")
                c3.download_button("Combined", combined_pdf(documents, report),
                                   file_name=f"{client.NAME}_{insp.safe_name(invoice_no)}_with_inspection.pdf",
                                   mime="application/pdf", key=f"insp_combined_{n}")

ui.footer()
