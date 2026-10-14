# DocuLoop

Local, offline Streamlit app for ONE client. The manager uploads a sample PDF (the finished look)
and the client's loading-order Excel. For every truck the app writes one 3-page PDF
(road manifest, commercial invoice, packing list) that looks identical to the sample.
One wrong number can delay an OGEFREM customs declaration, so correctness comes first.

## Environment
- Windows, `C:\Projects\DocuLoop`, Python 3.12 in `.venv`, 8 GB RAM, no GPU, no internet at run time.
- Allowed packages only: streamlit, pandas, openpyxl, pymupdf, fonttools, pytest. Ask before adding any other.
- Run the app: `start_doculoop.bat`. Run the tests: `.venv\Scripts\python -m pytest`.

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

The fields live in one table module (`core\layout.py`). At load time every old text must be found at its
spot, otherwise show a clear "sample does not match" error.

Things learned while building:
- The sample's own font is Inter; replaced values are written in Arial as planned.
- Arial maps "-" and the soft hyphen (and space / no-break space) to one glyph, so text read back wrong.
  `pdf_builder.py` uses an in-memory Arial copy with U+00AD and U+00A0 removed (fonttools).
- Private values (driver, passport, horse, trailers) are NOT written in `layout.py`. For those the load
  check only requires the sample to show the same value at every spot of that field.
- The Excel also has a "Trailer2 Reg" column; "N/A" or empty becomes "NIL".
- Unreadable "No. of packages" is an error too (the truck is skipped).
- Dates use a two-digit day: "05-Oct-26".

## Fields replaced
- Page 1: manifest no. and file ref (both = invoice no.), loaded date, package count, quantity "40.00 MT",
  exit border, horse, trailer 1, trailer 2 ("NIL" if none), driver, passport.
  Also the DRC clearance agent's "Contact person :" and "Mobile :" lines, chosen by exit border
  (`layout.AGENTS`: MOKAMBO = Pacafic +243 995 527 463, SAKANIA = Oscar Levite +243 997 595 381;
  "MALABAR RDC" stays). Any other border: the app asks the manager to choose the agent; until then
  those trucks wait and get no PDF. `document_values` refuses an unknown border without an agent.
- Page 2: invoice date, invoice no.; top row horse, trailer 1, driver; truck-detail row driver, horse,
  trailer 1, trailer 2; bags "40.00"; four lines (coal, freight 1, freight 2, insurance) each with
  quantity "40.00 MT", price "$70.00", amount "$2,800.00"; total. Freight wording is editable
  (defaults "Road freight outside DRC" and "Road freight inside DRC").
- Page 3: invoice date, invoice no.; top row horse, trailer 1; driver, horse, trailer 1, trailer 2;
  packages "40" right-aligned against the fixed word BAGS; net and gross weight "40MT" ("42MT", "42.5MT").

## Rules
- Prices USD/MT: coal 70, freight 1 88, freight 2 140, insurance 2 (editable in the UI).
- Amount = quantity x price with `Decimal`, `ROUND_HALF_UP`. Total = sum of the four amounts.
- Quantities come from the Excel first (tonnage parsed from "42T"). The UI also offers fixed figures for
  every truck, and a notice where the sample's figures differ from the Excel's for the same invoice no.
- Date format "12-Oct-26", English month names typed in code (no locale). Default today, editable.
- NEVER use an AI model to produce a document value. Everything is copied or calculated. No network calls.
- Validation: empty invoice no./driver/horse, unreadable tonnage, duplicate invoice no. = error (truck
  skipped); duplicate horse, empty passport/border = warning.

## Typed instructions (Step 3, optional)
- Files: `core\instructions.py` (schema, prompt, validation, truck/date lookup, limits, apply, log),
  `core\llm.py` (Ollama client; `OLLAMA_URL` and `MODEL` live only there), the box in `app.py`.
- Hard rules: orders change Step 3 settings and truck selection only, never a figure inside a document
  and never a figure for one truck. Nothing changes before Apply. The page must work without Ollama.
  No new dependencies (urllib only). Never install Ollama or download models without asking.
- Flat JSON schema sent as `format` to `/api/chat` (temperature 0, num_ctx 4096, num_predict 600,
  keep_alive 2m, timeout 120 s). Default model `llama3.2:3b`; never qwen2.5:3b (licence).
- Code, not the model, finds trucks (invoice no., invoice ending, S/N, horse, driver; unique only;
  ranges on S/N), reads dates (English month table), and checks limits.
- Typed-words check: every action needs its own words in the typed order, and every truck, number,
  date and wording must appear in it. This is what keeps unsupported orders from being applied.
- S/N is read in `app.py` (S/N column) and passed in truck refs; `core\trucks.py` is unchanged.
- Settings use session_state keys from `core\instructions.py`; Apply/Discard/Clear are on_click callbacks.
- Log: `output\instructions_log.csv` (git-ignored).
- Tests: `tests\test_instructions.py`, `tests\test_llm.py` (no Ollama), 25 cases in
  `tests\instruction_cases.json`. Never edit the cases to make the model pass.
- Benchmark (needs Ollama): `.venv\Scripts\python tests\benchmark_instructions.py`.
  On 2026-10-14: 24/25 right, 5/5 unsupported not applied, about 7 s per order (first 15-30 s).
  Known miss: "Only do <invoice>" is read as exclude by the model and refused by code.

## Streamlit notes
- No `use_container_width`. Keep results in `st.session_state`. Every download button needs a unique key.

## Layout of the code
- `core\excel_reader.py` header detection and reading; `core\trucks.py` column matching, parsing, validation.
- `core\layout.py` fields table; `core\pdf_builder.py` builds the PDFs.
- `app.py` 4 steps: sample upload + layout check, Excel upload + column matching, job details + data check,
  generate + downloads + preview.
- `tests\` pytest with invented data only. The sample-regression test is skipped if the sample is absent.

## Scope and privacy
- Work only in the project folder. `samples\` is read-only. Do not touch `.venv\`.
- `samples\` and `output\` are git-ignored. Real driver names, passports and phone numbers must never
  appear in committed files or tests.
  Exception (owner's decision, 2026-10-14): the two clearance agents' names and numbers in
  `core\layout.py` (`SAMPLE_VALUES` and `AGENTS`).
- Out of scope: multiple clients, other layouts, a local AI model, editable consignee/consignor.
- Only make changes that were asked for. Plain, readable code with short comments (the owner is a beginner).

## Stop and ask before
- Deleting any file, adding a dependency, changing a price / amount formula / the Excel-first quantity
  rule, or touching anything outside the project folder.

## Acceptance
- Regression: rebuilding the sample's own truck gives identical text on pages 1-3.
- 60 trucks in under 60 seconds, each PDF exactly 3 pages.
- Invoice total = sum of its four amounts for 40, 42 and 42.5 MT.
- No replaced text overflows its cell, including a 30-character driver name.
- pytest passes, `git status` shows no client data, `start_doculoop.bat` opens the app.
