# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""SmartAssist desktop window (Tkinter). One 3-page PDF per truck, from a client's sample PDF and Excel.

This file only draws the window. Every rule, check and figure comes from core/job.py, which uses the
same PDF builder as before, so the documents are identical. Start it with start_smartassist.bat, or
the installed SmartAssist shortcut.
"""
import base64
import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import pymupdf

from core import settings
from core.clients import get_client, list_clients
from core.job import Job, log_error, resource
from core.pdf_builder import two_decimals
from core.theme import COLORS as C, FONT, VERSION

TITLE = "SmartAssist"
TAGLINE = "Road manifest, commercial invoice and packing list from your Excel sheet"
STEP_NAMES = ["Sample PDF", "Loading-order Excel", "Job details", "Generate"]
NO_COLUMN = "(none)"
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")

# The truck states in the check table: icon + word, never colour alone.
STATUS = {"ready": "✅ Ready", "warning": "⚠️ Warning", "waiting": "⏳ Waiting", "error": "⛔ Error"}


def status_of(text):
    if text.startswith("SKIPPED"):
        return "error"
    if text.startswith("WAITING"):
        return "waiting"
    if text.startswith("Warning"):
        return "warning"
    return "ready"


def png_image(data, scale=1.0):
    """A Tk image from PNG bytes, resized with PyMuPDF (Tk alone can only resize by whole numbers)."""
    if scale != 1.0:
        pix = pymupdf.Pixmap(data)
        doc = pymupdf.open("png", data)
        data = doc[0].get_pixmap(matrix=pymupdf.Matrix(scale * pix.width / doc[0].rect.width,
                                                       scale * pix.height / doc[0].rect.height),
                                 alpha=True).tobytes("png")
    return tk.PhotoImage(data=base64.b64encode(data))


def read_file(path):
    with open(path, "rb") as f:
        return f.read()


class Scrollable(tk.Frame):
    """A frame that scrolls with the mouse wheel when the window is too small."""

    def __init__(self, master):
        super().__init__(master, bg=C["page"])
        self.canvas = tk.Canvas(self, bg=C["page"], highlightthickness=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=C["page"])
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._wheel)

    def _wheel(self, event):
        # Tables and lists scroll themselves; everything else scrolls the page.
        if isinstance(event.widget, (ttk.Treeview, tk.Listbox)) or str(event.widget).endswith("popdown.f.l"):
            return
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.geometry("1280x860")
        self.minsize(980, 640)
        self.configure(bg=C["page"])
        self._icon = tk.PhotoImage(file=resource("assets", "favicon.png"))
        self.iconphoto(True, self._icon)
        self._logo = png_image(read_file(resource("assets", "logos.png")), 0.26)
        self._styles()
        self.client_id = list_clients()[0].ID
        self.job = Job(self.client_id)
        self.check_result = None
        self.preview_images = []
        self.work = queue.Queue()
        self._refresh_after = None

        self.header = tk.Frame(self, bg=C["card"], highlightthickness=1, highlightbackground=C["border"])
        self.header.pack(fill="x")
        self.page = Scrollable(self)
        self.page.pack(fill="both", expand=True)
        self.body = tk.Frame(self.page.inner, bg=C["page"])
        self.body.pack(fill="x", padx=40, pady=(12, 24))
        self.start()

    # ---------------- look ----------------
    def _styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", font=(FONT, 10), background=C["card"], foreground=C["text"])
        s.configure("TButton", padding=(14, 6), background=C["card"], bordercolor=C["line"], lightcolor=C["card"],
                    darkcolor=C["card"], borderwidth=1, relief="solid")
        s.map("TButton", background=[("active", C["soft"])])
        s.configure("Accent.TButton", background=C["accent"], foreground="#FFFFFF", bordercolor=C["accent"],
                    font=(FONT, 10, "bold"))
        s.map("Accent.TButton", background=[("disabled", C["line"]), ("active", C["accent2"])],
              foreground=[("disabled", C["gray"])])
        s.configure("Generate.TButton", background=C["cerulean"], foreground=C["text"], bordercolor=C["cerulean"],
                    font=(FONT, 11, "bold"), padding=(14, 10))
        s.map("Generate.TButton", background=[("disabled", C["line"]), ("active", "#3B97CB")])
        s.configure("TEntry", fieldbackground=C["surface"], bordercolor=C["line"], padding=5)
        s.configure("TCombobox", fieldbackground=C["surface"], bordercolor=C["line"], padding=4)
        s.configure("TSpinbox", fieldbackground=C["surface"], bordercolor=C["line"], padding=4)
        s.configure("TRadiobutton", background=C["card"])
        s.configure("TCheckbutton", background=C["card"])
        s.configure("Treeview", rowheight=26, fieldbackground=C["card"], bordercolor=C["border"])
        s.configure("Treeview.Heading", background=C["surface"], font=(FONT, 9, "bold"), relief="flat")
        s.configure("TNotebook", background=C["card"], borderwidth=0)
        s.configure("TNotebook.Tab", padding=(12, 4))
        s.configure("Horizontal.TProgressbar", background=C["accent"], troughcolor=C["surface"])

    def label(self, parent, text, size=10, bold=False, color=None, bg=None, wrap=0, **pack):
        widget = tk.Label(parent, text=text, font=(FONT, size, "bold" if bold else "normal"),
                          fg=color or C["text"], bg=bg or parent["bg"], justify="left", anchor="w",
                          wraplength=wrap)
        if pack:
            widget.pack(**pack)
        return widget

    def card(self, title=None, number=None, done=False, summary=""):
        """A white card; with a number it is a step (a green tick and a summary when done)."""
        frame = tk.Frame(self.body, bg=C["card"], highlightthickness=1, highlightbackground=C["border"])
        frame.pack(fill="x", pady=6)
        inner = tk.Frame(frame, bg=C["card"])
        inner.pack(fill="x", padx=20, pady=16)
        if title:
            row = tk.Frame(inner, bg=C["card"])
            row.pack(fill="x")
            if number is not None:
                dot = tk.Canvas(row, width=30, height=30, bg=C["card"], highlightthickness=0)
                dot.create_oval(1, 1, 29, 29, fill=C["green"] if done else C["accent"], outline="")
                dot.create_text(15, 15, text="✓" if done else str(number), fill="#FFFFFF", font=(FONT, 11, "bold"))
                dot.pack(side="left", padx=(0, 10))
            self.label(row, title, 14, True, side="left")
            if summary:
                self.label(inner, ("✓ " if done else "") + summary, 10, color=C["gray"], wrap=1100,
                           fill="x", pady=(4, 0), padx=(40 if number is not None else 0, 0))
        return inner

    def message(self, parent, kind, text):
        """A coloured message box with an icon and a word, never colour alone."""
        colors = {"info": (C["soft"], C["accent2"], "ℹ️"), "ok": (C["green_soft"], C["green"], "✅"),
                  "warning": (C["orange_soft"], C["orange"], "⚠️"), "error": (C["red_soft"], C["red"], "⛔")}
        bg, fg, icon = colors[kind]
        box = tk.Frame(parent, bg=bg)
        box.pack(fill="x", pady=(8, 0))
        self.label(box, f"{icon}  {text}", 10, color=fg, bg=bg, wrap=1100, fill="x", padx=12, pady=8)
        return box

    # ---------------- the whole window ----------------
    def start(self, client_id=None):
        """A fresh start (also what a click on the logo does): nothing loaded."""
        if client_id:
            self.client_id = client_id
        self.job = Job(self.client_id)
        self.check_result = None
        self.generating = False
        # Forget everything typed or chosen for the previous job.
        self.vars, self.input_error, self.preview_choice = {}, "", None
        self.step1_error = self.step1_summary = self.step2_error = self.report_error = ""
        self.matching_open = tk.BooleanVar(value=False)
        self.draw()

    def draw(self):
        """Draw everything again from the job's state, like a page that only shows the steps reached."""
        for parent in (self.header, self.body):
            for child in parent.winfo_children():
                child.destroy()
        self.draw_header()
        steps_done = self.steps_done()
        self.draw_hero(steps_done)
        self.draw_clients()
        self.draw_workflow(steps_done)
        if not self.job.client.READY:
            self.message(self.card(), "info", f"{self.job.client.NAME} is not set up yet. Choose another client.")
            return
        self.draw_step1()
        if self.job.template is None:
            return self.footer(self.body)
        self.draw_step2()
        if self.job.sheet is None or self.job.missing_columns():
            return self.footer(self.body)
        self.draw_step3()
        self.check_body = tk.Frame(self.body, bg=C["page"])
        self.check_body.pack(fill="x")
        self.draw_check_and_after()

    def steps_done(self):
        job = self.job
        if job.template is None:
            return 0
        if job.sheet is None or job.missing_columns():
            return 1
        if job.results:
            return 4
        return 3 if self.inputs_ok() else 2

    def inputs_ok(self):
        return not getattr(self, "input_error", "")

    def draw_header(self):
        bar = tk.Frame(self.header, bg=C["card"])
        bar.pack(fill="x", padx=40, pady=10)
        logo = tk.Label(bar, image=self._logo, bg=C["card"], cursor="hand2", bd=1, relief="solid",
                        highlightthickness=0)
        logo.pack(side="left")
        logo.bind("<Button-1>", lambda e: self.start())          # the logo reloads SmartAssist
        tip = "Reload SmartAssist"
        logo.bind("<Enter>", lambda e: self.title(f"{TITLE} · {tip}"))
        logo.bind("<Leave>", lambda e: self.title(TITLE))
        self.label(bar, TITLE, 17, True, side="left", padx=14)
        chips = tk.Frame(bar, bg=C["card"])
        chips.pack(side="right")
        for text, bg, fg in [(f"🏢 Client: {self.job.client.NAME}", C["soft"], C["accent2"]),
                             ("🔒 Offline", C["green_soft"], C["green"]), (f"ⓘ v{VERSION}", C["surface"], C["gray"])]:
            self.label(chips, text, 9, True, color=fg, bg=bg, side="left", padx=4, ipadx=10, ipady=4)

    def draw_hero(self, steps_done):
        hero = tk.Frame(self.body, bg=C["accent"])
        hero.pack(fill="x", pady=(4, 6))
        tags = tk.Frame(hero, bg=C["accent"])
        tags.pack(fill="x", padx=24, pady=(18, 6))
        name = self.job.client.NAME
        current = [f"{name} sample PDF", f"{name} loading-order Excel", "Job details", "Generate"]
        texts = [f"Step {steps_done + 1}", current[steps_done]] if steps_done < 4 else ["✓ All steps done"]
        for text in texts:
            self.label(tags, text, 9, True, color="#FFFFFF", bg=C["accent2"], side="left", padx=(0, 8), ipadx=8, ipady=2)
        self.label(hero, TAGLINE, 12, color="#FFFFFF", bg=C["accent"], fill="x", padx=24, pady=(4, 18))

    def draw_clients(self):
        inner = self.card("Client selector")
        row = tk.Frame(inner, bg=C["card"])
        row.pack(fill="x", pady=(10, 0))
        for n, client in enumerate(list_clients()):
            chosen = client.ID == self.client_id
            box = tk.Frame(row, bg=C["soft"] if chosen else C["card"], highlightthickness=2 if chosen else 1,
                           highlightbackground=C["accent"] if chosen else C["border"], cursor="hand2")
            box.grid(row=0, column=n, sticky="nsew", padx=(0 if n == 0 else 8, 0))
            row.columnconfigure(n, weight=1, uniform="clients")
            title = self.label(box, f"{'◉' if chosen else '○'}  {client.NAME}" + ("   (selected)" if chosen else ""),
                               12, True, fill="x", padx=14, pady=(10, 2))
            text = self.label(box, client.DESCRIPTION, 10, color=C["gray"], fill="x", padx=14, pady=(0, 10))
            for widget in (box, title, text):
                widget.bind("<Button-1>", lambda e, cid=client.ID: self.choose_client(cid))

    def choose_client(self, client_id):
        if client_id == self.client_id:
            return
        if self.job.results and not messagebox.askyesno(
                TITLE, f"Switching to {get_client(client_id).NAME} clears the sample, the Excel and the PDFs already "
                       f"made for {self.job.client.NAME}. Switch?"):
            return
        self.start(client_id)

    def draw_workflow(self, steps_done):
        inner = self.card("Workflow")
        row = tk.Frame(inner, bg=C["card"])
        row.pack(fill="x", pady=(10, 0))
        for n, name in enumerate(STEP_NAMES, start=1):
            state = "done" if n <= steps_done else ("current" if n == steps_done + 1 else "todo")
            bg = C["soft"] if state == "current" else C["card"]
            tile = tk.Frame(row, bg=bg, highlightthickness=2 if state == "current" else 1,
                            highlightbackground=C["accent"] if state == "current" else C["border"])
            tile.grid(row=0, column=n - 1, sticky="nsew", padx=(0 if n == 1 else 8, 0))
            row.columnconfigure(n - 1, weight=1, uniform="steps")
            dot = tk.Canvas(tile, width=30, height=30, bg=bg, highlightthickness=0)
            fill = {"done": C["green"], "current": C["accent"], "todo": C["surface"]}[state]
            dot.create_oval(1, 1, 29, 29, fill=fill, outline=C["line"] if state == "todo" else "")
            dot.create_text(15, 15, text="✓" if state == "done" else str(n),
                            fill=C["muted"] if state == "todo" else "#FFFFFF", font=(FONT, 10, "bold"))
            dot.pack(side="left", padx=12, pady=12)
            words = tk.Frame(tile, bg=bg)
            words.pack(side="left")
            self.label(words, name, 11, True, color=C["text"] if state != "todo" else C["gray"], fill="x")
            word = {"done": "Done", "current": "Next", "todo": "Waiting"}[state]       # never colour alone
            self.label(words, word, 9, color={"done": C["green"], "current": C["accent"], "todo": C["muted"]}[state],
                       fill="x")

    # ---------------- Step 1 ----------------
    def draw_step1(self):
        job, name = self.job, self.job.client.NAME
        done = job.template is not None
        inner = self.card(f"Step 1 · {name} sample PDF", 1, done, getattr(self, "step1_summary", "") if done else "")
        self.upload_box(inner, "Choose sample PDF", f"The finished {name} truck PDF · its file name does not matter",
                        self.pick_sample, "Change" if done else "Choose file…")
        if not done:
            if getattr(self, "step1_error", ""):
                self.message(inner, "error", self.step1_error)
            else:
                self.message(inner, "info", f"Waiting for the {name} sample PDF: choose any finished {name} truck PDF.")

    def upload_box(self, parent, title, hint, command, button):
        box = tk.Frame(parent, bg=C["surface"], highlightthickness=1, highlightbackground=C["accent"])
        box.pack(fill="x", pady=(10, 0))
        self.label(box, "⬆", 16, color=C["accent"], bg=C["soft"], side="left", padx=14, pady=12, ipadx=8)
        words = tk.Frame(box, bg=C["surface"])
        words.pack(side="left", fill="x", expand=True)
        self.label(words, title, 11, True, fill="x")
        self.label(words, hint, 9, color=C["muted"], fill="x")
        ttk.Button(box, text=button, command=command).pack(side="right", padx=14)

    def pick_sample(self):
        path = filedialog.askopenfilename(title="Choose the sample PDF",
                                          filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if not path:
            return
        data = read_file(path)
        step = self.job.load_sample(os.path.basename(path), data)
        if step.other_client:
            choice = self.ask_other_client(step)
            if choice == "switch":
                self.start(step.other_client)
                step = self.job.load_sample(os.path.basename(path), data)
            elif choice == "use":
                step = self.job.load_sample(os.path.basename(path), data, confirmed_other_client=True)
            else:
                return
        self.step1_error = "" if step.ok else step.error
        self.step1_summary = step.summary
        self.draw()

    def ask_other_client(self, step):
        """The file looks like another client's: switch, use it anyway, or cancel."""
        other = get_client(step.other_client).NAME
        dialog = tk.Toplevel(self, bg=C["card"])
        dialog.title(TITLE)
        dialog.transient(self)
        dialog.grab_set()
        self.label(dialog, step.warning, 10, wrap=440, fill="x", padx=20, pady=(18, 12))
        answer = {"value": None}

        def close(value):
            answer["value"] = value
            dialog.destroy()

        row = tk.Frame(dialog, bg=C["card"])
        row.pack(fill="x", padx=20, pady=(0, 18))
        ttk.Button(row, text=f"Switch to {other}", style="Accent.TButton", command=lambda: close("switch")).pack(side="left")
        ttk.Button(row, text=f"Use it for {self.job.client.NAME} anyway", command=lambda: close("use")).pack(side="left", padx=8)
        ttk.Button(row, text="Cancel", command=lambda: close(None)).pack(side="left")
        self.wait_window(dialog)
        return answer["value"]

    # ---------------- Step 2 ----------------
    def draw_step2(self):
        job, name = self.job, self.job.client.NAME
        excel_step = job.excel_step() if job.sheet is not None else None
        done = bool(excel_step and excel_step.ok)
        inner = self.card(f"Step 2 · {name} loading-order Excel", 2, done, excel_step.summary if done else "")
        self.upload_box(inner, "Choose loading-order Excel", "The .xlsx or .xlsm sheet · its file name does not matter",
                        self.pick_excel, "Change" if job.raw_sheets else "Choose file…")
        if not job.raw_sheets:
            if getattr(self, "step2_error", ""):
                self.message(inner, "error", self.step2_error)
            else:
                self.message(inner, "info", f"Waiting for the {name} loading-order Excel.")
            return
        row = tk.Frame(inner, bg=C["card"])
        row.pack(fill="x", pady=(10, 0))
        self.label(row, "Sheet", side="left")
        sheet = ttk.Combobox(row, values=list(job.raw_sheets), state="readonly", width=30)
        sheet.set(job.sheet or "")
        sheet.pack(side="left", padx=8)
        sheet.bind("<<ComboboxSelected>>", lambda e: self.pick_sheet(sheet.get()))
        if getattr(self, "step2_error", ""):
            self.message(inner, "error", self.step2_error)
        if job.sheet is None:
            return
        # Column matching: closed unless a needed column is missing.
        missing = job.missing_columns()
        if missing:
            self.matching_open.set(True)
            self.message(inner, "error", excel_step.error)
        ttk.Checkbutton(inner, text="Column matching (open to correct it)", variable=self.matching_open,
                        command=self.draw).pack(anchor="w", pady=(10, 0))
        if self.matching_open.get():
            self.draw_matching(inner)

    def draw_matching(self, parent):
        job = self.job
        box = tk.Frame(parent, bg=C["card"])
        box.pack(fill="x", pady=(6, 0))
        top = tk.Frame(box, bg=C["card"])
        top.pack(fill="x")
        self.label(top, "Row that contains the column titles (the first row is 1)", side="left")
        rows = len(job.raw_sheets[job.sheet])
        header = ttk.Spinbox(top, from_=1, to=rows, width=6)
        header.set(job.header_row + 1)
        header.pack(side="left", padx=8)
        ttk.Button(top, text="Use this row", command=lambda: self.pick_header(header.get())).pack(side="left")
        columns = job.columns()
        self.label(box, f"{len(job.table())} rows found under the titles: {', '.join(columns)}", 9, color=C["muted"],
                   wrap=1100, fill="x", pady=(4, 6))
        grid = tk.Frame(box, bg=C["card"])
        grid.pack(fill="x")
        for n, (key, (label, _names)) in enumerate(job.client.FIELDS.items()):
            cell = tk.Frame(grid, bg=C["card"])
            cell.grid(row=n // 3, column=n % 3, sticky="ew", padx=(0, 12), pady=3)
            grid.columnconfigure(n % 3, weight=1, uniform="cols")
            self.label(cell, label, 9, color=C["gray"], fill="x")
            combo = ttk.Combobox(cell, values=[NO_COLUMN] + columns, state="readonly")
            combo.set(job.mapping.get(key) or NO_COLUMN)
            combo.pack(fill="x")
            combo.bind("<<ComboboxSelected>>", lambda e, k=key, c=combo: self.pick_column(k, c.get()))

    def pick_excel(self):
        path = filedialog.askopenfilename(title="Choose the loading-order Excel",
                                          filetypes=[("Excel files", "*.xlsx *.xlsm *.xls"), ("All files", "*.*")])
        if not path:
            return
        step = self.job.load_excel(os.path.basename(path), read_file(path))
        sheet = next(iter(self.job.raw_sheets), None)
        self.after_excel_step(step, sheet)

    def pick_sheet(self, sheet):
        self.after_excel_step(self.job.choose_sheet(sheet), sheet)

    def after_excel_step(self, step, sheet):
        """Show the result of choosing an Excel or a sheet. A 'columns not found' problem is shown by Step 2."""
        if step.other_client:
            choice = self.ask_other_client(step)
            if choice == "switch":
                self.start(step.other_client)
                return
            if choice == "use":
                step = self.job.choose_sheet(sheet, confirmed_other_client=True)
        self.step2_error = "" if (step.ok or self.job.sheet is not None or step.other_client) else step.error
        self.draw()

    def pick_header(self, text):
        try:
            row = int(text)
        except ValueError:
            return
        rows = len(self.job.raw_sheets[self.job.sheet])
        self.job.set_header_row(min(max(row, 1), rows) - 1)
        self.draw()

    def pick_column(self, key, choice):
        self.job.mapping[key] = None if choice == NO_COLUMN else choice
        self.draw()

    # ---------------- Step 3 ----------------
    def draw_step3(self):
        job = self.job
        self.input_error = self.read_inputs(store=False)
        done = not self.input_error
        prices = job.decimal_prices()
        source = job.quantities()[4]
        summary = f"Date {job.date_text()} · coal ${prices['coal']} · {source.split(' (')[0]}" if done else ""
        tiles = tk.Frame(self.body, bg=C["page"])
        tiles.pack(fill="x", pady=(6, 0))
        self.tiles = tiles
        inner = self.card("Step 3 · Job details", 3, done, summary)

        self.label(inner, "📅  Date and freight wording", 11, True, fill="x", pady=(10, 4))
        row = tk.Frame(inner, bg=C["card"])
        row.pack(fill="x")
        self.vars = getattr(self, "vars", None) or {}
        fields = [("date", "Date on the documents (DD/MM/YYYY)", job.doc_date.strftime("%d/%m/%Y")),
                  ("freight1", "Freight line 1 wording", job.freight1),
                  ("freight2", "Freight line 2 wording", job.freight2)]
        for n, (key, label, value) in enumerate(fields):
            cell = tk.Frame(row, bg=C["card"])
            cell.grid(row=0, column=n, sticky="ew", padx=(0, 12))
            row.columnconfigure(n, weight=1, uniform="job")
            self.label(cell, label, 9, color=C["gray"], fill="x")
            var = tk.StringVar(value=value)
            ttk.Entry(cell, textvariable=var).pack(fill="x")
            var.trace_add("write", lambda *a: self.inputs_changed())
            self.vars[key] = var
        self.date_hint = self.label(row, f"Will be written as {job.date_text()}", 9, color=C["muted"])
        self.date_hint.grid(row=1, column=0, sticky="w")

        self.label(inner, "💲  Coal price (USD per MT)", 11, True, fill="x", pady=(12, 4))
        var = tk.StringVar(value=f"{job.prices['coal']:.2f}")
        ttk.Entry(inner, textvariable=var, width=16).pack(anchor="w")
        var.trace_add("write", lambda *a: self.inputs_changed())
        self.vars["coal"] = var

        self.label(inner, "⚖  Quantities", 11, True, fill="x", pady=(12, 4))
        client = job.client
        if client.FIXED_TONNAGE is not None:
            self.label(inner, f"Every {client.NAME} truck: {two_decimals(client.FIXED_TONNAGE)} MT and "
                              f"{client.FIXED_PACKAGES} packages (always the same; the Excel's tonnage and packages "
                              "columns are not used).", 10, color=C["gray"], wrap=1100, fill="x")
        else:
            self.label(inner, "Where do the tonnage and number of packages come from?", 10, fill="x")
            source_var = tk.StringVar(value=job.source)
            for option in (settings.SOURCE_CLIENT, settings.SOURCE_EXCEL, settings.SOURCE_FIXED):
                ttk.Radiobutton(inner, text=option, value=option, variable=source_var,
                                command=lambda: self.set_source(source_var.get())).pack(anchor="w")
            if job.source == settings.SOURCE_CLIENT:
                self.label(inner, f"Every {client.NAME} truck is printed at {client.CLIENT_TONNAGE} MT; "
                                  "the Excel's tonnage column is not used.", 9, color=C["muted"], fill="x")
            if job.source == settings.SOURCE_FIXED:
                fixed = tk.Frame(inner, bg=C["card"])
                fixed.pack(fill="x", pady=(6, 0))
                for n, (key, label, value) in enumerate([("tonnage", "Tonnage (MT) for every truck",
                                                          f"{job.fixed_tonnage_input:.2f}"),
                                                         ("packages", "Packages for every truck",
                                                          str(job.fixed_packages_input))]):
                    cell = tk.Frame(fixed, bg=C["card"])
                    cell.grid(row=0, column=n, sticky="w", padx=(0, 16))
                    self.label(cell, label, 9, color=C["gray"], fill="x")
                    var = tk.StringVar(value=value)
                    ttk.Entry(cell, textvariable=var, width=14).pack(anchor="w")
                    var.trace_add("write", lambda *a: self.inputs_changed())
                    self.vars[key] = var
        self.step3_error = tk.Frame(inner, bg=C["card"])
        self.step3_error.pack(fill="x")
        if self.input_error:
            self.message(self.step3_error, "error", self.input_error)

    def set_source(self, source):
        self.job.source = source
        self.draw()

    def read_inputs(self, store=True):
        """Check the typed Step 3 values; store them in the job. Returns '' or a plain error message."""
        job, vars_ = self.job, getattr(self, "vars", {}) or {}
        if not vars_:
            return ""
        try:
            day = datetime.strptime(vars_["date"].get().strip(), "%d/%m/%Y").date()
        except ValueError:
            return "Type the date as day/month/year, for example 05/10/2026."
        try:
            coal = float(vars_["coal"].get().replace(",", "").strip())
            if coal < 0:
                raise ValueError
        except ValueError:
            return "Type the coal price as a number, for example 70 or 70.00."
        tonnage, packages = job.fixed_tonnage_input, job.fixed_packages_input
        if job.source == settings.SOURCE_FIXED and "tonnage" in vars_ and job.client.FIXED_TONNAGE is None:
            try:
                tonnage = float(vars_["tonnage"].get().strip())
                packages = int(vars_["packages"].get().strip())
                if tonnage < 0.01 or packages < 1:
                    raise ValueError
            except ValueError:
                return "Type the fixed tonnage (at least 0.01) and a whole number of packages (at least 1)."
        if store:
            job.doc_date, job.prices["coal"] = day, coal
            job.freight1, job.freight2 = vars_["freight1"].get(), vars_["freight2"].get()
            job.fixed_tonnage_input, job.fixed_packages_input = tonnage, packages
        return ""

    def inputs_changed(self):
        """Typing in Step 3: wait a moment, then check everything again (the typed field keeps its focus)."""
        if self._refresh_after:
            self.after_cancel(self._refresh_after)
        self._refresh_after = self.after(500, self.refresh_after_typing)

    def refresh_after_typing(self):
        self._refresh_after = None
        if self.generating:                        # wait until the PDFs are made, then check again
            self._refresh_after = self.after(300, self.refresh_after_typing)
            return
        self.input_error = self.read_inputs()
        for child in self.step3_error.winfo_children():
            child.destroy()
        if self.input_error:
            self.message(self.step3_error, "error", self.input_error)
        else:
            self.date_hint.config(text=f"Will be written as {self.job.date_text()}")
        self.draw_check_and_after()

    # ---------------- data check, Step 4, inspection report ----------------
    def draw_check_and_after(self):
        for child in self.check_body.winfo_children():
            child.destroy()
        for child in self.tiles.winfo_children():
            child.destroy()
        if self.input_error:
            return
        self.read_inputs()
        try:
            check = self.job.check()
        except Exception:
            log_error("checking the trucks")
            self.message(self.check_body, "error", "The trucks could not be read. Check the title row and the columns.")
            return
        self.check_result = check
        if not check.trucks_found:
            self.message(self.check_body, "warning", "No trucks were found in this sheet. Check the title row and the "
                                                     "column matching.")
            return
        for text, value in [("Trucks found", check.trucks_found), ("Ready", len(check.jobs))]:
            tile = tk.Frame(self.tiles, bg=C["card"], highlightthickness=1, highlightbackground=C["border"])
            tile.pack(side="left", padx=(0, 8))
            self.label(tile, text, 9, color=C["gray"], fill="x", padx=16, pady=(8, 0))
            self.label(tile, str(value), 18, True, fill="x", padx=16, pady=(0, 8))
        self.draw_check(check)
        self.draw_step4(check)
        self.draw_inspection(check)
        self.footer(self.check_body)

    def draw_check(self, check):
        old_body, self.body = self.body, self.check_body
        inner = self.card("Data check")
        self.body = old_body
        job = self.job
        if check.unknown_borders:
            self.message(inner, "warning", "Please confirm the DRC clearance agent: these exit borders have no agent on "
                                           "file. Choose one for each border, or correct the border in the Excel.")
            options = job.agent_options()
            for border in check.unknown_borders:
                row = tk.Frame(inner, bg=C["card"])
                row.pack(fill="x", pady=2)
                self.label(row, f"Clearance agent for exit border '{border or '(empty)'}'", side="left")
                combo = ttk.Combobox(row, values=["(choose the agent)"] + list(options), state="readonly", width=60)
                chosen = job.agent_choices.get(border)
                combo.set(next((k for k, a in options.items() if a is chosen), "(choose the agent)"))
                combo.pack(side="left", padx=8)
                combo.bind("<<ComboboxSelected>>", lambda e, b=border, c=combo: self.pick_agent(b, c.get()))

        columns = list(check.rows[0].keys())
        frame = tk.Frame(inner, bg=C["card"])
        frame.pack(fill="x", pady=(10, 0))
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=min(max(len(check.rows), 3), 12))
        widths = {"Status": 110, "Row": 50, "S/N": 50, "Trailer 2": 90, "Invoice total": 110}
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=widths.get(col, 120), stretch=True, anchor="w")
        for row in check.rows:
            shown = dict(row, Status=STATUS[status_of(row["Status"])])
            tree.insert("", "end", values=[shown[c] for c in columns])
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        ybar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        self.label(inner, f"{len(check.jobs)} trucks ready, {check.warned} with warnings, {check.skipped} skipped "
                          f"because of errors, {check.waiting} waiting for the clearance agent.", 10, True,
                   fill="x", pady=(8, 0))
        issues = [(row, s) for row, s in zip(check.rows, check.statuses) if s != "OK"]
        if issues:
            self.label(inner, "Points to check", 10, True, fill="x", pady=(8, 2))
            for row, s in issues:
                self.label(inner, f"• {STATUS[status_of(s)]} · row {row['Row']} · {row['Invoice No.'] or '(no invoice no.)'}"
                                  f" · {s}", 10, wrap=1100, fill="x")
        if check.skipped:
            self.message(inner, "error", "Skipped trucks get no PDF. Correct them in the Excel and choose it again.")
        for notice in check.notices:
            self.message(inner, "info", notice)

    def pick_agent(self, border, label):
        agent = self.job.agent_options().get(label)
        if agent:
            self.job.agent_choices[border] = agent
        else:
            self.job.agent_choices.pop(border, None)
        self.draw_check_and_after()

    def draw_step4(self, check):
        job = self.job
        results = job.results
        old_body, self.body = self.body, self.check_body
        summary = f"{job.client.NAME}: {len(results['files'])} PDFs made for {results['date']}" if results else ""
        inner = self.card("Step 4 · Generate", 4, bool(results), summary)
        self.body = old_body
        self.generate_button = ttk.Button(inner, text="📄  Generate PDFs", style="Generate.TButton",
                                          command=lambda: self.generate(check.jobs))
        self.generate_button.pack(fill="x", pady=(10, 0))
        if not check.jobs:
            self.generate_button.state(["disabled"])
        self.progress_area = tk.Frame(inner, bg=C["card"])
        self.progress_area.pack(fill="x")
        if not results:
            self.label(inner, "Click Generate to make one 3-page PDF per ready truck.", 9, color=C["muted"], fill="x",
                       pady=(6, 0))
            return
        if results["jobs"] != check.jobs:
            self.message(inner, "warning", "The data or settings changed after these PDFs were made. "
                                           "Click 'Generate PDFs' again to update them.")
        self.message(inner, "ok", f"{job.client.NAME}: {len(results['files'])} PDFs ready, 3 pages each · "
                                  f"{check.skipped} skipped · {check.waiting} waiting")
        self.draw_preview(inner)

    def generate(self, jobs):
        """Build the PDFs in the background, so the window keeps answering and shows the progress."""
        self.generate_button.state(["disabled"])
        self.generating = True
        bar = ttk.Progressbar(self.progress_area, maximum=len(jobs))
        bar.pack(fill="x", pady=(8, 0))
        text = self.label(self.progress_area, "Starting...", 9, color=C["muted"], fill="x")

        def work():
            try:
                self.job.generate(jobs, lambda n, total, name: self.work.put(("step", n, total, name)))
                self.work.put(("done",))
            except Exception:
                log_error("generating the PDFs")
                self.work.put(("failed",))

        def poll():
            try:
                while True:
                    item = self.work.get_nowait()
                    if item[0] == "step":
                        if bar.winfo_exists():
                            bar["value"] = item[1]
                            text.config(text=f"{item[1]} of {item[2]}: {item[3]}")
                    elif item[0] == "done":
                        self.generating = False
                        self.draw()
                        return
                    else:
                        self.generating = False
                        self.generate_button.state(["!disabled"])
                        self.message(self.progress_area, "error", "The PDFs could not be made. The details are in "
                                                                  "error_log.txt.")
                        return
            except queue.Empty:
                pass
            self.after(100, poll)

        threading.Thread(target=work, daemon=True).start()
        self.after(100, poll)

    def draw_preview(self, parent):
        files = self.job.results["files"]
        box = tk.Frame(parent, bg=C["card"], highlightthickness=1, highlightbackground=C["border"])
        box.pack(fill="x", pady=(10, 0))
        top = tk.Frame(box, bg=C["card"])
        top.pack(fill="x", padx=12, pady=8)
        self.label(top, "🔍  Preview · truck", 10, True, side="left")
        names = [name for name, _data in files]
        combo = ttk.Combobox(top, values=names, state="readonly", width=40)
        combo.set(getattr(self, "preview_choice", names[0]) if getattr(self, "preview_choice", None) in names else names[0])
        combo.pack(side="left", padx=8)
        tabs = ttk.Notebook(box)
        tabs.pack(fill="x", padx=12, pady=(0, 12))

        def show(*_):
            self.preview_choice = combo.get()
            for tab in tabs.tabs():
                tabs.forget(tab)
            self.preview_images = []
            doc = pymupdf.open(stream=dict(files)[combo.get()], filetype="pdf")
            for page, name in zip(doc, self.job.client.PAGE_NAMES):
                image = tk.PhotoImage(data=base64.b64encode(page.get_pixmap(dpi=80).tobytes("png")))
                self.preview_images.append(image)            # Tk forgets images that Python does not keep
                tabs.add(tk.Label(tabs, image=image, bg=C["card"]), text=name)

        combo.bind("<<ComboboxSelected>>", show)
        show()

    def draw_inspection(self, check):
        job = self.job
        old_body, self.body = self.body, self.check_body
        inner = self.card("Inspection report (optional)")
        self.body = old_body
        self.label(inner, "Choose the inspection report once. It is kept on this computer and added to every truck "
                          "until you replace or remove it. The report itself is never changed.", 9,
                   color=C["muted"], wrap=1100, fill="x", pady=(4, 0))
        info = job.report_info()
        if getattr(self, "report_error", ""):
            self.message(inner, "error", self.report_error)
        row = tk.Frame(inner, bg=C["card"])
        row.pack(fill="x", pady=(8, 0))
        if info:
            self.message(row, "ok", info)
            buttons = tk.Frame(inner, bg=C["card"])
            buttons.pack(fill="x", pady=(6, 0))
            ttk.Button(buttons, text="Replace it (only when the client sends a new report)",
                       command=self.pick_report).pack(side="left")
            ttk.Button(buttons, text="🗑  Remove it", command=self.remove_report).pack(side="left", padx=8)
        else:
            self.upload_box(row, "Choose inspection report", "PDF · used for every truck", self.pick_report,
                            "Choose file…")
            return
        if not job.results:
            self.message(inner, "info", "Click 'Generate PDFs' above to get the downloads with the inspection report.")
            return
        self.label(inner, "You get: Combined single PDF per truck (documents then report).", 9, color=C["muted"],
                   fill="x", pady=(10, 4))
        ttk.Button(inner, text="⬇  Save ZIP: combined PDF per truck", style="Accent.TButton",
                   command=self.save_zip).pack(anchor="w")
        self.label(inner, "Save one truck (documents or combined)", 10, True, fill="x", pady=(12, 4))
        one = tk.Frame(inner, bg=C["card"])
        one.pack(fill="x")
        labels = [f"{values['invoice_no']} · {values['driver']}" for _name, values in job.results["jobs"]]
        combo = ttk.Combobox(one, values=labels, state="readonly", width=50)
        combo.set(labels[0])
        combo.pack(side="left")
        ttk.Button(one, text="Documents", command=lambda: self.save_one(labels.index(combo.get()), False)).pack(
            side="left", padx=8)
        ttk.Button(one, text="Combined", command=lambda: self.save_one(labels.index(combo.get()), True)).pack(side="left")

    def pick_report(self):
        path = filedialog.askopenfilename(title="Choose the inspection report",
                                          filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if not path:
            return
        step = self.job.save_report(os.path.basename(path), read_file(path))
        self.report_error = "" if step.ok else step.error
        self.draw()

    def remove_report(self):
        if messagebox.askyesno(TITLE, f"Stop using the saved {self.job.client.NAME} inspection report?"):
            self.job.remove_report()
            self.draw()

    def save_as(self, name, data, kind):
        path = filedialog.asksaveasfilename(title="Save", initialdir=DOWNLOADS, initialfile=name,
                                            defaultextension=os.path.splitext(name)[1], filetypes=[kind])
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(data)
        except OSError:
            log_error("saving a file")
            messagebox.showerror(TITLE, "The file could not be saved there. Choose another folder.")
            return
        messagebox.showinfo(TITLE, f"Saved: {path}")

    def save_zip(self):
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            data = self.job.zip_with_inspection()
        finally:
            self.config(cursor="")
        self.save_as(self.job.zip_name(), data, ("ZIP files", "*.zip"))

    def save_one(self, index, combined):
        name, data = self.job.combined_pdf(index) if combined else self.job.documents_pdf(index)
        self.save_as(name, data, ("PDF files", "*.pdf"))

    def footer(self, parent):
        self.label(parent,
                   f"© 2026 Tradesmart Supplies Limited. All rights reserved.\nDeveloped by Tradesmart Supplies Limited · "
                   f"{TITLE} v{VERSION} · Works within the Tradesmart Supplies Limited Network", 9, color=C["gray"],
                   pady=(16, 0)).configure(justify="center", anchor="center")


def self_check():
    """SmartAssist.exe --check: proves the packed program can read Excel, use Arial and write PDFs.

    The answer goes to SmartAssist_check.txt in the user's temporary folder (the window is not opened).
    """
    import io
    import sys
    import tempfile
    import pandas as pd
    from core.excel_reader import read_raw_sheets
    from core.pdf_builder import FONTS
    lines = []
    try:
        buffer = io.BytesIO()
        pd.DataFrame([["Driver", "Horse Reg"], ["TEST DRIVER", "AAA111ZM"]]).to_excel(buffer, header=False, index=False)
        sheet = next(iter(read_raw_sheets(io.BytesIO(buffer.getvalue()), "check.xlsx").values()))
        lines.append(f"Excel: OK ({sheet.iloc[1, 0]})")
        lines.append(f"Fonts: {'Arial' if all(f['data'] for f in FONTS.values()) else 'built-in fallback'}")
        doc = pymupdf.open()
        doc.new_page().insert_text((50, 50), "SmartAssist check")
        lines.append(f"PDF: OK ({len(doc.tobytes())} bytes)")
        lines.append("RESULT: OK")
    except Exception as error:
        lines.append(f"RESULT: FAILED ({error!r})")
    with open(os.path.join(tempfile.gettempdir(), "SmartAssist_check.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    sys.exit(0 if lines[-1] == "RESULT: OK" else 1)


def build_from_files(client_id, sample_path, excel_path, out_dir):
    """SmartAssist.exe --build <bms|gck> <sample.pdf> <excel.xlsx> <folder>: makes the PDFs without the window.

    Used to check that the installed program gives exactly the same documents. Uses today's date.
    """
    import sys
    job = Job(client_id)
    steps = [job.load_sample(os.path.basename(sample_path), read_file(sample_path)),
             job.load_excel(os.path.basename(excel_path), read_file(excel_path))]
    if not all(step.ok for step in steps):
        sys.exit(1)
    os.makedirs(out_dir, exist_ok=True)
    for name, data in job.generate(job.check().jobs)["files"]:
        with open(os.path.join(out_dir, name), "wb") as f:
            f.write(data)
    sys.exit(0)


def main():
    import sys
    if "--check" in sys.argv:
        self_check()
    if len(sys.argv) == 6 and sys.argv[1] == "--build":
        build_from_files(*sys.argv[2:])
    App().mainloop()


if __name__ == "__main__":
    main()
