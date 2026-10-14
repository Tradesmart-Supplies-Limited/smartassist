"""DocuLoop: one 3-page PDF per truck, made from the sample PDF and the loading-order Excel."""
import io
import os
import re
import zipfile
from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from core import inspection as insp
from core import instructions as ins
from core import layout, llm, ui
from core.excel_reader import clean_sheet, detect_header_row, read_raw_sheets
from core.pdf_builder import (LayoutError, agent_for_border, build_pdf, document_values, format_date,
                              load_template, pymupdf, two_decimals)
from core.trucks import FIELDS, OPTIONAL, cell_text, check_trucks, guess_columns, read_trucks, simplify

NO_COLUMN = "(none)"
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "instructions_log.csv")

st.set_page_config(page_title="DocuLoop", page_icon=":material/local_shipping:", layout="wide")
ui.apply_style()


@st.cache_data(ttl=60, show_spinner=False)
def reader_status():
    """Is Ollama there? Checked at most once a minute (the check is slow when Ollama is off)."""
    return llm.status()


reader_ok, reader_message = reader_status()
ui.header(reader_ok, llm.MODEL)

# ---------------- Step 1: sample PDF ----------------
with st.container(border=True):
    step1 = st.empty()
    ui.step_header(step1, 1, "Sample PDF")
    pdf_file = st.file_uploader("Upload the sample PDF (the finished look)", type=["pdf"], key="pdf")
    if not pdf_file:
        st.info("Waiting for the sample PDF: drop the finished example (e.g. YS-BMS10-288.pdf) in the box above.",
                icon=":material/upload_file:")
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
        st.error(st.session_state.template_error, icon=":material/error:")
        st.stop()
    template = st.session_state.template
    sample = template["sample"]
    ui.step_header(step1, 1, "Sample PDF", done=True,
                   summary=f"Sample recognised: {pdf_file.name} · all {len(template['spots'])} fields found on "
                           f"pages 1-3 (sample invoice {sample['invoice_no']}). Any later pages are ignored.")

