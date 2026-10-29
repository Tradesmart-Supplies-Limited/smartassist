# SmartAssist

(Renamed from DocuLoop on 2026-10-22, owner's request; the project folder `C:\Projects\DocuLoop`, the
GitHub repository and the Figma file keep the old name.)

Local, offline Windows desktop program (Tkinter) for this company's clients (BMS; GCK prepared, see "Clients"). The manager uploads a sample PDF (the finished look)
and the client's loading-order Excel. For every truck the app writes one 3-page PDF
(road manifest, commercial invoice, packing list) that looks identical to the sample.
One wrong number can delay an OGEFREM customs declaration, so correctness comes first.

## Environment
- Windows, `C:\Projects\DocuLoop`, Python 3.12 in `.venv`, 8 GB RAM, no GPU, no internet at run time.
- Allowed packages only: pandas, openpyxl, pymupdf, fonttools, pytest (Tkinter comes with Python).
  Ask before adding any other. Streamlit was removed on 2026-10-29 (owner's request).
  Build-only (owner's OK, 2026-10-29): pyinstaller (`requirements-build.txt`) and Inno Setup 6 (installed for the
  user via winget) make the desktop installer; neither is needed to run SmartAssist.
- Run the app: `start_smartassist.bat` (or `.venv\Scripts\python desktop_app.py`). Run the tests:
  `.venv\Scripts\python -m pytest`. Make the installer: `packaging\build_installer.bat`.

## Inputs
- `samples\` (read-only, git-ignored): the sample PDF (e.g. `YS-BMS10-288.pdf`) and the client Excel.
- Excel: one sheet, title rows above, header around row 5. Columns: unnamed number column, S/N, Driver,
  Passport No., Horse Reg, Trailer Reg, Phone, PRODUCT, Tonnage (text like "42T"), No. OF PACKAGES, ETA,
  INVOICE No., EXIT BORDER. The header row is auto-detected and the user can correct it.
- Sample PDF: page 1 ROAD MANIFEST, page 2 COMMERCIAL INVOICE, page 3 PACKING LIST.
  Pages 4-5 (inspection report) are ignored and never copied into the output.
- Red text in the sample = what changes per truck. Black invoice values follow from them.

## Method (locked, do not redesign)
The sample PDF IS the template. Never redraw lines or logos. With PyMuPDF:
1. Copy pages 1-3 into a NEW PDF with `insert_pdf` (not `doc.select()`, which keeps the page 4-5 photos).
2. Locate each per-truck value as a text span (page, old text, position).
3. Redact only that span (`fill=False`, `images=0`, `graphics=0`, tight rect).
4. Write the new text at the span's original baseline, size, bold and colour, centred on the old span
   (right-aligned where noted). Shrink the font to fit its table cell.
5. Embed `C:\Windows\Fonts\arial.ttf` / `arialbd.ttf` (fallback helv/hebo), then `subset_fonts()` in try/except.
   Each truck PDF should be well under 300 KB.

The fields live in the client's profile (`core\clients\bms.py`, moved from `core\layout.py`). Since 2026-10-14 (owner's request) ANY truck's PDF
of this format is accepted as the sample, not only YS-BMS10-288. At load time:
- each spot is found by the middle of its text (x = centre, or the right edge for "right"; y = middle
  height), so names of any length match;
- every value must fit its `bms.FORMATS` pattern (invoice no., date, "40.00 MT", "$2,800.00", ...);
  names, plates, border and wording only have to be present;
- a value repeated in several spots must be the same everywhere, and the 3 page titles must be there;
- otherwise show a clear "does not match" error listing what is wrong.
The "sample shows X MT / Y packages" notice reads those figures from the uploaded sample.
The owner replaced samples\YS-BMS10-288.pdf with an improved version on 2026-10-16 (850 KB; output
about 211 KB per truck, still under 300 KB); it passes every check and is the regression sample now.
Checked on YS-BMS10-288 to 293: all accepted, each rebuilds its own truck with identical text, and an
invented truck gives the same text whichever of them is the sample.

Things learned while building:
- The sample's own font is Inter; replaced values are written in Arial as planned.
- Arial maps "-" and the soft hyphen (and space / no-break space) to one glyph, so text read back wrong.
  `pdf_builder.py` uses an in-memory Arial copy with U+00AD and U+00A0 removed (fonttools).
- Private values (driver, passport, horse, trailers) are NOT written in `bms.py`. For those the load
  check only requires the sample to show the same value at every spot of that field.
- The Excel also has a "Trailer2 Reg" column; "N/A" or empty becomes "NIL".
- Unreadable "No. of packages" is an error too (the truck is skipped).
- Dates use a two-digit day: "05-Oct-26".

## Fields replaced
- Page 1: manifest no. and file ref (both = invoice no.), loaded date, package count, quantity "40.00 MT",
  exit border, horse, trailer 1, trailer 2 ("NIL" if none), driver, passport.
  Also the DRC clearance agent's "Contact person :" and "Mobile :" lines, chosen by exit border
  (`bms.AGENTS`: MOKAMBO = Pacafic +243 995 527 463, SAKANIA = Oscar Levite +243 997 595 381;
  "MALABAR RDC" stays). Any other border: the app asks the manager to choose the agent; until then
  those trucks wait and get no PDF. `document_values` refuses an unknown border without an agent.
- Page 2: invoice date, invoice no.; top row horse, trailer 1, driver; truck-detail row driver, horse,
  trailer 1, trailer 2; bags "40.00"; four lines (coal, freight 1, freight 2, insurance) each with
  quantity "40.00 MT", price "$70.00", amount "$2,800.00"; total. Freight wording is editable
  (defaults "Road freight outside DRC" and "Road freight inside DRC").
- Page 3: invoice date, invoice no.; top row horse, trailer 1; driver, horse, trailer 1, trailer 2;
  packages "40" right-aligned against the fixed word BAGS; net and gross weight "40MT" ("42MT", "42.5MT").

## Rules
- Prices USD/MT: coal 70, freight 1 88, freight 2 140, insurance 2. Only coal is shown and editable
  in the UI (owner's request, 2026-10-14); the other three keep their defaults and, since the
  Instructions box was removed (2026-10-15), can only be changed in `core\clients\bms.py`.
- Amount = quantity x price with `Decimal`, `ROUND_HALF_UP`. Total = sum of the four amounts.
- Quantities, BMS (owner's rule, 2026-10-16): figures NEVER change. Every BMS truck is 40.00 MT and
  40 packages (`bms.FIXED_TONNAGE`, `bms.FIXED_PACKAGES`); the app shows no quantity choice for BMS and
  does not read the Excel's tonnage or packages. GCK (FIXED_* = None) keeps the radio with all three
  choices, defaulting to "From the Excel". The sample-vs-Excel notice only appears for figures read
  from the Excel.
- Date format "12-Oct-26", English month names typed in code (no locale). Default today, editable.
- NEVER use an AI model to produce a document value. Everything is copied or calculated. No network calls.
- Validation: empty invoice no./driver/horse, unreadable tonnage, duplicate invoice no. = error (truck
  skipped); duplicate horse, empty passport/border = warning.

## Clients (since 2026-10-15, branch multi-client)
- `core\clients\bms.py` is the BMS profile: id, name, READY, PDF and Excel fingerprints, Excel FIELDS /
  OPTIONAL, PRICE_ITEMS (the client's invoice lines), PAGE_NAMES, and the fields table,
  formats, agents, client tonnage and default prices that used to be `core\layout.py`.
- GCK RULE (owner, 2026-10-15): what GCK's Excel and sample give is what is kept. Tonnage exactly as
  the Excel says (42 stays 42, 43 stays 43; no 40 MT rule, `CLIENT_TONNAGE = None`, default quantity
  source = the Excel). The person named for the border / clearance agent stays as the sample or Excel
  shows it (no AGENTS swap by border) unless the owner instructs otherwise. Nothing else is changed.
- `core\clients\gck.py` is READY since 2026-10-16, built from the real GCK sample YS-GCK03-026.pdf and
  "KITWE TO GCK LOADING ORDER.xlsx" (both in `samples\GCK\`, git-ignored; inspection report
  YS-GCK03-026-4-6.pdf installed as `output\inspection_report_GCK.pdf`). Differences from BMS: US-Letter
  pages; 3 invoice lines (coal 40, freight 1 120, freight 2 145; no insurance, `PRICE_ITEMS`); weight
  written "42" (`WEIGHT_SUFFIX = ""`); "Border of Entry" on the packing list; no invoice top row;
  `AGENTS = {}` so the agent text stays as the sample shows it (`document_values` adds agent lines only
  when `client.AGENTS`). Tests in `tests\test_clients.py` rebuild the GCK sample identically and check
  that GCK values match its Excel (43T = 43.00 MT, total 43 x 305).
- `core\clients\__init__.py`: `get_client`, `list_clients`, `detect_client_from_pdf`,
  `detect_client_from_excel` (content only, never file names), `pairing_problem`.
- Core functions take the client: `load_template(bytes, client)`, `document_values(..., client=client)`,
  `agent_for_border(border, client)`, `guess_columns(columns, client)`, `read_order(..., client)`.
- Window: client cards at the top. Switching starts a new `Job` (clears sample, Excel, results and
  settings; asks first if PDFs exist). A file recognised as another client asks: switch, use it anyway, or
  cancel. A client with READY = False shows "not set up yet".
- Names carry the client: `BMS_<invoice>.pdf`, `SmartAssist_BMS_<date>.zip`, combined
  `BMS_<invoice>_with_inspection.pdf`; the inspection report is
  kept per client as `output\inspection_report_BMS.pdf` (the older `output\inspection_report.pdf` is
  still used for BMS if present).
- Files: type is read from the first bytes, never the name; an Excel chosen as the sample (or a PDF as
  the Excel) gets a "use the other step" message; any other problem is a plain message and the
  details go to `error_log.txt` in `data_dir()`. Technical details are never shown in the window.
- BMS regression: `tests\test_bms_regression.py` compares every word and position of 4 invented trucks
  with `tests\bms_reference.json`, made with the code before the change.

## Typed instructions (REMOVED, owner's requests 2026-10-15 screen, 2026-10-20 code)
- The Ollama-based Instructions box is gone completely: `core\instructions.py`, `core\llm.py`, their tests,
  the benchmark and `instruction_cases.json` were deleted on 2026-10-20 (still in git history), together
  with the "excluded by instruction" truck status and the clients' FREIGHT_LINES / EXAMPLES.
  SmartAssist uses no AI and no Ollama. `core\settings.py` keeps the Step 3 setting names and the
  quantity-source texts (used by `core\job.py`).
- The hidden freight 1 / freight 2 / insurance prices can only be changed in the client profile.
- Checked after the removal: BMS (6 trucks) and GCK (18 trucks) from the real samples give PDFs with the
  same text as before.

## Inspection report (optional, uploaded once)
- Owner's request (2026-10-14): ONE inspection report for every truck, uploaded once and kept on disk
  at `output\inspection_report.pdf` (git-ignored) until the manager replaces or removes it. This
  replaced the earlier one-report-per-truck upload and matching.
- `core\inspection.py` (no Streamlit): `validate_report`, `combine` (3 pages then the report, pages
  copied unchanged, no font subsetting on them), `build_zip` (all PDFs directly in the ZIP, no folders since v2.1, owner 2026-10-29; modes "Documents
  only" and "Combined single PDF per truck"). `match_reports` is still there and tested, but the app
  no longer uses it.
- `core\job.py`: `save_report` / `remove_report` / `report_info`; reports live in `data_dir()` as
  `inspection_report_<CLIENT>.pdf`. The window's "Inspection report" card offers the only downloads (owner:
  no documents-only ZIP): "Save ZIP" (combined PDF per truck) and one truck's "Documents" or "Combined".
  With no saved report there is nothing to save.
- Tests: `tests\test_inspection.py`.

## Design rules (UI)
- All colours live in `assets\theme.toml`; `core\theme.py` reads them (`COLORS`, `FONT` = Segoe UI, `VERSION`).
  Never hard-code a colour anywhere else. Text contrast >= 4.5:1. The look follows the Figma design
  "DocuLoop UI" (https://www.figma.com/design/KMTzehAfWLeH1ElOeaEYoC, frame 4:2) as far as Tkinter allows
  (square cards): white top bar (Tradesmart logo, name, client / offline / version chips), blue hero with
  "Step n" + step-name tags and the tagline (no app name in it, owner's choice), Client selector cards,
  Workflow tiles, numbered step cards, upload boxes with a "Choose file…" button.
- Offline only: system fonts, the PNGs in `assets\` and emoji. Nothing downloaded at run time.
- Status is always icon + word (`STATUS` in desktop_app.py), never colour alone.
- The top-bar logo restarts SmartAssist (new Job, everything loaded is cleared; saved reports stay).
- Generate PDFs button: the logo's cerulean #4CA8DC with dark text (5.8:1).
- Window/taskbar icon `assets\favicon.png`; program icon `packaging\smartassist.ico` (made from it).
- UI changes must never change logic, figures or the PDFs: those live in `core\`.

## Desktop version 2.0 (Tkinter, owner's request 2026-10-29)
- The Tkinter window replaced the browser (Streamlit) version on 2026-10-29 (owner's request): app.py,
  core\ui.py, assets\style.css, assets\icons, .streamlit, brand_streamlit.py and tests\test_style.py were
  deleted (still in git history). The Streamlit Cloud app and the company repo's .devcontainer ran app.py
  and no longer work. `start_smartassist.bat` opens the window with pythonw.
- `core\job.py` (no screen code): the steps, rules and messages of the former app.py as a `Job` per client
  (load_sample, load_excel / choose_sheet / set_header_row / mapping, check, generate, inspection report,
  ZIP / combined). `data_dir()` = project `output\` from source, `%LOCALAPPDATA%\SmartAssist` in the .exe.
  `resource()` finds assets inside the .exe. Tests: `tests\test_job.py` (invented data).
- `desktop_app.py`: the Tkinter window only (redraws from the Job's state on every change; Step 3
  typing is checked 0.5 s after the last key; Generate runs in a thread). Colours only from
  `assets\theme.toml` via `core\theme.py` (VERSION "2.1"; keep it equal to AppVersion in installer.iss). Hidden test options: `SmartAssist.exe --check`
  (writes SmartAssist_check.txt to %TEMP%) and `--build <bms|gck> <sample> <excel> <folder>`.
- `packaging\`: `make_icon.py` (PNG-in-ICO, no Pillow), `smartassist.spec` (PyInstaller one-folder, excludes
  streamlit/pyarrow), `installer.iss` (per-user install, no admin), `build_installer.bat` (tests -> icon ->
  pack -> --check -> installer). Output `dist\` and `build\` are git-ignored.
- Checked 2026-10-29: window, packed .exe and installed program all give PDFs with the same text as the
  browser version for the real BMS (6) and GCK (18) samples; installer 42.9 MB, installed 131 MB.

## Layout of the code
- `core\excel_reader.py` header detection and reading; `core\trucks.py` column matching, parsing, validation.
- `core\clients\` one profile per client (fields table, Excel columns, defaults); `core\pdf_builder.py` builds the PDFs.
- `core\job.py` the 4 steps without screen code; `desktop_app.py` the window: sample + layout check, Excel +
  column matching, job details + data check, generate + preview, inspection report + saving.
- `packaging\` installer recipe (see "Desktop version 2.0").
- `tests\` pytest with invented data only. The sample-regression test is skipped if the sample is absent.

## Scope and privacy
- Work only in the project folder. `samples\` is read-only. Do not touch `.venv\` (except installing the
  approved packages). Streamlit is still installed in `.venv\` but no longer used.
- `samples\` and `output\` are git-ignored. Real driver names, passports and phone numbers must never
  appear in committed files or tests.
  Exception (owner's decision, 2026-10-14): the two clearance agents' names and numbers in
  `core\clients\bms.py` (`SAMPLE_VALUES` and `AGENTS`).
- Out of scope: other layouts than the clients' own, editable consignee/consignor.
- Only make changes that were asked for. Plain, readable code with short comments (the owner is a beginner).

## Stop and ask before
- Deleting any file, adding a dependency, changing a price / amount formula / the fixed BMS 40 MT / 40 packages
  rule, or touching anything outside the project folder.

## Acceptance
- Regression: rebuilding the sample's own truck gives identical text on pages 1-3.
- 60 trucks in under 60 seconds, each PDF exactly 3 pages.
- Invoice total = sum of its four amounts for 40, 42 and 42.5 MT.
- No replaced text overflows its cell, including a 30-character driver name.
- pytest passes, `git status` shows no client data, `start_smartassist.bat` opens the window, and
  `packaging\build_installer.bat` makes an installer whose program passes `--check`.
