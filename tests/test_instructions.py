# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Instruction handling with NO language model: the model's answer is faked (invented data only)."""
import csv
import json
import os
from datetime import date

import pytest

from core import instructions as ins

CASES = json.load(open(os.path.join(os.path.dirname(__file__), "instruction_cases.json"), encoding="utf-8"))
TODAY = date.fromisoformat(CASES["today"])
TRUCKS = CASES["trucks"]


def reply(*actions, unsupported=()):
    """What the model would answer, as a JSON string."""
    return json.dumps({"actions": list(actions), "unsupported": list(unsupported)})


def fake_chat(answer):
    return lambda system, user, schema: answer


def applied(plan):
    """The settings a plan would change, starting from nothing."""
    return ins.apply_plan(plan, {})


# ---------- the cases file itself ----------

@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["text"])
def test_each_case_gives_the_intended_result(case):
    plan = ins.read_order(case["text"], TRUCKS, TODAY, fake_chat(reply(*case["expected"])))
    if case.get("unsupported"):
        assert plan["understood"] == []
    else:
        assert plan["understood"] and plan["not_done"] == [], plan["not_done"]


def test_cases_file_has_25_orders_and_5_unsupported():
    assert len(CASES["cases"]) == 25
    assert sum(1 for c in CASES["cases"] if c.get("unsupported")) >= 5


# ---------- trucks ----------

@pytest.mark.parametrize("ref, sn", [("XX-TEST-290", "3"), ("xx-test-290", "3"), ("290", "3"),
                                     ("truck 3", "3"), ("3", "3"), ("aaa104zm", "4"),
                                     ("Grace Zulu", "5"), ("tembo", "3")])
def test_find_truck(ref, sn):
    truck, reason = ins.find_truck(ref, TRUCKS)
    assert reason is None and truck["sn"] == sn


def test_unknown_or_ambiguous_truck_is_refused():
    assert ins.find_truck("999", TRUCKS)[0] is None
    two_johns = TRUCKS + [{"row": 14, "sn": "9", "invoice_no": "XX-TEST-296", "horse": "B1", "driver": "JOHN MWALE"}]
    truck, reason = ins.find_truck("John Mwale", two_johns)
    assert truck is None and "2 trucks" in reason


def test_range_uses_sn_only():
    found, reason = ins.find_range("2", "4", TRUCKS)
    assert reason is None and [t["sn"] for t in found] == ["2", "3", "4"]
    assert ins.find_range("20", "30", TRUCKS)[0] == []


def test_truck_actions_name_invoice_and_driver():
    plan = ins.read_order("skip 3", TRUCKS, TODAY, fake_chat(reply({"type": "exclude_trucks", "trucks": ["3"]})))
    assert "XX-TEST-290" in plan["understood"][0]["say"] and "MARY TEMBO" in plan["understood"][0]["say"]


# ---------- dates ----------

@pytest.mark.parametrize("text, expected", [
    ("15 October", date(2026, 10, 15)), ("15 Oct 2026", date(2026, 10, 15)), ("2026-10-15", date(2026, 10, 15)),
    ("October 15", date(2026, 10, 15)), ("15th of October 2027", date(2027, 10, 15)),
    ("today", TODAY), ("tomorrow", date(2026, 10, 15)), ("yesterday", date(2026, 10, 13)),
    ("31 February", None), ("next week", None), ("", None)])
def test_parse_date(text, expected):
    assert ins.parse_date(text, TODAY) == expected


# ---------- limits and hard rules ----------

@pytest.mark.parametrize("action", [
    {"type": "set_price", "item": "coal", "price": 0},
    {"type": "set_price", "item": "coal", "price": 1001},
    {"type": "fixed_quantity", "tonnage": 101},
    {"type": "fixed_quantity", "packages": 0},
    {"type": "set_freight_label", "line": "freight_1", "text": "x" * 61},
    {"type": "fixed_quantity", "tonnage": 38, "trucks": ["3"]},       # a figure for one truck: never
    {"type": "set_price", "item": "coal", "price": 75, "trucks": ["3"]},
    {"type": "set_date", "date_text": "someday"},
])
def test_out_of_limits_or_per_truck_figures_are_rejected(action):
    plan = ins.read_order("x", TRUCKS, TODAY, fake_chat(reply(action)))
    assert plan["understood"] == [] and plan["not_done"]


def test_wrong_types_and_unknown_keys_are_dropped():
    actions, unsupported, dropped = ins.validate_reply({
        "actions": [{"type": "set_price", "item": "coal", "price": "75", "colour": "red"},
                    {"type": "launch_rocket"}, "nonsense"],
        "unsupported": ["coffee", 5]})
    assert actions[0]["price"] is None and "colour" not in actions[0]
    assert dropped == 2 and unsupported == ["coffee"]


