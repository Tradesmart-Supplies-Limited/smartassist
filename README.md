# SmartAssist: manager guide

**© 2026 Tradesmart Supplies Limited. All rights reserved.** Developed by Maurille Khonde. See the LICENSE file.

SmartAssist makes the truck documents for you. You give it one finished PDF (the sample) and the
client's loading-order Excel. It gives back one 3-page PDF per truck: road manifest, commercial
invoice and packing list, looking exactly like the sample.

It works on this computer only. Nothing is sent to the internet, and every figure is copied from
the Excel or calculated by the program.

## Start
Double-click **start_smartassist.bat**. A black window opens, then your browser shows SmartAssist.
Keep the black window open while you work. Close it when you have finished.

## Desktop version (SmartAssist 2.0, a normal Windows program)
SmartAssist also exists as a desktop window: the same steps, the same checks and **exactly the same
PDFs**, without a browser. It is installed with one file and needs no Python and no internet.

**Installing it on a laptop (once):**
1. Copy `SmartAssist_Setup_2.0.exe` to the laptop (USB stick, shared folder or email link) and
   double-click it.
2. If Windows says "Windows protected your PC": click **More info → Run anyway** (the program is not
   digitally signed).
3. Tick "Put a SmartAssist icon on the desktop" if you want it, then **Next → Install → Finish**.
   No administrator password is needed.
4. Open SmartAssist and choose the BMS and GCK inspection reports once on that laptop.

**Every day:** double-click the SmartAssist icon. Choose the files with the "Choose file…" buttons;
downloads are saved with "Save ZIP" or "Documents" / "Combined", into the folder you pick
(Downloads by default). Clicking the logo starts again from the beginning.

**Updating:** run the new `SmartAssist_Setup_x.x.exe` over the old one. The saved inspection reports
stay (they are kept in `%LOCALAPPDATA%\SmartAssist`). **Removing:** Windows Settings → Apps →
SmartAssist → Uninstall.

**Making the installer (only on the PC with the project):** double-click
`packaging\build_installer.bat`. It runs the checks, packs SmartAssist with its own Python
(PyInstaller), checks the packed program and makes `dist\SmartAssist_Setup_2.0.exe` (Inno Setup 6
must be installed on that PC). To try the window without installing:
`.venv\Scripts\python desktop_app.py`.

## Start from VS Code (instead of the .bat file)
1. **File → Open Folder** → choose the SmartAssist folder.
2. **Terminal → New Terminal**.
3. Switch to SmartAssist's own Python (do this every time you open a new terminal):
   `.venv\Scripts\activate` (the line then starts with `(.venv)`)
4. Start the app: `streamlit run app.py`
5. Open the address it shows (e.g. `http://localhost:8501`). Press **Ctrl+C** in the terminal to stop.

Starting from VS Code? Run `.venv\Scripts\python brand_streamlit.py` once (and again after
reinstalling), so the browser tab shows SmartAssist's truck icon from the first moment.

Skip step 3 and `streamlit run app.py` uses the wrong Python and shows "No module named 'fontTools'".
If step 3 says "running scripts is disabled", use this instead of steps 3-4:
`.venv\Scripts\python -m streamlit run app.py`

## The screen
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
- After **Generate PDFs**: **Download everything (ZIP)**, then one truck at a time, then the preview.

## Choosing the client
At the top, choose the client: **BMS** or **GCK**. The steps then ask for that client's files
(for example "Upload the BMS sample PDF"), and the PDFs are named with the client, e.g.
`BMS_YS-BMS10-288.pdf`. Changing the client clears the loaded files (SmartAssist asks first if PDFs were
already made). Each client keeps its own rules:
- **BMS:** always 40.00 MT and 40 packages; the clearance agent follows the exit border.
- **GCK:** tonnage and packages exactly as the Excel gives them (e.g. 43T = 43.00 MT); prices 40 / 120 / 145
  (coal / freight outside DRC / freight inside DRC, no insurance line); the clearance agent stays as the
  GCK sample shows it. Upload GCK's own sample PDF and Excel, and GCK's inspection report once.

File names do not matter: SmartAssist recognises a client's files by what is inside them. If a file looks
like it belongs to the other client, SmartAssist warns you and offers to switch. If you drop an Excel in
the PDF box (or the other way round), it tells you which box to use.

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
     freight line 1 88, freight line 2 140, insurance 2.
   - Quantities: for **BMS** every truck is always **40.00 MT and 40 packages**; there is nothing
     to choose. For **GCK** you choose where the tonnage and packages come from.
   - **Read the data check table.** "OK" trucks are ready. "Warning" trucks are made, but look at
     the reason. "SKIPPED" trucks get no PDF: correct the Excel and upload it again.
4. **Generate.** Click "Generate PDFs". Then download everything as one ZIP, or one truck at a
   time. Use the preview to look at any truck before you send it.

## Inspection report (optional, uploaded once)
The inspection report is the same for every truck, so you upload it **once**:
1. In **Inspection report (optional)**, upload the report PDF. It is kept on this computer
   (`output\inspection_report.pdf`) and shown as "Saved inspection report" from then on, also after
   restarting SmartAssist.
2. Only when the client sends a new report: open **Replace it** and upload the new one.
   **Remove it** stops adding a report.
3. After **Generate PDFs** you get one **combined PDF per truck** (the 3 pages, then the report).
   **Download ZIP** gives one folder per truck; **Download per truck** offers each truck's
   documents or combined PDF.
The report itself is never changed: its pages are copied as they are.

## DRC clearance agent
The agent on the road manifest follows each truck's EXIT BORDER in the Excel:
- **Mokambo:** Contact person Pacafic, mobile +243 995 527 463
- **Sakania:** Contact person Oscar Levite, mobile +243 997 595 381

For any other border (or an empty one) SmartAssist asks you to choose the agent before it makes those
trucks' PDFs; until you choose, they show "WAITING" in the data check. The "Clearance agent" column
shows which agent each truck will get. To change an agent, edit `AGENTS` in `core\clients\bms.py`.

## How the figures are worked out
- Amount = quantity x price, rounded to cents. Total = the sum of the four amounts.
- Example for 42 MT: 2,940.00 + 3,696.00 + 5,880.00 + 84.00 = 12,600.00.
- BMS: every truck is 40.00 MT and 40 packages (40MT on the packing list), whatever the Excel says.
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
2. Put the SmartAssist folder in a short place such as `C:\SmartAssist` (not deep inside other folders).
3. Double-click **install_smartassist.bat** and wait for "SmartAssist is installed".
4. Double-click **start_smartassist.bat**.

The sample PDF and the Excel are not part of the program: bring them yourself and upload them in the app.

To check the program: `.venv\Scripts\python -m pytest`
