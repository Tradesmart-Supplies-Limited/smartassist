"""Build one 3-page PDF per truck, using the sample PDF itself as the template.

Nothing is redrawn. For each spot in core/layout.py we remove the old text
and write the new text at the same place, size, weight and colour.
"""
import io
import os
import re
from decimal import Decimal, ROUND_HALF_UP

try:
    import pymupdf
except ImportError:          # older installs call the package "fitz"
    import fitz as pymupdf

from fontTools.ttLib import TTFont

from core import layout

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CENT = Decimal("0.01")
CELL_PADDING = 2.0           # points kept free between text and the table lines
SPOT_TOLERANCE = 1.5         # how far (points) a text may sit from its expected spot

FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


class LayoutError(Exception):
    """The uploaded PDF does not match the expected sample."""


# ---------- fonts ----------

def _load_font(file_name, builtin):
    """Arial from Windows if present, otherwise a built-in PDF font."""
    path = os.path.join(FONT_DIR, file_name)
    if not os.path.exists(path):
        return {"name": builtin, "data": None, "font": pymupdf.Font(builtin)}
    # Arial draws "-" and the invisible "soft hyphen" with the same shape (same for the
    # space and the "no-break space"). A PDF reader would then read "YS-BMS10-288" back
    # with the wrong hidden character, so we drop those two twins from our copy of the font.
    font = TTFont(path)
    for table in font["cmap"].tables:
        table.cmap.pop(0xAD, None)    # soft hyphen
        table.cmap.pop(0xA0, None)    # no-break space
    buffer = io.BytesIO()
    font.save(buffer)
    data = buffer.getvalue()
    return {"name": file_name[:-4], "data": data, "font": pymupdf.Font(fontbuffer=data)}


FONTS = {False: _load_font("arial.ttf", "helv"), True: _load_font("arialbd.ttf", "hebo")}


# ---------- formatting (all figures are calculated here, by code) ----------

def format_date(day):
    """date(2026, 10, 12) -> '12-Oct-26' (month names are typed above, not from the locale)."""
    return f"{day.day:02d}-{MONTHS[day.month - 1]}-{day.year % 100:02d}"


