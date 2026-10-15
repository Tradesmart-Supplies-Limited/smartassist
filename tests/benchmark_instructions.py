# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Benchmark: the 25 typed orders against the real local model (needs Ollama running).

Run:  .venv\\Scripts\\python tests\\benchmark_instructions.py
Not a pytest test (pytest does not collect it), because it needs Ollama and takes minutes.
A case is right when the model's answer leads to exactly the same settings as the expected
actions. An unsupported case is right when nothing at all would be applied.
"""
import json
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import instructions as ins   # noqa: E402
from core import llm                   # noqa: E402

CASES = json.load(open(os.path.join(os.path.dirname(__file__), "instruction_cases.json"), encoding="utf-8"))
TODAY = date.fromisoformat(CASES["today"])
TRUCKS = CASES["trucks"]


def settings(plan):
    """The settings a plan would change, without the plain-English summary."""
    state = ins.apply_plan(plan, {})
    state.pop(ins.KEY_ACTIVE, None)
    return state


def short(actions, unsupported=0):
    """A compact one-line view of a list of actions."""
    parts = []
    for a in actions:
        values = [f"{k}={v}" for k, v in a.items() if k != "type" and v is not None]
        parts.append(f"{a['type']}({', '.join(values)})")
    if unsupported:
        parts.append(f"unsupported x{unsupported}")
    return "; ".join(parts) or "-"


def main():
    ok, message = llm.status()
    print(message)
    if not ok:
        return
    rows, times = [], []
    for n, case in enumerate(CASES["cases"], start=1):
        expected_json = json.dumps({"actions": case["expected"], "unsupported": []})
        expected = ins.read_order(case["text"], TRUCKS, TODAY, lambda *a: expected_json)
        start = time.time()
        try:
            got = ins.read_order(case["text"], TRUCKS, TODAY, llm.chat)
            got_text = short(got["actions"], sum(r.startswith("Not supported") for r in got["not_done"]))
            if got["not_done"]:
                got_text += " | not done: " + "; ".join(got["not_done"])
        except (llm.LLMError, ins.InvalidReply) as error:
            got, got_text = None, f"ERROR {error}"
        seconds = time.time() - start
        times.append(seconds)
        if got is None:
            right = False
        elif case.get("unsupported"):
            right = got["understood"] == [] and bool(got["not_done"])
        else:
            right = settings(got) == settings(expected) and got["not_done"] == []
        rows.append((n, case, right, got, got_text, seconds))
        print(f"{n:2} | {case['text'][:55]:55} | expected: {short(case['expected']) if case['expected'] else 'unsupported'}"
              f" | got: {got_text} | {'PASS' if right else 'FAIL'} | {seconds:.1f}s", flush=True)

    passed = sum(r[2] for r in rows)
    unsupported = [r for r in rows if r[1].get("unsupported")]
    not_applied = sum(1 for r in unsupported if r[3] is not None and r[3]["understood"] == [])
    print(f"\nExactly right: {passed}/{len(rows)} ({100 * passed / len(rows):.0f}%)")
    print(f"Unsupported cases NOT applied: {not_applied}/{len(unsupported)}")
    print(f"Seconds per order: first {times[0]:.1f}, median {sorted(times)[len(times) // 2]:.1f}, max {max(times):.1f}")


if __name__ == "__main__":
    main()
