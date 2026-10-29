# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
# PyInstaller recipe: packs desktop_app.py with its own Python into dist\SmartAssist\SmartAssist.exe.
# Run it with packaging\build_installer.bat (never needed to use SmartAssist, only to make the installer).
import os

PROJECT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(PROJECT, "desktop_app.py")],
    pathex=[PROJECT],
    datas=[
        (os.path.join(PROJECT, "assets", "logos.png"), "assets"),
        (os.path.join(PROJECT, "assets", "favicon.png"), "assets"),
        (os.path.join(PROJECT, "assets", "theme.toml"), "assets"),
    ],
    hiddenimports=["openpyxl"],            # pandas opens .xlsx files with openpyxl, found only at run time
    # Not needed by the window (Streamlit may still be installed in .venv) nor the big optional extras of pandas.
    excludes=["streamlit", "pyarrow", "altair", "pydeck", "matplotlib", "IPython", "pytest", "scipy",
              "tornado", "watchdog", "git", "jinja2"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="SmartAssist",
    icon=os.path.join(SPECPATH, "smartassist.ico"),
    console=False,                         # a normal window, no black command window
    version=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="SmartAssist")
