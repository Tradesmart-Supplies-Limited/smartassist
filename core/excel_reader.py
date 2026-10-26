# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
import pandas as pd


def read_raw_sheets(file, filename):
    """Read every sheet exactly as it is, with no header guessing."""
    if filename.lower().endswith(".csv"):
        return {"CSV": pd.read_csv(file, header=None, dtype=object)}
    return pd.read_excel(file, sheet_name=None, header=None, dtype=object)


def detect_header_row(raw, scan_rows=30):
    """Guess which row holds the column titles (the first row that is mostly text)."""
    scores = []
    for i in range(min(scan_rows, len(raw))):
        scores.append(sum(isinstance(v, str) and v.strip() != "" for v in raw.iloc[i]))
    if not scores or max(scores) == 0:
        return 0
    threshold = 0.7 * max(scores)
    for i, s in enumerate(scores):
        if s >= threshold:
            return i
    return 0


def clean_sheet(raw, header_row):
    """Turn the raw sheet into a clean table using the chosen header row."""
    headers = [str(v).strip() if pd.notna(v) else "" for v in raw.iloc[header_row]]
    seen, names = {}, []
    for j, h in enumerate(headers):
        if h == "":
            h = f"Column {j + 1}"
        if h in seen:
            seen[h] += 1
            h = f"{h} ({seen[h]})"
        else:
            seen[h] = 1
        names.append(h)

    df = raw.iloc[header_row + 1:].copy()
    df.columns = names
    df = df.dropna(how="all").dropna(axis=1, how="all")
    for c in df.columns:
        df[c] = df[c].apply(lambda v: v.strip() if isinstance(v, str) else v)
    return df.reset_index(drop=True)