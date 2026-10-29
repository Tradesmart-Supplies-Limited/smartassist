# SmartAssist: manager guide

**© 2026 Tradesmart Supplies Limited. All rights reserved.** Developed by Maurille Khonde. See the LICENSE file.

SmartAssist makes the truck documents for you. You give it one finished PDF (the sample) and the
client's loading-order Excel. It gives back one 3-page PDF per truck: road manifest, commercial
invoice and packing list, looking exactly like the sample.

SmartAssist is a normal Windows program (a desktop window). It works on this computer only. Nothing
is sent to the internet, and every figure is copied from the Excel or calculated by the program.

## Installing it on a laptop (once)
1. Copy the installer (for example `SmartAssist_Setup_2.2.exe`) to the laptop (shared folder, USB stick or a private link) and
   double-click it.
2. If Windows says "Windows protected your PC": click **More info → Run anyway** (the program is not
   digitally signed).
3. Tick "Put a SmartAssist icon on the desktop" if you want it, then **Next → Install → Finish**.
   No administrator password, no Python and no internet are needed.
4. Open SmartAssist and choose the BMS and GCK inspection reports once on that laptop.

**Updating:** run the new `SmartAssist_Setup_x.x.exe` over the old one. The saved inspection reports
stay (they are kept in `%LOCALAPPDATA%\SmartAssist`). **Removing:** Windows Settings → Apps →
SmartAssist → Uninstall.

## Start
Double-click the **SmartAssist** icon (desktop or Start menu). On the PC with the project folder you
can also double-click **start_smartassist.bat**. Clicking the logo at the top left starts again from
the beginning (everything loaded is cleared; the saved inspection reports stay).

## The window
- The white bar at the top shows the active client, that SmartAssist works offline, and the version.
  The blue band under it tells you which step you are on.
- Under it, choose the client (BMS or GCK) in "Client selector"; each shows a one-line reminder of its rules.
- The "Workflow" card shows where you are: Sample PDF, Loading-order Excel, Job details,
  Generate. Done steps get a green tick; the next step is outlined in blue.
- Each step is a card with a number. When a step is done, the number turns into a green tick and a
  one-line summary tells you what was used (file, sheet, date, prices).
- The two tiles above Step 3 show how many trucks were found and how many are ready.
- In the data check, every truck has a status with an icon and a word: ✅ Ready, ⚠️ Warning,
  ⏳ Waiting (choose the clearance agent), ⛔ Error (no PDF).
  "Points to check" under the table lists the reasons.
- After **Generate PDFs**: the preview, then the downloads in "Inspection report".

## Choosing the client
At the top, choose the client: **BMS** or **GCK**. The steps then ask for that client's files,
and the PDFs are named with the client, e.g. `BMS_YS-BMS10-288.pdf`. Changing the client clears the
loaded files (SmartAssist asks first if PDFs were already made). Each client keeps its own rules:
- **BMS:** always 40.00 MT and 40 packages. The **prices** and the **DRC clearance agent** are taken from the
  BMS sample you choose (for example coal $65, freight $83 / $140, insurance $2, agent Cargo Congo /
  Benjamin). Both BMS looks are accepted: the older A4 one and the newer US-Letter one; the PDFs always copy
  the look of the sample you chose.
- **GCK:** tonnage and packages exactly as the Excel gives them (e.g. 43T = 43.00 MT); prices 40 / 120 / 145
  (coal / freight outside DRC / freight inside DRC, no insurance line); the clearance agent stays as the
  GCK sample shows it. Use GCK's own sample PDF and Excel, and GCK's inspection report.

File names do not matter: SmartAssist recognises a client's files by what is inside them. If a file looks
like it belongs to the other client, SmartAssist asks whether to switch, to use it anyway, or to cancel.
If you choose an Excel as the sample PDF (or the other way round), it tells you which step to use.

## The four steps
1. **Sample PDF.** Click "Choose file…" and pick any finished truck PDF in this client's format
   (for example `YS-BMS10-288.pdf`). A green tick confirms the layout was recognised. A red message
   lists what does not match (for example a missing title or a value in the wrong place).
2. **Loading-order Excel.** Choose the Excel and check the sheet. The row with the column titles is
   found automatically; "Column matching" opens by itself only if a column was not recognised.