def plain(number):
    """Decimal('42.50') -> '42.5', Decimal('40') -> '40'"""
    text = format(Decimal(number), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def two_decimals(number):
    """Decimal('2800') -> '2,800.00'"""
    return f"{Decimal(number).quantize(CENT, rounding=ROUND_HALF_UP):,.2f}"


def amount(tonnage, price):
    """Amount = quantity x price, rounded half up to cents."""
    return (Decimal(tonnage) * Decimal(price)).quantize(CENT, rounding=ROUND_HALF_UP)


def agent_for_border(border):
    """The DRC clearance agent for an exit border, or None if the border is not known."""
    return layout.AGENTS.get(" ".join(str(border).split()).upper())


def document_values(truck, tonnage, packages, date_text, prices, freight1, freight2, agent=None):
    """Every text that goes into one truck's PDF, as {key: text}.

    agent: the clearance agent ({"name", "mobile"}). If not given, it follows the truck's exit border;
    a border without a known agent must be confirmed by the manager first (the app asks).
    """
    agent = agent or agent_for_border(truck.border)
    if agent is None:
        raise ValueError(f"No clearance agent is known for exit border '{truck.border}'.")
    amounts = {name: amount(tonnage, price) for name, price in prices.items()}
    total = sum(amounts.values(), Decimal("0"))
    quantity = two_decimals(tonnage) + " MT"
    values = {
        "invoice_no": truck.invoice_no,
        "date": date_text,
        "driver": truck.driver,
        "passport": truck.passport,
        "horse": truck.horse,
        "trailer1": truck.trailer1,
        "trailer2": truck.trailer2 or "NIL",
        "border": truck.border,
        "packages": plain(packages),
        "bags": two_decimals(packages),
        "quantity": quantity,
        "weight": plain(tonnage) + "MT",
        "freight1_text": freight1,
        "freight2_text": freight2,
        "total": "$" + two_decimals(total),
        "agent_contact": "Contact person :" + agent["name"],
        "agent_mobile": "Mobile :" + agent["mobile"],
    }
    for name in prices:
        values["price_" + name] = "$" + two_decimals(prices[name])
        values["amount_" + name] = "$" + two_decimals(amounts[name])
    return values


# ---------- reading the sample ----------

def _page_spans(page):
    """All text spans on a page."""
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans.extend(line["spans"])
    return spans


def _cell_edges(page, span):
    """Left and right table lines of the cell that holds this span."""
    x0, y0, x1, y1 = span["bbox"]
    middle = (y0 + y1) / 2
    left, right = page.rect.x0, page.rect.x1
    for drawing in page.get_drawings():
        r = drawing["rect"]
        if r.width > 1 or not (r.y0 <= middle <= r.y1):
            continue                      # not a vertical line next to this text
        if r.x0 <= x0 + 1:
            left = max(left, r.x0)
        elif r.x0 >= x1 - 1:
            right = min(right, r.x0)
    return left, right


def _span_at(spans, x, y, align):
    """The one text on this line (middle height y) that is centred on x, or ends at x for "right"."""
    found = [s for s in spans if abs((s["bbox"][1] + s["bbox"][3]) / 2 - y) <= SPOT_TOLERANCE + 1 and
             (abs(s["bbox"][2] - x) <= SPOT_TOLERANCE if align == "right"
              else s["bbox"][0] - 1 <= x <= s["bbox"][2] + 1)]
    return found[0] if len(found) == 1 else None


def load_template(pdf_bytes):
    """Check the sample and prepare it for filling. Raises LayoutError if it does not match.

    Returns a dict with:
      base   - a 3-page PDF (bytes) with the per-truck texts removed
      spots  - where and how to write each value
      sample - the values the sample itself shows, {key: text}
    """
    try:
        source = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        raise LayoutError(f"This file cannot be opened as a PDF ({error}).")
    if len(source) < layout.PAGES:
        raise LayoutError(f"The sample must have at least {layout.PAGES} pages, this PDF has {len(source)}.")

    # Copy pages 1-3 into a NEW file, so the inspection photos are left behind.
    base = pymupdf.open()
    base.insert_pdf(source, from_page=0, to_page=layout.PAGES - 1)

    spots, sample, problems = [], {}, []
    for page_no, title in enumerate(layout.TITLES):
        if title not in " ".join(base[page_no].get_text().split()):
            problems.append(f"page {page_no + 1}: the title '{title}' is missing")
    spans_by_page = [_page_spans(page) for page in base]
    for page_no, x, y, key, align in layout.SPOTS:
        page = base[page_no]
        span = _span_at(spans_by_page[page_no], x, y, align)
        where = f"page {page_no + 1}, {key}"
        if span is None:
            problems.append(f"{where}: nothing found at the expected place")
            continue
        text = span["text"].strip()
        if key in layout.FORMATS and not re.fullmatch(layout.FORMATS[key], text):
            example = layout.SAMPLE_VALUES.get(key, "")
            problems.append(f"{where}: found '{text}', which is not in the expected format (like '{example}')")
            continue
        if key in sample and text != sample[key]:
            problems.append(f"{where}: found '{text}' but the same field elsewhere shows '{sample[key]}'")
            continue
        sample[key] = text

        x0, y0, x1, y1 = span["bbox"]
        left, right = _cell_edges(page, span)
        centre = (x0 + x1) / 2
        if align == "right":
            max_width = x1 - left - CELL_PADDING
        else:
            max_width = 2 * (min(centre - left, right - centre) - CELL_PADDING)
        colour = span["color"]
        spots.append({
            "page": page_no, "key": key, "align": align,
            "centre": centre, "right": x1, "baseline": span["origin"][1],
            "size": span["size"], "bold": bool(span["flags"] & 16),
            "colour": ((colour >> 16) / 255, ((colour >> 8) & 255) / 255, (colour & 255) / 255),
            "max_width": max_width, "cell": (left, right),
            # the sample ends some amounts with a space; keep it so the text stays identical
            "suffix": span["text"][len(span["text"].rstrip()):],
        })
        # Remove only this text: a thin strip through the middle of its letters.
        middle = (y0 + y1) / 2
        page.add_redact_annot(pymupdf.Rect(x0 + 0.2, middle - 1, x1 - 0.2, middle + 1), fill=False)

    if problems:
        raise LayoutError("This PDF does not match the expected sample:\n- " + "\n- ".join(problems))

    for page in base:
        page.apply_redactions(images=0, graphics=0)   # 0 = leave pictures and lines alone
    return {"base": base.tobytes(garbage=4, deflate=True), "spots": spots, "sample": sample}


# ---------- writing one truck ----------

def fitted_size(font, text, size, max_width):
    """The font size to use so that the text fits in max_width."""
    width = font.text_length(text, fontsize=size)
    return size if width <= max_width else size * max_width / width


def build_pdf(template, values):
    """Write one truck's values into the template. Returns the PDF as bytes."""
    doc = pymupdf.open(stream=template["base"], filetype="pdf")
    ready = set()                 # (page, bold) pairs whose font is already on the page
    for spot in template["spots"]:
        text = values[spot["key"]] + spot["suffix"]
        if not text.strip():
            continue
        f = FONTS[spot["bold"]]
        size = fitted_size(f["font"], text, spot["size"], spot["max_width"])
        width = f["font"].text_length(text, fontsize=size)
        x = spot["right"] - width if spot["align"] == "right" else spot["centre"] - width / 2
        page = doc[spot["page"]]
        if f["data"] and (spot["page"], spot["bold"]) not in ready:
            page.insert_font(fontname=f["name"], fontbuffer=f["data"])
            ready.add((spot["page"], spot["bold"]))
        page.insert_text(
            (x, spot["baseline"]), text,
            fontname=f["name"], fontsize=size, color=spot["colour"],
        )
    try:
        doc.subset_fonts()        # keep only the letters we used, so the file stays small
    except Exception:
        pass
    return doc.tobytes(garbage=3, deflate=True)
