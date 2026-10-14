"""Typed orders ("skip truck 3", "coal is 75") turned into a fixed list of settings.

The language model only proposes actions in a strict JSON shape. Everything else is done here,
by code: checking the JSON, finding the trucks, reading dates, checking limits and applying.
Orders only change Step 3 settings and which trucks are made. They never touch a figure inside
a document: figures still come only from the Excel and the price formulas.
"""
import csv
import json
import os
import re
from datetime import date, datetime, timedelta

from core.pdf_builder import format_date

# ---------- sanity limits ----------
MAX_PRICE = 1000          # USD per MT, must be above 0
MAX_TONNAGE = 100         # MT, must be above 0
MIN_PACKAGES, MAX_PACKAGES = 1, 1000
MAX_LABEL = 60            # characters in a freight line wording

# ---------- the Step 3 settings an order may change (session_state keys used by app.py) ----------
KEY_DATE = "doc_date"
KEY_PRICES = {"coal": "price_coal", "freight_1": "price_freight1",
              "freight_2": "price_freight2", "insurance": "price_insurance"}
KEY_LABELS = {"freight_1": "freight1_text", "freight_2": "freight2_text"}
KEY_SOURCE = "source"
SOURCE_EXCEL = "From the Excel (each truck's own figures)"
SOURCE_FIXED = "Fixed figures for every truck"
KEY_TONNAGE = "fixed_tonnage"
KEY_PACKAGES = "fixed_packages"
KEY_EXCLUDED = "excluded_rows"     # Excel rows of trucks not to make
KEY_ONLY = "only_rows"             # if set: make only these Excel rows
KEY_ACTIVE = "active_changes"      # plain-English list of applied orders

ITEM_NAMES = {"coal": "Coal", "freight_1": "Freight line 1", "freight_2": "Freight line 2",
              "insurance": "Insurance"}

# ---------- the JSON shape the model must answer in (kept flat on purpose) ----------
ACTION_TYPES = ["exclude_trucks", "only_trucks", "set_date", "set_price", "set_freight_label",
                "fixed_quantity", "use_excel_quantity"]
ITEMS = ["coal", "freight_1", "freight_2", "insurance"]
LINES = ["freight_1", "freight_2"]

SCHEMA = {
    "type": "object",
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ACTION_TYPES},
                    "trucks": {"type": ["array", "null"], "items": {"type": "string"}},
                    "range_from": {"type": ["string", "null"]},
                    "range_to": {"type": ["string", "null"]},
                    "date_text": {"type": ["string", "null"]},
                    "item": {"type": ["string", "null"], "enum": ITEMS + [None]},
                    "line": {"type": ["string", "null"], "enum": LINES + [None]},
                    "price": {"type": ["number", "null"]},
                    "text": {"type": ["string", "null"]},
                    "tonnage": {"type": ["number", "null"]},
                    "packages": {"type": ["integer", "null"]},
                },
                "required": ["type", "trucks", "range_from", "range_to", "date_text", "item", "line",
                             "price", "text", "tonnage", "packages"],
            },
        },
        "unsupported": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["actions", "unsupported"],
}

SYSTEM_PROMPT = """You turn a manager's order about truck documents into JSON settings.
Allowed action types (every action has all keys; unused keys are null):
- exclude_trucks: do not make documents for some trucks. Use "trucks" (list) or "range_from"/"range_to".
- only_trucks: make documents only for some trucks. Use "trucks" or "range_from"/"range_to".
- set_date: the date on the documents. Copy the date words exactly into "date_text".
- set_price: price per tonne for one "item": coal, freight_1 (road freight outside DRC, the first
  freight line), freight_2 (road freight inside DRC, the second freight line) or insurance. Put the number in "price".
- set_freight_label: new wording for freight line "line" (freight_1 or freight_2) in "text".
- fixed_quantity: the same "tonnage" and/or "packages" for EVERY truck.
- use_excel_quantity: take tonnage and packages from the Excel again.
Rules:
- Copy truck references exactly as typed (a number, an invoice number, a horse registration or a driver name).
- Never invent trucks, dates or numbers. Never change a figure for one single truck.
- Anything else (other requests, changing one truck's weight or total, deleting, emailing, consignee)
  goes into "unsupported" as a short phrase, with no action.
Examples:
"skip truck 3" -> {"actions":[{"type":"exclude_trucks","trucks":["3"],"range_from":null,"range_to":null,"date_text":null,"item":null,"line":null,"price":null,"text":null,"tonnage":null,"packages":null}],"unsupported":[]}
"only make trucks 1 to 4" -> {"actions":[{"type":"only_trucks","trucks":null,"range_from":"1","range_to":"4","date_text":null,"item":null,"line":null,"price":null,"text":null,"tonnage":null,"packages":null}],"unsupported":[]}
"coal is 75 and date them 20 October" -> {"actions":[{"type":"set_price","trucks":null,"range_from":null,"range_to":null,"date_text":null,"item":"coal","line":null,"price":75,"text":null,"tonnage":null,"packages":null},{"type":"set_date","trucks":null,"range_from":null,"range_to":null,"date_text":"20 October","item":null,"line":null,"price":null,"text":null,"tonnage":null,"packages":null}],"unsupported":[]}
"use 40 tonnes and 40 bags for all trucks" -> {"actions":[{"type":"fixed_quantity","trucks":null,"range_from":null,"range_to":null,"date_text":null,"item":null,"line":null,"price":null,"text":null,"tonnage":40,"packages":40}],"unsupported":[]}
"set truck 5 total to 9000 and print them" -> {"actions":[],"unsupported":["set truck 5 total to 9000","print them"]}
"""