3. **Job details.**
   - Date on the documents (today unless you change it), typed as day/month/year and written like `12-Oct-26`.
   - Wording of the two freight lines.
   - Coal price in USD per MT. **BMS:** the four prices are read from the sample (Step 1 says which);
     only coal is shown and you may change it. **GCK:** coal 40, freight 120 and 145 (fixed).
   - Quantities: for **BMS** every truck is always **40.00 MT and 40 packages**; there is nothing
     to choose. For **GCK** you choose where the tonnage and packages come from.
   - **Read the data check table.** "Ready" trucks are made. "Warning" trucks are made, but look at
     the reason. "Error" trucks get no PDF: correct the Excel and choose it again.
4. **Generate.** Click "Generate PDFs" and wait for the bar to finish. Use the preview to look at any
   truck's three pages before you send them.

## Inspection report and saving the PDFs
The inspection report is the same for every truck, so you choose it **once**:
1. In **Inspection report (optional)**, choose the report PDF. It is kept on this computer and shown as
   "Saved inspection report" from then on, also after closing SmartAssist.
2. Only when the client sends a new report: click **Replace it** and choose the new one.
   **Remove it** stops adding a report.
3. After **Generate PDFs**: **Save ZIP** gives one ZIP with one combined PDF per truck (the 3 pages,
   then the report), all directly in the ZIP with no folders, e.g. `BMS_YS-BMS10-288_with_inspection.pdf`.
   **Save one truck** gives one truck's **Documents** (3 pages) or **Combined** PDF.
   You pick the folder; Downloads is suggested.
The report itself is never changed: its pages are copied as they are. Without a saved report there is
nothing to save, so keep each client's report saved.

## DRC clearance agent
The agent on the road manifest (company, contact person and mobile) is copied **exactly as the sample
shows it**, for every truck and every border. To change the agent, choose a sample that shows the new
agent. (Until October 2026 BMS chose the agent by exit border; that rule was replaced on the owner's
request.)

## How the figures are worked out
- Amount = quantity x price, rounded to cents. Total = the sum of the four amounts.
- Example for 40 MT at the sample's prices 65 / 83 / 140 / 2: 2,600.00 + 3,320.00 + 5,600.00 + 80.00 = 11,600.00.
- BMS: every truck is 40.00 MT and 40 packages (40MT on the packing list), whatever the Excel says.
- An empty or "N/A" second trailer is written as NIL.

## What stops a truck (errors)
Empty invoice number, driver or horse; tonnage or number of packages that cannot be read; the same
invoice number used twice.

## What only warns
The same horse used twice; empty passport number; empty exit border.

## If something goes wrong
- **Red message at step 1:** the PDF is not a sample in this client's format (for BMS: neither the
  A4 look nor the US-Letter look). The message lists what did not match.
- **Changed a setting after generating:** click "Generate PDFs" again; a yellow message reminds you.
- **Something failed with no clear reason:** the details are in `error_log.txt`, in
  `%LOCALAPPDATA%\SmartAssist` (installed program) or in `output\` (project folder).

## For the person who maintains SmartAssist (project folder)
**First-time setup (once, needs internet):**
1. Install Python 3.12 from https://www.python.org/downloads/ and tick "Add python.exe to PATH"
   (keep "tcl/tk and IDLE" ticked: the window needs it).
2. Put the SmartAssist folder in a short place such as `C:\SmartAssist` (not deep inside other folders).
3. Double-click **install_smartassist.bat** and wait for "SmartAssist is installed".
4. Double-click **start_smartassist.bat**, or run `.venv\Scripts\python desktop_app.py`.

**Checks:** `.venv\Scripts\python -m pytest`

**Making the installer:** double-click `packaging\build_installer.bat`. It runs the checks, packs
SmartAssist with its own Python (PyInstaller), checks the packed program and makes
`dist\SmartAssist_Setup_<version>.exe`. Needs, on that PC only: `.venv\Scripts\python -m pip install -r
requirements-build.txt` and Inno Setup 6 (`winget install --id JRSoftware.InnoSetup --scope user`).

The sample PDF and the Excel are not part of the program: bring them yourself and choose them in the window.
