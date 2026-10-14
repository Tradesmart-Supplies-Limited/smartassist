# DocuLoop: manager guide

DocuLoop makes the truck documents for you. You give it one finished PDF (the sample) and the
client's loading-order Excel. It gives back one 3-page PDF per truck: road manifest, commercial
invoice and packing list, looking exactly like the sample.

It works on this computer only. Nothing is sent to the internet, and every figure is copied from
the Excel or calculated by the program.

## Start
Double-click **start_doculoop.bat**. A black window opens, then your browser shows DocuLoop.
Keep the black window open while you work. Close it when you have finished.

## Start from VS Code (instead of the .bat file)
1. **File → Open Folder** → choose the DocuLoop folder.
2. **Terminal → New Terminal**.
3. Switch to DocuLoop's own Python (do this every time you open a new terminal):
   `.venv\Scripts\activate` (the line then starts with `(.venv)`)
4. Start the app: `streamlit run app.py`
5. Open the address it shows (e.g. `http://localhost:8501`). Press **Ctrl+C** in the terminal to stop.

Skip step 3 and `streamlit run app.py` uses the wrong Python and shows "No module named 'fontTools'".
If step 3 says "running scripts is disabled", use this instead of steps 3-4:
`.venv\Scripts\python -m streamlit run app.py`

## The screen
- The navy band at the top shows whether the instruction assistant is **ready** or **offline**.
- Each step is a card with a number. When a step is done, the number turns into a green tick and a
  one-line summary tells you what was used (file, sheet, date, prices).
- The two tiles above Step 3 show how many trucks were found and how many are ready.
- In the data check, every truck has a status with an icon and a word: ✅ Ready, ⚠️ Warning,
  ⏳ Waiting (choose the clearance agent), ⛔ Error (no PDF), ➖ Excluded (by an instruction).
  "Points to check" under the table lists the reasons.
- The instruction box has an example button ("Coal price is 75") that fills the box for you.
- After **Generate PDFs**: **Download everything (ZIP)**, then one truck at a time, then the preview.

## The four steps
1. **Sample PDF.** Upload any finished truck PDF in this client's format (for example
   `YS-BMS10-288.pdf` or `YS-BMS10-291.pdf`). A green tick confirms the layout was recognised. A red
   message lists what does not match (for example a missing title or a value in the wrong place).
2. **Loading-order Excel.** Upload the Excel and check the sheet. The row with the column titles is
   found automatically; "Column matching" opens by itself only if a column was not recognised.
3. **Job details.**
   - Date on the documents (today unless you change it), written like `12-Oct-26`.
   - Wording of the two freight lines.
   - Coal price in USD per MT (70 unless you change it). The other prices are fixed and not shown:
     freight line 1 88, freight line 2 140, insurance 2 (a typed instruction can still change them).
   - Quantities: by default every truck is printed at **40 MT**, with the number of packages from
     the Excel (this client's rule). You can switch to "From the Excel" (each truck's own tonnage
     and packages) or "Fixed figures for every truck" (the same tonnage and packages for all).
   - **Read the data check table.** "OK" trucks are ready. "Warning" trucks are made, but look at
     the reason. "SKIPPED" trucks get no PDF: correct the Excel and upload it again.
4. **Generate.** Click "Generate PDFs". Then download everything as one ZIP, or one truck at a
   time. Use the preview to look at any truck before you send it.

## Inspection report (optional, uploaded once)
The inspection report is the same for every truck, so you upload it **once**:
1. In **Inspection report (optional)**, upload the report PDF. It is kept on this computer
   (`output\inspection_report.pdf`) and shown as "Saved inspection report" from then on, also after
   restarting DocuLoop.
2. Only when the client sends a new report: open **Replace it** and upload the new one.
   **Remove it** stops adding a report.
3. After **Generate PDFs**, choose **What to include**: documents only, or one combined PDF per truck
   (the 3 pages, then the report). **Download ZIP** gives one folder per truck; **Download per truck**
   offers each truck's documents or combined PDF.
The report itself is never changed: its pages are copied as they are.

## DRC clearance agent
The agent on the road manifest follows each truck's EXIT BORDER in the Excel:
- **Mokambo:** Contact person Pacafic, mobile +243 995 527 463
- **Sakania:** Contact person Oscar Levite, mobile +243 997 595 381

