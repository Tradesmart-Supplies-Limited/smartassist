# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""One SmartAssist job, step by step, without any screen code.

The desktop window (desktop_app.py) only shows what this module decides. Every rule here is the
same as in the browser version (app.py): the same checks, the same messages, the same figures and
the same PDF builder, so both give identical documents.
"""
import io
import os
import re
import sys
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from core import inspection as insp
from core import settings
from core.clients import detect_client_from_excel, detect_client_from_pdf, get_client, pairing_problem
from core.excel_reader import clean_sheet, detect_header_row, read_raw_sheets
from core.pdf_builder import (LayoutError, agent_for_border, build_pdf, document_values, format_date,
                              load_template, two_decimals)
from core.trucks import cell_text, check_trucks, guess_columns, read_trucks, simplify

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FROZEN = getattr(sys, "frozen", False)          # True inside SmartAssist.exe (PyInstaller)


def resource(*parts):
    """A file that ships with SmartAssist (logo, icons): inside the .exe or in the project folder."""
    base = getattr(sys, "_MEIPASS", PROJECT)
    return os.path.join(base, *parts)


def data_dir():
    """Where SmartAssist keeps its own files (inspection reports, error log).

    In the installed program that is the user's own folder, because programs may not write in
    C:\\Program Files. When run from the project folder it stays the project's output folder.
    """
    if FROZEN:
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SmartAssist")
    return os.path.join(PROJECT, "output")


def log_error(where):
    """Write the technical details of an unexpected problem to error_log.txt (never on screen)."""
    try:
        os.makedirs(data_dir(), exist_ok=True)
        with open(os.path.join(data_dir(), "error_log.txt"), "a", encoding="utf-8") as f:
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


@dataclass
class Step:
    """The answer to one upload: ok, or an error message, or a file that looks like another client's."""
    ok: bool
    error: str = ""
    other_client: str | None = None       # set when the file looks like another client's
    warning: str = ""                     # the plain-language pairing message
    summary: str = ""


@dataclass
class Check:
    """The data check: one row per truck, the trucks that will be made, and the counts."""
    rows: list = field(default_factory=list)
    statuses: list = field(default_factory=list)
    jobs: list = field(default_factory=list)            # (file name, values) per truck that will be made
    unknown_borders: list = field(default_factory=list)
    notices: list = field(default_factory=list)
    trucks_found: int = 0
    skipped: int = 0
    warned: int = 0
    waiting: int = 0


