# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""The step-by-step job behind the desktop window, with invented data only."""
import io
import zipfile
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from conftest import make_pretend_sample
from core import job as job_module
from core import settings
from core.job import Job, file_kind
from core.pdf_builder import pymupdf

TITLES = ["", "S/N", "Driver", "Passport No.", "Horse Reg", "Trailer Reg", "Trailer2 Reg", "Tonnage",
          "No. OF PACKAGES", "INVOICE No.", "EXIT BORDER"]


def excel(rows, titles=TITLES, heading="KITWE TO BMS COAL LOADING ORDER"):
    """An invented loading order: a title line, empty lines, then the column titles and the trucks."""
    lines = [[heading] + [""] * (len(titles) - 1), [""] * len(titles),
             [""] * len(titles), [""] * len(titles), titles] + rows
    buffer = io.BytesIO()
    pd.DataFrame(lines).to_excel(buffer, header=False, index=False)
    return buffer.getvalue()


def truck(n, border="MOKAMBO", tonnage="42T", packages="42"):
    return ["", n, f"DRIVER {n}", f"XX00000{n}", f"AAA{n}11ZM", f"BBB{n}22ZM", "N/A", tonnage, packages,
            f"YS-TEST-{n:03d}", border]


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Inspection reports and the error log go to a temporary folder, never to output/."""
    monkeypatch.setattr(job_module, "data_dir", lambda: str(tmp_path))
    return tmp_path


def ready_job(rows=None):
    job = Job("bms")
    assert job.load_sample("sample.pdf", make_pretend_sample()).ok
    step = job.load_excel("order.xlsx", excel(rows or [truck(1), truck(2)]))
    assert step.ok, step.error
    return job


def test_file_kind_reads_the_first_bytes_not_the_name():
    assert file_kind(b"") == "empty"
    assert file_kind(b"%PDF-1.7 ...") == "pdf"
    assert file_kind(b"PK\x03\x04...") == "excel"
    assert file_kind(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1...") == "old excel"
    assert file_kind(b"hello") == "other"


def test_wrong_files_get_plain_messages():
    job = Job("bms")
    assert "Excel sheet, not the sample PDF" in job.load_sample("a.pdf", excel([truck(1)])).error
    assert "empty" in job.load_sample("a.pdf", b"").error
    assert "not a PDF" in job.load_sample("a.pdf", b"hello").error
    assert "PDF, not the Excel" in job.load_excel("a.xlsx", make_pretend_sample()).error
    assert "old .xls format" in job.load_excel("a.xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1rest").error
    assert job.template is None and job.sheet is None


def test_sample_and_excel_are_recognised():
    job = ready_job()
    assert job.header_row == 4                         # titles on row 5
    assert job.excel_step().summary.endswith("titles on row 5 · 2 rows read")
    assert not job.missing_columns()


def test_missing_column_is_reported_and_can_be_matched_by_hand():
    titles = [t if t != "Driver" else "Chauffeur" for t in TITLES]
    job = Job("bms")
    job.load_sample("sample.pdf", make_pretend_sample())
    step = job.load_excel("order.xlsx", excel([truck(1)], titles))
    assert not step.ok and "Driver" in step.error
    job.mapping["driver"] = "Chauffeur"
    assert job.excel_step().ok


def test_bms_is_always_40_mt_and_40_packages_whatever_the_excel_says():
    job = ready_job([truck(1, tonnage="42T", packages="45")])
    check = job.check()
    values = check.jobs[0][1]
    assert check.rows[0]["Tonnage"] == "40.00" and check.rows[0]["Packages"] == "40"
    assert values["total"] == f"${(Decimal(40) * (70 + 88 + 140 + 2)):,.2f}"


def test_gck_figures_come_from_the_excel_or_are_fixed():
    job = Job("gck")
    job.template = ready_job().template                 # GCK rules, an invented BMS-shaped sample
    assert job.load_excel("order.xlsx", excel([truck(1, tonnage="43T", packages="43")],
                                              heading="KITWE TO GCK LOADING ORDER")).ok
    assert job.source == settings.SOURCE_EXCEL
    assert job.check().rows[0]["Tonnage"] == "43.00"
    job.source, job.fixed_tonnage_input, job.fixed_packages_input = settings.SOURCE_FIXED, 41.5, 30
    row = job.check().rows[0]
    assert (row["Tonnage"], row["Packages"]) == ("41.50", "30")


def test_unknown_border_waits_until_an_agent_is_chosen():
    job = ready_job([truck(1), truck(2, border="KASUMBALESA")])
    check = job.check()
    assert check.unknown_borders == ["KASUMBALESA"] and check.waiting == 1 and len(check.jobs) == 1
    job.agent_choices["KASUMBALESA"] = next(iter(job.agent_options().values()))
    assert len(job.check().jobs) == 2


def test_truck_with_errors_is_skipped():
    bad = truck(2)
    bad[2] = ""                                         # no driver
    check = ready_job([truck(1), bad]).check()
    assert check.skipped == 1 and len(check.jobs) == 1 and check.statuses[1].startswith("SKIPPED")


def test_settings_reach_the_documents():
    job = ready_job()
    job.doc_date, job.prices["coal"], job.freight1 = date(2026, 10, 5), 75.0, "Road freight Zambia"
    values = job.check().jobs[0][1]
    assert values["date"] == "05-Oct-26"
    assert "$75.00" in values.values() and "Road freight Zambia" in values.values()


def test_generate_makes_one_3_page_pdf_per_ready_truck():
    job = ready_job()
    results = job.generate(job.check().jobs)
    assert [name for name, _ in results["files"]] == ["BMS_YS-TEST-001.pdf", "BMS_YS-TEST-002.pdf"]
    assert all(pymupdf.open(stream=data, filetype="pdf").page_count == 3 for _, data in results["files"])


def test_inspection_report_is_kept_replaced_and_removed(data_dir):
    job = ready_job()
    assert job.report() is None and job.report_info() == ""
    assert not job.save_report("bad.pdf", b"not a pdf").ok
    report = pymupdf.open()
    report.new_page()
    report.new_page()
    assert job.save_report("report.pdf", report.tobytes()).ok
    assert (data_dir / "inspection_report_BMS.pdf").exists()
    assert job.report_info().startswith("Saved inspection report: 2 page(s)")
    job.generate(job.check().jobs)
    name, combined = job.combined_pdf(0)
    assert name == "BMS_YS-TEST-001_with_inspection.pdf"
    assert pymupdf.open(stream=combined, filetype="pdf").page_count == 5     # 3 documents + 2 report pages
    assert job.zip_name().startswith("SmartAssist_BMS_") and job.zip_with_inspection()[:2] == b"PK"
    names = zipfile.ZipFile(io.BytesIO(job.zip_with_inspection())).namelist()
    assert names == ["BMS_YS-TEST-001_with_inspection.pdf", "BMS_YS-TEST-002_with_inspection.pdf"]   # no folders
    job.remove_report()
    assert job.report() is None


def test_excel_of_another_client_asks_first():
    job = Job("gck")
    step = job.load_excel("order.xlsx", excel([truck(1)]))          # its title says BMS
    assert not step.ok and step.other_client == "bms" and "looks like a BMS file" in step.warning
    assert job.sheet is None                                         # nothing is used before the manager answers
    assert job.choose_sheet(next(iter(job.raw_sheets)), confirmed_other_client=True).ok
