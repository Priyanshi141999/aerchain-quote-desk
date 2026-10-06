"""The analyst: plain-English questions → real calculations on the extracted data → grounded answer.

Step 1 (AI plans): the model reads the question and the table schemas and writes pandas code.
Step 2 (code runs): the code runs on the real comparison tables. Nothing is answered from memory.
Step 3 (AI explains): the model writes the answer using ONLY the computed results, and lists assumptions.
"""
from __future__ import annotations

import json
import re
import traceback

import numpy as np
import pandas as pd

from .llm import Part, complete_json

PLAN_SYSTEM = """You are a senior procurement analyst working for the buyer. You answer questions about a set
of vendor quotations by WRITING PYTHON (pandas) CODE that runs on the real data. You never compute numbers in
your head and never invent data.

DATA AVAILABLE TO YOUR CODE (already loaded as pandas DataFrames):
- `lines`: one row per vendor x RFQ line. Columns:
  vendor (key A-E), vendor_name, qualification ("qualified"|"conditional"|"not_qualified"), line (1-30), item,
  board, annual_qty, uom, status, price_inr (INR per uom, ex-GST, ex-freight; NaN if not priced),
  freight_inr (INR per uom; NaN if unknown), landed_inr (price+freight; NaN if freight unknown),
  annual_value_inr (price_inr x annual_qty), confidence ("high"|"medium"|"low"|"confirmed"),
  excluded_from_ranking (True when the price is a suspected error, must not win "cheapest" unless the user
  explicitly asks to include it), flag_codes (comma-separated edge-case codes), as_written.
- `vendors`: one row per vendor. Columns: vendor, vendor_name, qualification, Q1_status..Q10_status
  ("yes"|"no"|"partial"|"pending"|"not_answered"), lines_priced, payment_days, lead_time_days, validity_days,
  freight_basis, discounts (text), one_time_charges (text), late_submission (bool), offer_expired (bool),
  blockers, warnings.
- `items`: the 30 RFQ lines (id, name, form, board, dims, bf, print_colours, annual_qty, uom, weight_kg).
- Libraries: pd, np, px (plotly.express). Do NOT import anything. Do not read or write files.

RULES
- "Qualified" means qualification == "qualified" unless the user says otherwise; mention "conditional"
  vendors separately when they change the answer.
- Rows with excluded_from_ranking == True are suspected errors: exclude them from rankings by default and say so.
- Missing prices are NaN: never treat them as zero. If a line has no eligible price, report it explicitly.
- Prefer price_inr for "cheapest/price" questions; use landed_inr only for landed-cost questions, and report
  where freight is unknown.
- Conditional discounts (in vendors.discounts) apply ONLY if their condition is met in the scenario. Check it.
- If the question is ambiguous, pick the most reasonable reading, and state it in "interpretation" and
  "assumptions".
- Your code MUST assign `result` (a DataFrame, Series, dict or number) and MAY assign `fig` (a plotly figure)
  when a chart would help, and MAY assign `export` (a DataFrame) if the user asks for a download/export.
- Keep `result` compact (<= 40 rows). Round money to 2 decimals for unit prices and 0 for totals.

Return JSON: {"interpretation": str, "assumptions": [str], "code": str, "wants_chart": bool}
"""

ANSWER_SYSTEM = """You are a senior procurement analyst writing to the buyer (and their VP). Write the answer
using ONLY the computed results provided. Every number you mention must appear in the results. Be concise and
decision-oriented: lead with the answer, then the 2-4 facts that matter, then caveats that could change the
decision (unqualified vendors, suspected errors, missing lines, unknown freight, conditional discounts, late or
expired offers). Use INR with Indian digit grouping (₹1,23,45,678) or lakh/crore where natural.
If the results are empty or show an error, say plainly what could not be answered and why.

Return JSON: {"answer_markdown": str, "caveats": [str], "followups": [str]}  (2-3 short follow-up questions)
"""