For any other border (or an empty one) DocuLoop asks you to choose the agent before it makes those
trucks' PDFs; until you choose, they show "WAITING" in the data check. The "Clearance agent" column
shows which agent each truck will get. To change an agent, edit `AGENTS` in `core\layout.py`.

## Typed instructions (optional)
In Step 3 you can type an order in plain English instead of changing the settings by hand.
Click **Read instruction**, check the **Understood as** list (every truck is shown with its invoice
number and driver), then click **Apply**, or **Discard** to change nothing.
Nothing changes before Apply. Orders add up; **Clear all instructions** returns to the default settings.

An order can only change these settings, never a figure inside a document:
which trucks to make (skip some, or only some), the date, the four prices, the wording of the two
freight lines, and fixed tonnage and packages for **every** truck (or back to the Excel figures).
Anything else appears under **Not done**.

Examples that work:
1. `Skip truck 3` (by S/N, invoice no. ending, full invoice no., horse or driver name)
2. `Don't make the documents for 288`
3. `Leave out the truck driven by Grace Zulu`
4. `Exclude trucks 1 to 3` (ranges use the S/N column)
5. `Only make trucks 5 to 8`
6. `Set the date to 15 October` (also `tomorrow`, `yesterday`, `2026-10-20`)
7. `Coal price is 75 dollars`
8. `Freight inside DRC is now 150`
9. `Call freight line 1 'Road freight Kitwe to Kasumbalesa'`
10. `Use 40 tonnes and 40 bags for every truck` (and `Go back to the Excel quantities`)

Not possible on purpose: changing one truck's weight, total or any single figure; consignee or
consignor; deleting or sending files. Limits: prices above 0 and up to 1,000; tonnage above 0 and
up to 100; packages 1 to 1,000; freight wording up to 60 characters.
Every order is recorded in `output\instructions_log.csv`.

The first order after starting can take 15-30 seconds while the model loads; later ones about 7 seconds.

### Setting up the instruction reader (once, needs internet)
The reader is a free program, **Ollama**, that runs a small language model on this computer.
Without it DocuLoop works normally; the box just says the reader is not available.
1. Install Ollama from https://ollama.com/download and start it.
2. In a terminal run: `ollama pull llama3.2:3b` (about 2 GB).
3. Restart DocuLoop. Step 3 shows "Instruction reader ready".

To use another model, change `MODEL = "llama3.2:3b"` at the top of `core\llm.py`, pull that model,
and run `.venv\Scripts\python tests\benchmark_instructions.py` to check it still reads the 25 test
orders correctly. **Check the model's licence before company use.** Llama 3.2 comes with the Llama 3.2
Community License and its acceptable use policy; do not use qwen2.5:3b, whose licence limits
commercial use.

## How the figures are worked out
- Amount = quantity x price, rounded to cents. Total = the sum of the four amounts.
- Example for 42 MT: 2,940.00 + 3,696.00 + 5,880.00 + 84.00 = 12,600.00.
- By default the tonnage is 40 MT for every truck. With "From the Excel", "42T" in the Excel
  becomes 42.00 MT on the invoice and 42MT on the packing list.
- An empty or "N/A" second trailer is written as NIL.

## What stops a truck (errors)
Empty invoice number, driver or horse; tonnage or number of packages that cannot be read; the same
invoice number used twice.

## What only warns
The same horse used twice; empty passport number; empty exit border.

## If something goes wrong
- **The browser does not open:** look in the black window for the line with `http://localhost:` and
  type that address in the browser's address bar.
- **Red message at step 1:** the PDF is not the sample this program was built for.
- **Changed a setting after generating:** click "Generate PDFs" again; a yellow message reminds you.

## First-time setup (once, needs internet)
1. Install Python 3.12 from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
2. Put the DocuLoop folder in a short place such as `C:\DocuLoop` (not deep inside other folders).
3. Double-click **install_doculoop.bat** and wait for "DocuLoop is installed".
4. Double-click **start_doculoop.bat**.

The sample PDF and the Excel are not part of the program: bring them yourself and upload them in the app.

To check the program: `.venv\Scripts\python -m pytest`