def test_invalid_json_is_retried_once_then_fails():
    answers = iter(["not json", reply({"type": "use_excel_quantity"})])
    plan = ins.read_order("back to the excel figures", TRUCKS, TODAY, lambda *a: next(answers))
    assert plan["understood"][0]["set"] == {ins.KEY_SOURCE: ins.SOURCE_EXCEL}
    with pytest.raises(ins.InvalidReply):
        ins.read_order("x", TRUCKS, TODAY, fake_chat("still not json"))


# ---------- the order must really ask for it ----------

@pytest.mark.parametrize("typed, action", [
    ("Change the consignee to ABC Mining", {"type": "exclude_trucks", "trucks": ["3"]}),     # truck not typed
    ("change truck 3 weight to 38", {"type": "exclude_trucks", "trucks": ["3"]}),           # no skip word
    ("change truck 3 weight to 38", {"type": "fixed_quantity", "tonnage": 38}),             # not every truck
    ("Email the PDFs to the client", {"type": "set_price", "item": "coal", "price": 75}),   # number not typed
    ("Email the PDFs to the client", {"type": "set_date", "date_text": "20 October"}),     # date not typed
    ("Email the PDFs to the client", {"type": "use_excel_quantity"}),                      # no excel word
    ("Only do XX-TEST-290", {"type": "exclude_trucks", "trucks": ["XX-TEST-290"]}),         # opposite meaning
])
def test_actions_not_in_the_typed_order_are_refused(typed, action):
    plan = ins.read_order(typed, TRUCKS, TODAY, fake_chat(reply(action)))
    assert plan["understood"] == [] and "your order" in plan["not_done"][0]


def test_trucks_inside_a_typed_range_count_as_typed():
    plan = ins.read_order("Only make trucks 5 to 8", TRUCKS, TODAY,
                          fake_chat(reply({"type": "only_trucks", "trucks": ["5", "6", "7", "8"]})))
    assert plan["not_done"] == [] and applied(plan)[ins.KEY_ONLY] == [10, 11, 12, 13]


def test_only_the_untyped_trucks_are_refused():
    plan = ins.read_order("Remove horse AAA104ZM", TRUCKS, TODAY,
                          fake_chat(reply({"type": "exclude_trucks", "trucks": ["17", "AAA104ZM"]})))
    assert applied(plan)[ins.KEY_EXCLUDED] == [9] and "17" in plan["not_done"][0]


def test_empty_actions_are_ignored_and_a_stray_date_is_kept():
    plan = ins.read_order("Skip trucks 2 and 7, and date them yesterday", TRUCKS, TODAY, fake_chat(reply(
        {"type": "exclude_trucks", "trucks": ["2", "7"], "date_text": "yesterday"}, {"type": "set_price"})))
    assert plan["not_done"] == []
    assert applied(plan)[ins.KEY_DATE] == date(2026, 10, 13) and applied(plan)[ins.KEY_EXCLUDED] == [7, 12]


def test_empty_answer_says_nothing_was_understood():
    plan = ins.read_order("delete everything", TRUCKS, TODAY, fake_chat(reply()))
    assert plan["understood"] == [] and plan["not_done"] == ["Nothing in this order could be understood as a setting"]


# ---------- applying ----------

def test_nothing_changes_until_apply_and_orders_add_up():
    state = {"price_coal": 70.0}
    plan = ins.read_order("coal 75 and skip truck 1", TRUCKS, TODAY, fake_chat(reply(
        {"type": "set_price", "item": "coal", "price": 75}, {"type": "exclude_trucks", "trucks": ["1"]})))
    assert state == {"price_coal": 70.0}                  # reading an order changes nothing
    ins.apply_plan(plan, state)
    assert state["price_coal"] == 75.0 and state[ins.KEY_EXCLUDED] == [6]
    second = ins.read_order("skip 2", TRUCKS, TODAY, fake_chat(reply({"type": "exclude_trucks", "trucks": ["2"]})))
    ins.apply_plan(second, state)
    assert state[ins.KEY_EXCLUDED] == [6, 7] and len(state[ins.KEY_ACTIVE]) == 3


def test_fixed_and_excel_quantity():
    plan = ins.read_order("42.5 tonnes on every truck", TRUCKS, TODAY,
                          fake_chat(reply({"type": "fixed_quantity", "tonnage": 42.5})))
    assert applied(plan) == {ins.KEY_SOURCE: ins.SOURCE_FIXED, ins.KEY_TONNAGE: 42.5,
                             ins.KEY_ACTIVE: ["Same figures for every truck: 42.5 MT"]}


def test_log_is_written(tmp_path):
    path = tmp_path / "log" / "instructions_log.csv"
    ins.log_instruction(str(path), "skip truck 3", [{"type": "exclude_trucks"}], True, "bms")
    ins.log_instruction(str(path), "make coffee", [], False, "bms")
    rows = list(csv.reader(open(path, encoding="utf-8")))
    assert rows[0] == ["timestamp", "typed text", "validated actions", "applied", "client"]
    assert rows[1][1:] == ["skip truck 3", '[{"type": "exclude_trucks"}]', "yes", "BMS"] and rows[2][3] == "no"