BANNED = re.compile(r"\b(import|open|exec|eval|compile|__\w+__|globals|locals|getattr|setattr|delattr|os\.|sys\.|subprocess|input)\b")


def _safe_frames(lines: pd.DataFrame, vendors: pd.DataFrame, items: list[dict]):
    keep = ["vendor", "vendor_name", "qualification", "line", "item", "board", "annual_qty", "uom", "status",
            "price_inr", "freight_inr", "landed_inr", "annual_value_inr", "confidence", "excluded_from_ranking",
            "flag_codes", "as_written"]
    L = lines[keep].copy()
    for c in ("price_inr", "freight_inr", "landed_inr", "annual_value_inr"):
        L[c] = pd.to_numeric(L[c], errors="coerce")
    I = pd.DataFrame(items)[["id", "name", "form", "board", "dims", "bf", "print_colours", "annual_qty", "uom", "weight_kg"]]
    return L, vendors.copy(), I


def run_code(code: str, L, V, I) -> dict:
    if BANNED.search(code):
        return {"error": "Code used a disallowed operation (imports, files or system access)."}
    import plotly.express as px
    env = {"pd": pd, "np": np, "px": px, "lines": L.copy(), "vendors": V.copy(), "items": I.copy()}
    safe_builtins = {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k)
                     for k in ("len", "range", "min", "max", "sum", "sorted", "round", "abs", "list", "dict", "set",
                               "tuple", "str", "int", "float", "bool", "enumerate", "zip", "any", "all", "isinstance",
                               "print", "map", "filter", "reversed", "Exception", "ValueError", "KeyError")}
    try:
        exec(code, {"__builtins__": safe_builtins}, env)
    except Exception:
        return {"error": traceback.format_exc(limit=2)[-900:]}
    if "result" not in env:
        return {"error": "Code did not assign `result`."}
    return {"result": env["result"], "fig": env.get("fig"), "export": env.get("export")}


def _render(result) -> str:
    if isinstance(result, pd.DataFrame):
        return result.head(40).to_csv(index=False)
    if isinstance(result, pd.Series):
        return result.head(40).to_string()
    try:
        return json.dumps(result, default=str, indent=1)[:6000]
    except Exception:
        return str(result)[:6000]


def ask(question: str, lines: pd.DataFrame, vendors: pd.DataFrame, items: list[dict], history: list[dict] | None = None) -> dict:
    L, V, I = _safe_frames(lines, vendors, items)
    hist = ""
    for h in (history or [])[-4:]:
        hist += f"Q: {h['q']}\nA (summary): {h.get('answer','')[:400]}\n"
    context = (f"Sample of `lines` (first 8 rows):\n{L.head(8).to_csv(index=False)}\n"
               f"`vendors` (all rows):\n{V.to_csv(index=False)}\n"
               f"Previous conversation:\n{hist or '(none)'}\n\nQUESTION: {question}")
    plan = complete_json(PLAN_SYSTEM, [Part(text=context)], max_tokens=6000).data
    out = run_code(plan.get("code", ""), L, V, I)
    if "error" in out:  # one self-correction round, with the real error
        fix_ctx = context + f"\n\nYour previous code:\n{plan.get('code')}\n\nIt failed with:\n{out['error']}\nFix it."
        plan = complete_json(PLAN_SYSTEM, [Part(text=fix_ctx)], max_tokens=6000).data
        out = run_code(plan.get("code", ""), L, V, I)
    computed = out.get("error") and f"ERROR: {out['error']}" or _render(out["result"])
    ans = complete_json(ANSWER_SYSTEM, [Part(text=(
        f"QUESTION: {question}\nINTERPRETATION: {plan.get('interpretation')}\n"
        f"ASSUMPTIONS: {plan.get('assumptions')}\nCOMPUTED RESULTS:\n{computed}"))], max_tokens=3000).data
    return {"question": question, "plan": plan, "result": out.get("result"), "fig": out.get("fig"),
            "export": out.get("export"), "error": out.get("error"), "answer": ans}
