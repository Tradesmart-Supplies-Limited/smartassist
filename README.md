# DocuLoop: manager guide

DocuLoop makes the truck documents for you. You give it one finished PDF (the sample) and the
client's loading-order Excel. It gives back one 3-page PDF per truck: road manifest, commercial
invoice and packing list, looking exactly like the sample.

It works on this computer only. Nothing is sent to the internet, and every figure is copied from
the Excel or calculated by the program.

## Start
Double-click **start_doculoop.bat**. A black window opens, then your browser shows DocuLoop.
Keep the black window open while you work. Close it when you have finished.

## The four steps
1. **Sample PDF.** Upload the sample (for example `YS-BMS10-288.pdf`). A green message confirms
   the layout was recognised. A red message means this is not the expected sample.
2. **Loading-order Excel.** Upload the Excel. Check the sheet and the row that holds the column
   titles (normally row 5). Open "Column matching" only if a column was not recognised.
3. **Job details.**
   - Date on the documents (today unless you change it), written like `12-Oct-26`.
   - Wording of the two freight lines.
   - Prices in USD per MT: coal 70, freight line 1 88, freight line 2 140, insurance 2.
   - Quantities: normally taken from the Excel for each truck. Choose "Fixed figures for every
     truck" to give every truck the same tonnage and number of packages.
   - **Read the data check table.** "OK" trucks are ready. "Warning" trucks are made, but look at
     the reason. "SKIPPED" trucks get no PDF: correct the Excel and upload it again.
4. **Generate.** Click "Generate PDFs". Then download everything as one ZIP, or one truck at a
   time. Use the preview to look at any truck before you send it.

## How the figures are worked out
- Amount = quantity x price, rounded to cents. Total = the sum of the four amounts.
- Example for 42 MT: 2,940.00 + 3,696.00 + 5,880.00 + 84.00 = 12,600.00.
- "42T" in the Excel becomes 42.00 MT on the invoice and 42MT on the packing list.
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
Open a terminal in this folder and run:

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install streamlit pandas openpyxl pymupdf fonttools pytest
```

To check the program: `.venv\Scripts\python -m pytest`