class Job:
    """Everything loaded for one client. Switching client means starting a new Job."""

    def __init__(self, client_id):
        self.client = get_client(client_id)
        self.sample_name = ""
        self.template = None
        self.excel_name = ""
        self.raw_sheets = {}
        self.sheet = None
        self.header_row = 0                 # 0-based, like app.py
        self.mapping = {}
        self.results = None                 # {"files", "jobs", "date", "client"} after Generate
        # Step 3 settings, with the same defaults as app.py
        self.doc_date = date.today()
        self.freight1 = self.client.DEFAULT_FREIGHT1
        self.freight2 = self.client.DEFAULT_FREIGHT2
        self.prices = {item: float(self.client.DEFAULT_PRICES[self.price_name(item)])
                       for item in self.client.PRICE_ITEMS}
        self.source = settings.SOURCE_CLIENT if self.client.CLIENT_TONNAGE is not None else settings.SOURCE_EXCEL
        self.fixed_tonnage_input = 40.0
        self.fixed_packages_input = 40
        self.agent_choices = {}             # border -> agent chosen by the manager

    @staticmethod
    def price_name(item):
        return {"coal": "coal", "freight_1": "freight1", "freight_2": "freight2", "insurance": "insurance"}[item]

    # ---------------- Step 1: sample PDF ----------------
    def load_sample(self, name, data, confirmed_other_client=False):
        client = self.client
        kind = file_kind(data)
        if kind == "empty":
            return Step(False, "This file is empty. Choose the sample PDF again.")
        if kind in ("excel", "old excel"):
            return Step(False, "This is an Excel sheet, not the sample PDF. Use it in Step 2 (the Excel), and "
                               f"choose a finished {client.NAME} truck PDF here.")
        if kind != "pdf":
            return Step(False, f"This file is not a PDF. Choose a finished {client.NAME} truck PDF here.")
        detected = detect_client_from_pdf(data)[0]
        problem = pairing_problem(client.ID, detected, "sample PDF")
        if problem and not confirmed_other_client:
            return Step(False, other_client=detected, warning=problem)
        try:
            template = load_template(data, client)
        except LayoutError as error:
            return Step(False, str(error))
        except Exception:
            log_error("reading the sample PDF")
            return Step(False, f"This file could not be read. Check that it is a {client.NAME} sample PDF.")
        self.template, self.sample_name, self.results = template, name, None
        return Step(True, summary=f"Sample recognised: {name} · all {len(template['spots'])} fields found on "
                                  f"pages 1-3 (sample invoice {template['sample']['invoice_no']}). "
                                  "Any later pages are ignored.")

    # ---------------- Step 2: Excel ----------------
    def load_excel(self, name, data):
        client = self.client
        kind = file_kind(data)
        if kind == "empty":
            return Step(False, "This file is empty. Choose the Excel sheet again.")
        if kind == "pdf":
            return Step(False, "This is a PDF, not the Excel sheet. Use the sample PDF in Step 1, and the "
                               f"{client.NAME} loading-order Excel here.")
        if kind == "old excel":
            return Step(False, "This Excel file is in the old .xls format. Open it in Excel, choose Save As, "
                               "'Excel Workbook (.xlsx)', and choose that file.")
        if kind != "excel":
            return Step(False, f"This file is not an Excel sheet. Choose the {client.NAME} loading-order Excel here.")
        try:
            sheets = read_raw_sheets(io.BytesIO(data), "sheet.xlsx")      # the real name is never used
        except Exception:
            log_error("reading the Excel")
            return Step(False, f"This file could not be read. Check that it is the {client.NAME} Excel sheet.")
        self.excel_name, self.raw_sheets, self.results = name, sheets, None
        return self.choose_sheet(next(iter(sheets)))

    def choose_sheet(self, sheet, confirmed_other_client=False):
        """Use this sheet: find its title row and guess the columns, like app.py does."""
        client = self.client
        raw = self.raw_sheets[sheet]
        self.sheet = None                   # set only once the sheet is accepted
        self.mapping = {}
        if len(raw) < 2:
            return Step(False, "This sheet is empty. Choose another sheet or another file.")
        detected = detect_client_from_excel(raw)[0]
        problem = pairing_problem(client.ID, detected, "Excel sheet")
        if problem and not confirmed_other_client:
            return Step(False, other_client=detected, warning=problem)
        self.sheet = sheet
        try:
            self.set_header_row(detect_header_row(raw))
        except Exception:
            log_error("reading the Excel sheet")
            self.sheet = None
            return Step(False, f"This file could not be read. Check that it is the {client.NAME} Excel sheet.")
        return self.excel_step()

    def set_header_row(self, header_row):
        """The row with the column titles (0-based); the columns are guessed again."""
        self.header_row = int(header_row)
        self.mapping = dict(guess_columns(self.columns(), self.client))

    def table(self):
        return clean_sheet(self.raw_sheets[self.sheet], self.header_row)

    def columns(self):
        return list(self.table().columns)

    def missing_columns(self):
        client = self.client
        return [client.FIELDS[k][0] for k in client.FIELDS if self.mapping.get(k) is None and k not in client.OPTIONAL]

    def excel_step(self):
        """Step 2 is done when every needed column is matched."""
        missing = self.missing_columns()
        if missing:
            return Step(False, "These columns were not found: " + ", ".join(missing) + f". Check that this is the "
                               f"{self.client.NAME} Excel, or choose the columns under 'Column matching'.")
        return Step(True, summary=f"{self.excel_name} · sheet '{self.sheet}' · titles on row {self.header_row + 1} · "
                                  f"{len(self.table())} rows read")

    # ---------------- Step 3 + data check ----------------
    def quantities(self):
        """(tonnage from Excel?, packages from Excel?, fixed tonnage, fixed packages, source text)."""
        client = self.client
        if client.FIXED_TONNAGE is not None:
            # This client's figures never change (BMS: 40.00 MT and 40 packages), so there is no choice.
            return False, False, client.FIXED_TONNAGE, client.FIXED_PACKAGES, "fixed for this client"
        source = self.source
        tonnage_from_excel = source == settings.SOURCE_EXCEL
        packages_from_excel = source in (settings.SOURCE_EXCEL, settings.SOURCE_CLIENT)
        fixed_tonnage = client.CLIENT_TONNAGE if source == settings.SOURCE_CLIENT else None
        fixed_packages = None
        if source == settings.SOURCE_FIXED:
            fixed_tonnage = Decimal(f"{self.fixed_tonnage_input:.2f}")
            fixed_packages = Decimal(int(self.fixed_packages_input))
        return tonnage_from_excel, packages_from_excel, fixed_tonnage, fixed_packages, source

    def decimal_prices(self):
        return {self.price_name(item): Decimal(f"{value:.2f}") for item, value in self.prices.items()}

    def date_text(self):
        return format_date(self.doc_date)

    def agent_options(self):
        """The agents the manager may choose for an unknown border: {label: agent}."""
        return {f"{a['name']} ({a['mobile']}), as for {border.title()}": a for border, a in self.client.AGENTS.items()}

    def check(self):
        """Read and check every truck, exactly as app.py's data check does."""
        client = self.client
        table = self.table()
        trucks = read_trucks(table, self.mapping, self.header_row)
        tonnage_from_excel, packages_from_excel, fixed_tonnage, fixed_packages, _source = self.quantities()
        check_trucks(trucks, figures_from_excel=packages_from_excel, tonnage_from_excel=tonnage_from_excel)
        columns = list(table.columns)
        sn_column = next((c for c in columns if simplify(c) in ("sn", "serialno", "serialnumber")), None)
        prices, date_text = self.decimal_prices(), self.date_text()
        freight1, freight2 = self.freight1.strip(), self.freight2.strip()

        result = Check(trucks_found=len(trucks))
        result.unknown_borders = sorted({t.border for t in trucks if client.AGENTS and not t.errors
                                         and agent_for_border(t.border, client) is None})
        for truck in trucks:
            tonnage = truck.tonnage if tonnage_from_excel else fixed_tonnage
            packages = truck.packages if packages_from_excel else fixed_packages
            total = ""
            agent = agent_for_border(truck.border, client) or self.agent_choices.get(truck.border)
            if truck.errors:
                status = "SKIPPED: " + "; ".join(truck.errors)
            elif client.AGENTS and agent is None:
                status = "WAITING: confirm the clearance agent above"
            else:
                values = document_values(truck, tonnage, packages, date_text, prices, freight1, freight2, agent,
                                         client=client)
                file_name = f"{client.NAME}_" + re.sub(r"[^A-Za-z0-9._-]", "_", truck.invoice_no) + ".pdf"
                result.jobs.append((file_name, values))
                total = values["total"]
                status = "Warning: " + "; ".join(truck.warnings) if truck.warnings else "OK"
            result.statuses.append(status)
            serial = cell_text(table.iloc[truck.row - self.header_row - 2][sn_column]) if sn_column else ""
            result.rows.append({
                "Status": status, "Row": truck.row, "S/N": serial, "Invoice No.": truck.invoice_no,
                "Driver": truck.driver, "Passport": truck.passport, "Horse": truck.horse,
                "Trailer 1": truck.trailer1, "Trailer 2": truck.trailer2, "Border": truck.border,
                "Clearance agent": agent["name"] if agent else ("as in the sample" if not client.AGENTS else ""),
                "Tonnage": two_decimals(tonnage) if tonnage is not None else truck.tonnage_text,
                "Packages": str(packages) if packages is not None else truck.packages_text,
                "Invoice total": total,
            })
        result.skipped = sum(s.startswith("SKIPPED") for s in result.statuses)
        result.warned = sum(s.startswith("Warning") for s in result.statuses)
        result.waiting = sum(s.startswith("WAITING") for s in result.statuses)

        # Tell the manager when the sample shows other figures than the Excel for the same invoice.
        sample = self.template["sample"]
        sample_tonnage = Decimal(re.sub(r"[^0-9.]", "", sample["weight"]))    # "40MT" or "42" -> the number
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
                result.notices.append(f"Notice: for {truck.invoice_no} the Excel says " + " and ".join(differences) +
                                      ". The Excel figures will be used. Choose 'Fixed figures for every truck' "
                                      "above if the sample's figures are the right ones.")
        return result

    # ---------------- Step 4: generate ----------------
    def generate(self, jobs, progress=None):
        """Build one PDF per ready truck. progress(n, total, file name) is called after each one."""
        files = []
        for n, (file_name, values) in enumerate(jobs, start=1):
            files.append((file_name, build_pdf(self.template, values)))
            if progress:
                progress(n, len(jobs), file_name)
        self.results = {"files": files, "jobs": jobs, "date": self.date_text(), "client": self.client.ID}
        return self.results

    # ---------------- Inspection report (one per client, kept on this computer) ----------------
    def report_path(self):
        path = os.path.join(data_dir(), f"inspection_report_{self.client.NAME}.pdf")
        old = os.path.join(data_dir(), "inspection_report.pdf")        # saved before there were 2 clients
        if self.client.ID == "bms" and not os.path.exists(path) and os.path.exists(old):
            return old
        return path

    def report(self):
        """The saved report's bytes, or None."""
        path = self.report_path()
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    def report_info(self):
        """'Saved inspection report: 3 page(s), saved on 16 Oct 2026.' or '' when none is saved."""
        report = self.report()
        if not report:
            return ""
        _ok, pages, _message = insp.validate_report(report)
        saved_on = date.fromtimestamp(os.path.getmtime(self.report_path())).strftime("%d %b %Y")
        return f"Saved inspection report: {pages} page(s), saved on {saved_on}. It is used for every truck."

    def save_report(self, name, data):
        ok, _pages, message = insp.validate_report(data)
        if not ok:
            return Step(False, f"{name} was not saved: {message}.")
        path = os.path.join(data_dir(), f"inspection_report_{self.client.NAME}.pdf")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return Step(True)

    def remove_report(self):
        path = self.report_path()
        if os.path.exists(path):
            os.remove(path)

    def zip_with_inspection(self):
        """The ZIP: one combined PDF (documents then report) per truck."""
        report = self.report()
        reports = {values["invoice_no"]: report for _name, values in self.results["jobs"]}
        return insp.build_zip(self.results, reports, insp.MODE_COMBINED, f"{self.client.NAME}_")

    def zip_name(self):
        return f"SmartAssist_{self.client.NAME}_{self.results['date']}_with_inspection.zip"

    def combined_pdf(self, index):
        """(file name, bytes) of one truck's documents followed by the report."""
        documents = self.results["files"][index][1]
        invoice_no = self.results["jobs"][index][1]["invoice_no"]
        return (f"{self.client.NAME}_{insp.safe_name(invoice_no)}_with_inspection.pdf",
                insp.combine(documents, self.report()))

    def documents_pdf(self, index):
        """(file name, bytes) of one truck's 3 documents."""
        return self.results["files"][index]