# ---------------- Step 2: Excel ----------------
with st.container(border=True):
    step2 = st.empty()
    ui.step_header(step2, 2, "Loading-order Excel")
    xl_file = st.file_uploader("Upload the client's Excel sheet", type=["xlsx", "xlsm"], key="xl")
    if not xl_file:
        st.info("Waiting for the loading-order Excel: drop the client's sheet in the box above.",
                icon=":material/upload_file:")
        st.stop()

    try:
        raw_sheets = read_raw_sheets(io.BytesIO(xl_file.getvalue()), xl_file.name)
    except Exception as error:
        st.error(f"This Excel file cannot be read ({error}).", icon=":material/error:")
        st.stop()

    c1, c2 = st.columns(2)
    sheet_name = c1.selectbox("Sheet", list(raw_sheets))
    raw = raw_sheets[sheet_name]
    if len(raw) < 2:
        st.warning("This sheet is empty.", icon=":material/warning:")
        st.stop()

    header_row = c2.number_input(
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
    with st.expander("Column matching (open to correct it)", expanded=bool(missing),
                     icon=":material/view_column:"):
        cols = st.columns(3)
        for n, (key, (label, _names)) in enumerate(FIELDS.items()):
            options = [NO_COLUMN] + columns
            start = options.index(guess[key]) if guess[key] in options else 0
            choice = cols[n % 3].selectbox(label, options, index=start,
                                           key=f"col_{key}_{sheet_name}_{header_row}")
            mapping[key] = None if choice == NO_COLUMN else choice

    missing = [FIELDS[k][0] for k in FIELDS if mapping[k] is None and k not in OPTIONAL]
    if missing:
        st.error("Choose a column for: " + ", ".join(missing), icon=":material/error:")
        st.stop()
    ui.step_header(step2, 2, "Loading-order Excel", done=True,
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


truck_refs = [{"row": t.row, "sn": serial_no(t), "invoice_no": t.invoice_no, "horse": t.horse,
               "driver": t.driver} for t in trucks]

# A different Excel (or sheet, or title row) means earlier truck orders no longer apply.
xl_id = (xl_file.name, xl_file.size, sheet_name, int(header_row))
if st.session_state.get("xl_id") != xl_id:
    st.session_state.xl_id = xl_id
    for key in (ins.KEY_EXCLUDED, ins.KEY_ONLY, ins.KEY_ACTIVE, "pending", "reports"):
        st.session_state.pop(key, None)
    st.session_state.reports_round = st.session_state.get("reports_round", 0) + 1

# Every Step 3 setting has a key, so an applied order can change it. These are the defaults.
DEFAULTS = {
    ins.KEY_DATE: date.today(),
    ins.KEY_LABELS["freight_1"]: layout.DEFAULT_FREIGHT1,
    ins.KEY_LABELS["freight_2"]: layout.DEFAULT_FREIGHT2,
    ins.KEY_SOURCE: ins.SOURCE_CLIENT,
    ins.KEY_TONNAGE: 40.0,
    ins.KEY_PACKAGES: 40,
}
PRICE_NAMES = {"coal": "coal", "freight_1": "freight1", "freight_2": "freight2", "insurance": "insurance"}
for item, name in PRICE_NAMES.items():
    DEFAULTS[ins.KEY_PRICES[item]] = float(layout.DEFAULT_PRICES[name])
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

# Example orders shown as chips; clicking one fills the order box (it is not applied).
EXAMPLES = ["Skip truck 3", "Coal price is 75", "Date them 15 October", "Only make trucks 1 to 5"]


def apply_pending():
    """Apply button: write the understood order into the settings, then log it."""
    pending = st.session_state.pop("pending")
    ins.apply_plan(pending["plan"], st.session_state)
    ins.log_instruction(LOG_PATH, pending["text"], pending["plan"]["actions"], True)
    st.session_state.instruction_text = ""


def discard_pending():
    """Discard button: change nothing, only log it."""
    pending = st.session_state.pop("pending")
    ins.log_instruction(LOG_PATH, pending["text"], pending["plan"]["actions"], False)


def clear_instructions():
    """Back to the default settings, with no truck excluded."""
    for key, value in DEFAULTS.items():
        st.session_state[key] = value
    for key in (ins.KEY_EXCLUDED, ins.KEY_ONLY, ins.KEY_ACTIVE):
        st.session_state.pop(key, None)


def use_example(text):
    """Example chip: put the example in the order box."""
    st.session_state.instruction_text = text


def md(text):
    """Show $ signs as $ (Streamlit would otherwise read them as maths)."""
    return text.replace("$", "\\$")


with step3_card:
    # ---- the instruction assistant, styled as a command bar ----
    with st.container(border=True):
        st.markdown("**:material/smart_toy: Instructions (optional)**")
        if reader_ok:
            st.caption(reader_message + " Orders change the settings below only after you click Apply.")
            bar, button = st.columns([5, 1], vertical_alignment="bottom")
            bar.text_area("Type an order in plain English", key="instruction_text", height=68,
                          placeholder="e.g. skip truck 3 · coal is 75 · date them 15 October · only trucks 1 to 5")
            read_clicked = button.button("Read instruction", key="read_instruction", type="primary",
                                         icon=":material/send:", disabled="pending" in st.session_state)
            chips = st.columns(len(EXAMPLES) + 2)
            chips[0].caption("Try:")
            for n, example in enumerate(EXAMPLES):
                chips[n + 1].button(example, key=f"example_{n}", type="tertiary", on_click=use_example,
                                    args=(example,))
            if read_clicked:
                typed = st.session_state.instruction_text.strip()
                if typed:
                    with st.spinner("Reading the order... the first one can take up to a minute while the model loads."):
                        try:
                            plan = ins.read_order(typed, truck_refs, date.today(), llm.chat)
                            st.session_state.pending = {"text": typed, "plan": plan}
                        except (llm.LLMError, ins.InvalidReply) as error:
                            st.warning(f"The order could not be read. {error} Use the settings below by hand.",
                                       icon=":material/warning:")
        else:
            st.info(reader_message, icon=":material/cloud_off:")

        pending = st.session_state.get("pending")
        if pending:
            with st.container(border=True):
                st.markdown(md(f"**Your order:** {pending['text']}"))
                understood = pending["plan"]["understood"]
                st.markdown("**:material/check_circle: Understood as:**" +
                            ("" if understood else " nothing that can be applied."))
                for item in understood:
                    st.markdown(md(f"- {item['say']}"))
                if pending["plan"]["not_done"]:
                    st.markdown("**:material/block: Not done:**")
                    for reason in pending["plan"]["not_done"]:
                        st.markdown(md(f"- {reason}"))
                b1, b2, _ = st.columns([1, 1, 4])
                b1.button("Apply", type="primary", key="apply_instruction", on_click=apply_pending,
                          disabled=not understood, icon=":material/done:")
                b2.button("Discard", key="discard_instruction", on_click=discard_pending,
                          icon=":material/close:")

    st.markdown("##### :material/event: Date and freight wording")
    c1, c2, c3 = st.columns(3)
    doc_date = c1.date_input("Date on the documents", format="DD/MM/YYYY", key=ins.KEY_DATE)
    date_text = format_date(doc_date)
    c1.caption(f"Will be written as {date_text}")
    freight1 = c2.text_input("Freight line 1 wording", key=ins.KEY_LABELS["freight_1"]).strip()
    freight2 = c3.text_input("Freight line 2 wording", key=ins.KEY_LABELS["freight_2"]).strip()

    st.markdown("##### :material/payments: Prices (USD per MT)")
    prices = {}
    for col, (item, name) in zip(st.columns(4), PRICE_NAMES.items()):
        typed_price = col.number_input(ins.ITEM_NAMES[item], min_value=0.0, step=1.0, format="%.2f",
                                       key=ins.KEY_PRICES[item])
        prices[name] = Decimal(f"{typed_price:.2f}")

    st.markdown("##### :material/scale: Quantities")
    source = st.radio("Where do the tonnage and number of packages come from?",
                      [ins.SOURCE_CLIENT, ins.SOURCE_EXCEL, ins.SOURCE_FIXED], key=ins.KEY_SOURCE)
    tonnage_from_excel = source == ins.SOURCE_EXCEL
    packages_from_excel = source in (ins.SOURCE_EXCEL, ins.SOURCE_CLIENT)
    fixed_tonnage = layout.CLIENT_TONNAGE if source == ins.SOURCE_CLIENT else None
    fixed_packages = None
    if source == ins.SOURCE_CLIENT:
        st.caption(f"Every truck is printed at {layout.CLIENT_TONNAGE} MT; the Excel's tonnage column is not used.")
    if source == ins.SOURCE_FIXED:
        f1, f2, _ = st.columns(3)
        fixed_tonnage = Decimal(f"{f1.number_input('Tonnage (MT) for every truck', min_value=0.01, step=0.5, format='%.2f', key=ins.KEY_TONNAGE):.2f}")
        fixed_packages = Decimal(int(f2.number_input("Packages for every truck", min_value=1, step=1,
                                                     key=ins.KEY_PACKAGES)))
    ui.step_header(step3, 3, "Job details", done=True,
                   summary=f"Date {date_text} · coal ${prices['coal']} · freight ${prices['freight1']} / "
                           f"${prices['freight2']} · insurance ${prices['insurance']} · "
                           f"{source.split(' (')[0]}")

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
    AGENT_CHOICES = {f"{a['name']} ({a['mobile']}), as for {border.title()}": a for border, a in layout.AGENTS.items()}
    CHOOSE = "(choose the agent)"
    confirmed_agents = {}
    unknown_borders = sorted({t.border for t in trucks
                              if not t.errors and not left_out(t) and agent_for_border(t.border) is None})
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
    ready_tonnage = Decimal("0")
    for truck in trucks:
        tonnage = truck.tonnage if tonnage_from_excel else fixed_tonnage
        packages = truck.packages if packages_from_excel else fixed_packages
        total = ""
        agent = agent_for_border(truck.border) or confirmed_agents.get(truck.border)
        if left_out(truck):
            status = "Excluded by instruction"
        elif truck.errors:
            status = "SKIPPED: " + "; ".join(truck.errors)
        elif agent is None:
            status = "WAITING: confirm the clearance agent above"
        else:
            values = document_values(truck, tonnage, packages, date_text, prices, freight1, freight2, agent)
            file_name = re.sub(r"[^A-Za-z0-9._-]", "_", truck.invoice_no) + ".pdf"
            jobs.append((file_name, values))
            total = values["total"]
            ready_tonnage += tonnage
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
    t1, t2, t3, t4, t5 = st.columns(5)
    t1.metric("Trucks found", len(trucks), border=True)
    t2.metric("Ready", len(jobs), border=True)
    t3.metric("Need attention", warned + waiting, border=True,
              help="Warnings (truck is still made) and trucks waiting for a clearance agent.")
    t4.metric("Skipped", skipped + excluded, border=True,
              help="Errors in the Excel, plus trucks excluded by an instruction.")
    t5.metric("Total tonnage (ready)", f"{two_decimals(ready_tonnage)} MT", border=True)

# ---------------- Step 4: generate ----------------
with st.container(border=True):
    step4 = st.empty()
    ui.step_header(step4, 4, "Generate")
    active = st.session_state.get(ins.KEY_ACTIVE, [])
    if active:
        with st.container(border=True):
            st.markdown("**Active changes from instructions**")
            for line in active:
                st.badge(md(line), icon=":material/tune:", color="blue")
            st.button("Clear all instructions (back to the default settings)", key="clear_instructions",
                      on_click=clear_instructions, icon=":material/restart_alt:")
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
                                    "jobs": jobs, "date": date_text}

    results = st.session_state.get("results")
    if not results:
        st.caption("Click Generate to make one 3-page PDF per ready truck.")
    else:
        files = results["files"]
        ui.step_header(step4, 4, "Generate", done=True,
                       summary=f"{len(files)} PDFs made for {results['date']}")
        if results["jobs"] != jobs:
            st.warning("The data or settings changed after these PDFs were made. "
                       "Click 'Generate PDFs' again to update them.", icon=":material/warning:")
        st.success(f"{len(files)} PDFs ready, 3 pages each · {skipped} skipped · {excluded} excluded · "
                   f"{waiting} waiting", icon=":material/task_alt:")
        st.download_button("Download everything (ZIP)", results["zip"],
                           file_name=f"DocuLoop_{results['date']}.zip", mime="application/zip",
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
            for page, tab in zip(preview, st.tabs(["Manifest", "Invoice", "Packing list"])):
                tab.image(page.get_pixmap(dpi=110).tobytes("png"))

# ---------------- Inspection reports (optional) ----------------
with st.container(border=True):
    st.markdown("### :material/assignment: Inspection reports (optional)")
    st.caption("Upload one inspection report PDF per truck. They are matched by invoice number or horse plate "
               "in the file name, and copied unchanged. Without reports everything above works as before.")
    uploads = st.file_uploader("Inspection report PDFs", type=["pdf"], accept_multiple_files=True,
                               key=f"inspection_files_{st.session_state.get('reports_round', 0)}")

    ready_trucks = [t for t in trucks if t.invoice_no in {values["invoice_no"] for _name, values in jobs}]
    valid_files = []
    for upload in uploads or []:
        ok, _pages, message = insp.validate_report(upload.getvalue())
        if ok:
            valid_files.append((upload.name, upload.getvalue()))
        else:
            st.error(f"{upload.name} is not used: {message}.", icon=":material/error:")

    matched, unmatched, missing, sources = insp.match_reports(ready_trucks, valid_files)
    NO_REPORT = "(no report)"
    manual = {}
    if valid_files and missing and unmatched:
        st.markdown("**Assign the remaining files by hand**")
        unmatched_names = [name for name, _data in unmatched]
        for truck in [t for t in ready_trucks if t.invoice_no in missing]:
            pick = st.selectbox(f"Report for {truck.invoice_no} · {truck.driver}", [NO_REPORT] + unmatched_names,
                                key=f"manual_report_{truck.invoice_no}")
            if pick != NO_REPORT:
                manual[truck.invoice_no] = pick
        doubles = {name for name in manual.values() if list(manual.values()).count(name) > 1}
        if doubles:
            st.error("The same file was chosen for two trucks: " + ", ".join(sorted(doubles)) +
                     ". It is not used until you choose it for one truck only.", icon=":material/error:")
            manual = {inv: name for inv, name in manual.items() if name not in doubles}

    by_name = dict(unmatched)
    reports = dict(matched)
    reports.update({inv: by_name[name] for inv, name in manual.items()})
    st.session_state["reports"] = reports       # keyed by invoice number

    if valid_files:
        report_rows = []
        for truck in ready_trucks:
            if truck.invoice_no in matched:
                source_name, status = sources[truck.invoice_no], "✅ Matched"
            elif truck.invoice_no in manual:
                source_name, status = manual[truck.invoice_no], "✋ Manual"
            else:
                source_name, status = "", "➖ Missing"
            report_rows.append({"Truck": f"{truck.invoice_no} · {truck.driver}", "Matched file": source_name,
                                "Status": status})
        st.dataframe(pd.DataFrame(report_rows), hide_index=True)
        left_over = [name for name, _data in unmatched if name not in manual.values()]
        if left_over:
            st.warning("Not matched to any truck: " + ", ".join(left_over), icon=":material/warning:")
        st.write(f"**{len(reports)} of {len(ready_trucks)} trucks have a report. "
                 f"{len(ready_trucks) - len(reports)} missing.**")

    @st.cache_data(show_spinner=False, max_entries=200)
    def combined_pdf(documents, report):
        """Documents then report, made once per pair and remembered."""
        return insp.combine(documents, report)

    @st.cache_data(show_spinner=False, max_entries=6)
    def zip_for(files, jobs, reports, mode):
        """The batch ZIP, made once per choice and remembered between clicks."""
        return insp.build_zip({"files": files, "jobs": jobs}, reports, mode)

    if not valid_files:
        pass                              # nothing uploaded: the app works exactly as before
    elif not results:
        include = st.radio("What to include", insp.MODES, key="inspection_mode")
        st.info("Click 'Generate PDFs' above to get the downloads with inspection reports.", icon=":material/info:")
    else:
        include = st.radio("What to include", insp.MODES, key="inspection_mode")
        with st.spinner("Preparing the ZIP..."):
            batch = zip_for(results["files"], results["jobs"], reports, include)
        st.download_button(f"Download ZIP: {include}", batch,
                           file_name=f"DocuLoop_{results['date']}_{len(reports)}_reports.zip",
                           mime="application/zip", key="download_inspection_zip", type="primary",
                           icon=":material/download:")
        with st.expander("Download per truck (documents, inspection report, combined)", icon=":material/description:"):
            for n, ((file_name, documents), (_name, values)) in enumerate(zip(results["files"], results["jobs"])):
                invoice_no = values["invoice_no"]
                report = reports.get(invoice_no)
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1], vertical_alignment="center")
                c1.write(f"{invoice_no} · {values['driver']}")
                c2.download_button("Documents", documents, file_name=file_name, mime="application/pdf",
                                   key=f"insp_documents_{n}")
                if report:
                    folder = insp.safe_name(invoice_no)
                    c3.download_button("Inspection report", report, file_name=f"{folder}_inspection_report.pdf",
                                       mime="application/pdf", key=f"insp_report_{n}")
                    c4.download_button("Combined", combined_pdf(documents, report),
                                       file_name=f"{folder}_with_inspection.pdf", mime="application/pdf",
                                       key=f"insp_combined_{n}")
                else:
                    c3.caption("No report")

ui.footer()