FIELD_TYPES = {"trucks": "list", "range_from": "str", "range_to": "str", "date_text": "str",
               "item": "item", "line": "line", "price": "number", "text": "str",
               "tonnage": "number", "packages": "int"}


class InvalidReply(Exception):
    """The model's answer is not usable JSON in the expected shape."""


# ---------- 1. checking the model's JSON ----------

def _clean_value(kind, value):
    """The value if it has the right type, otherwise None."""
    if value is None:
        return None
    is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "str":
        if isinstance(value, str):
            return value.strip() or None
        return str(value) if is_number else None
    if kind == "list":
        if not isinstance(value, list):
            return None
        items = [str(v).strip() for v in value if isinstance(v, str) or (isinstance(v, int) and not isinstance(v, bool))]
        return [v for v in items if v] or None
    if kind == "item":
        return value if value in ITEMS else None
    if kind == "line":
        return value if value in LINES else None
    if kind == "number":
        return value if is_number else None
    if kind == "int":
        return int(value) if is_number and float(value).is_integer() else None
    return None


def validate_reply(data):
    """Check the model's JSON. Returns (actions, unsupported, dropped).

    Unknown keys and wrong types are dropped; unknown action types are left out and counted.
    Raises InvalidReply if the overall shape is wrong.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            raise InvalidReply("not JSON")
    if not isinstance(data, dict) or not isinstance(data.get("actions", []), list):
        raise InvalidReply("wrong shape")
    actions, dropped = [], 0
    for raw in data.get("actions") or []:
        if not isinstance(raw, dict) or raw.get("type") not in ACTION_TYPES:
            dropped += 1
            continue
        action = {"type": raw["type"]}
        for key, kind in FIELD_TYPES.items():
            action[key] = _clean_value(kind, raw.get(key))
        actions.append(action)
    unsupported = [u.strip() for u in data.get("unsupported") or [] if isinstance(u, str) and u.strip()]
    return actions, unsupported, dropped


# ---------- 2. dates (read by code, English months typed here) ----------

MONTHS = {"jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
          "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
          "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12}


def parse_date(text, today):
    """'15 October', '15 Oct 2026', '2026-10-15', 'today', 'tomorrow', 'yesterday' -> date, else None.
    A missing year means the current year."""
    words = (text or "").lower().replace(",", " ").replace("'s", " ").split()
    words = [w for w in words if w not in ("the", "of", "on", "date", "dated", "use")]
    simple = " ".join(words)
    if simple in ("today", "tomorrow", "yesterday"):
        return today + timedelta(days={"today": 0, "tomorrow": 1, "yesterday": -1}[simple])
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", simple)
    if match:
        year, month, day = (int(g) for g in match.groups())
    else:
        parts = re.split(r"[\s\-/.]+", simple)
        parts = [re.sub(r"^(\d+)(st|nd|rd|th)$", r"\1", p) for p in parts if p]
        if len(parts) not in (2, 3):
            return None
        if parts[0].isdigit() and parts[1] in MONTHS:          # 15 October [2026]
            day, month = int(parts[0]), MONTHS[parts[1]]
        elif parts[0] in MONTHS and parts[1].isdigit():        # October 15 [2026]
            day, month = int(parts[1]), MONTHS[parts[0]]
        else:
            return None
        year = today.year
        if len(parts) == 3:
            if not parts[2].isdigit():
                return None
            year = int(parts[2]) + (2000 if len(parts[2]) == 2 else 0)
    try:
        return date(year, month, day)
    except ValueError:
        return None


# ---------- 3. finding trucks (by code, unique matches only) ----------
# A truck reference is a dict: {"row", "sn", "invoice_no", "horse", "driver"}.

def _simple(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def find_truck(ref, trucks):
    """Return (truck, None) or (None, reason). Tries, in order: exact invoice no., invoice-no.
    ending, S/N, horse reg., driver name. A step that matches several trucks is a refusal."""
    typed = re.sub(r"^(truck|trucks|invoice|inv|no\.?|number|s/?n|serial)\s*[#:.]?\s*", "",
                   ref.strip(), flags=re.I).strip() or ref.strip()
    key = _simple(typed)
    if not key:
        return None, f"'{ref}' is not a truck reference"

    def ending(invoice):
        digits = re.search(r"(\d+)$", invoice or "")
        return digits.group(1).lstrip("0") if digits else None

    steps = [
        ("invoice no.", lambda t: _simple(t["invoice_no"]) == key),
        ("invoice no. ending", lambda t: key.isdigit() and ending(t["invoice_no"]) == key.lstrip("0")),
        ("S/N", lambda t: _simple(t["sn"]) == key),
        ("horse reg.", lambda t: _simple(t["horse"]) == key),
        ("driver name", lambda t: _simple(t["driver"]) == key),
        ("driver name", lambda t: key in _simple(t["driver"]) and len(key) >= 3),
    ]
    for label, test in steps:
        found = [t for t in trucks if test(t)]
        if len(found) == 1:
            return found[0], None
        if len(found) > 1:
            return None, f"'{ref}' matches {len(found)} trucks by {label}; please be more precise"
    return None, f"no truck matches '{ref}'"


def find_range(start, end, trucks):
    """Trucks whose S/N is from `start` to `end` (numbers). Returns (trucks, None) or ([], reason)."""
    try:
        low, high = sorted((int(str(start).strip()), int(str(end).strip())))
    except ValueError:
        return [], f"the range '{start} to {end}' must be two S/N numbers"
    found = [t for t in trucks if _simple(t["sn"]).isdigit() and low <= int(_simple(t["sn"])) <= high]
    if not found:
        return [], f"no truck has an S/N from {low} to {high}"
    return found, None


def describe_truck(t):
    return f"S/N {t['sn'] or '?'} · {t['invoice_no'] or '(no invoice no.)'} · {t['driver'] or '(no driver)'}"


# ---------- 4. turning actions into a plan ----------

def _picked_trucks(action, trucks):
    """Resolve the trucks of an exclude/only action. Returns (found trucks, reasons for refusals)."""
    found, reasons = [], []
    if action["range_from"] or action["range_to"]:
        group, reason = find_range(action["range_from"] or "", action["range_to"] or "", trucks)
        found += group
        if reason:
            reasons.append(reason)
    for ref in action["trucks"] or []:
        truck, reason = find_truck(ref, trucks)
        if truck:
            found.append(truck)
        else:
            reasons.append(reason)
    unique = {t["row"]: t for t in found}
    return list(unique.values()), reasons


def check_action(action, trucks, today):
    """One validated action -> list of plan items: {"ok", "say", "set"/"exclude"/"only"}."""
    kind = action["type"]
    per_truck = action["trucks"] or action["range_from"] or action["range_to"]

    def refuse(reason):
        return [{"ok": False, "say": reason}]

    if kind in ("exclude_trucks", "only_trucks"):
        if not per_truck:
            return refuse(f"{kind.replace('_', ' ')}: no truck was named")
        found, reasons = _picked_trucks(action, trucks)
        items = [{"ok": False, "say": r} for r in reasons]
        if found:
            rows = [t["row"] for t in found]
            names = "; ".join(describe_truck(t) for t in found)
            if kind == "exclude_trucks":
                items.insert(0, {"ok": True, "say": f"Do not make: {names}", "exclude": rows})
            else:
                items.insert(0, {"ok": True, "say": f"Make only: {names} (replaces any earlier 'only' order)",
                                 "only": rows})
        return items

    if per_truck:   # every other setting applies to all trucks; a figure for one truck is never changed
        return refuse(f"{kind.replace('_', ' ')} for single trucks is not allowed: settings apply to every truck")

    if kind == "set_date":
        day = parse_date(action["date_text"], today)
        if day is None:
            return refuse(f"date not understood: '{action['date_text'] or ''}'")
        return [{"ok": True, "say": f"Date on the documents: {format_date(day)}", "set": {KEY_DATE: day}}]

    if kind == "set_price":
        item, price = action["item"], action["price"]
        if item is None or price is None:
            return refuse("set price: the item or the price is missing")
        if not 0 < price <= MAX_PRICE:
            return refuse(f"{ITEM_NAMES[item]} price {price} rejected: it must be above 0 and up to {MAX_PRICE}")
        return [{"ok": True, "say": f"{ITEM_NAMES[item]} price: ${price:,.2f} per MT",
                 "set": {KEY_PRICES[item]: float(round(price, 2))}}]

    if kind == "set_freight_label":
        line, text = action["line"], (action["text"] or "").strip()
        if line is None or not text:
            return refuse("freight wording: the line or the new wording is missing")
        if len(text) > MAX_LABEL:
            return refuse(f"freight wording rejected: longer than {MAX_LABEL} characters")
        return [{"ok": True, "say": f"{ITEM_NAMES[line]} wording: \"{text}\"", "set": {KEY_LABELS[line]: text}}]

    if kind == "fixed_quantity":
        tonnage, packages = action["tonnage"], action["packages"]
        if tonnage is None and packages is None:
            return refuse("fixed figures: no tonnage or packages given")
        if tonnage is not None and not 0 < tonnage <= MAX_TONNAGE:
            return refuse(f"tonnage {tonnage} rejected: it must be above 0 and up to {MAX_TONNAGE}")
        if packages is not None and not MIN_PACKAGES <= packages <= MAX_PACKAGES:
            return refuse(f"packages {packages} rejected: they must be from {MIN_PACKAGES} to {MAX_PACKAGES}")
        changes, said = {KEY_SOURCE: SOURCE_FIXED}, []
        if tonnage is not None:
            changes[KEY_TONNAGE] = float(round(tonnage, 2))
            said.append(f"{tonnage:g} MT")
        if packages is not None:
            changes[KEY_PACKAGES] = int(packages)
            said.append(f"{packages} packages")
        return [{"ok": True, "say": "Same figures for every truck: " + " and ".join(said), "set": changes}]

    # use_excel_quantity
    return [{"ok": True, "say": "Tonnage and packages from the Excel again", "set": {KEY_SOURCE: SOURCE_EXCEL}}]


def make_plan(actions, unsupported, dropped, trucks, today):
    """Returns {"understood": [ok items], "not_done": [plain-English reasons]}."""
    understood, not_done = [], []
    for action in actions:
        for item in check_action(action, trucks, today):
            (understood if item["ok"] else not_done).append(item if item["ok"] else item["say"])
    not_done += [f"Not supported: {u}" for u in unsupported]
    if dropped:
        not_done.append(f"{dropped} unknown order type(s) ignored")
    return {"understood": understood, "not_done": not_done}


def read_order(text, trucks, today, chat):
    """Ask the model (through `chat(system, user, schema) -> str`) and build a plan.
    Retries once if the answer is not valid JSON. Raises InvalidReply after that."""
    for _attempt in range(2):
        try:
            actions, unsupported, dropped = validate_reply(chat(SYSTEM_PROMPT, text, SCHEMA))
            plan = make_plan(actions, unsupported, dropped, trucks, today)
            plan["actions"] = actions
            return plan
        except InvalidReply:
            continue
    raise InvalidReply("The model's answer could not be read twice in a row.")


# ---------- 5. applying (only after the manager clicks Apply) ----------

def apply_plan(plan, state):
    """Write the understood items into `state` (st.session_state or a dict). Orders add up."""
    for item in plan["understood"]:
        for key, value in item.get("set", {}).items():
            state[key] = value
        if "exclude" in item:
            state[KEY_EXCLUDED] = sorted(set(state.get(KEY_EXCLUDED, [])) | set(item["exclude"]))
        if "only" in item:
            state[KEY_ONLY] = sorted(item["only"])
        state[KEY_ACTIVE] = state.get(KEY_ACTIVE, []) + [item["say"]]
    return state


def log_instruction(path, text, actions, applied):
    """Add one line to the instructions log (CSV)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["timestamp", "typed text", "validated actions", "applied"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"), text,
                         json.dumps(actions, ensure_ascii=False), "yes" if applied else "no"])
