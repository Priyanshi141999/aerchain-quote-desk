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
- `last_year`: last year's rate contract with the incumbent (Annapurna), one row per line it covered. Columns:
  line (same numbering as this RFQ, join on it), ly_item, ly_bf, ly_annual_qty, ly_price_inr (INR per unit ex-GST).
  Lines 20 and 24 are new this year (not in it); line 5's spec changed (20 BF last year, 22 BF now).
  For year-on-year questions compare unit prices on this year's quantities: (price_inr - ly_price_inr) * annual_qty.
- `items`: the 30 RFQ lines (id, name, form, board, dims, bf, print_colours, annual_qty, uom, weight_kg).
- Libraries: pd, np, px (plotly.express). Do NOT import anything. Do not read or write files.

VETTED HELPERS (use them for award scenarios instead of writing your own arithmetic):
- cheapest_split(lines, vendors_allowed=None, basis="price_inr", include_suspect=False) -> DataFrame with one row
  per RFQ line: line, item, annual_qty, n_eligible, winner, winner_name, unit_price, annual_value, runner_up,
  runner_up_price. Lines with no eligible quote have winner=None (report them!).
- single_vendor(lines, vendor, basis="price_inr", discount_pct=0) -> dict with EXACTLY these keys:
  vendor, lines_priced_reliably, total_reliable_lines, total_after_discount, discount_pct, lines_missing,
  lines_suspect_excluded, note.
- same_lines_comparison(split_df, single_vendor_result, lines, basis="price_inr") -> dict with EXACTLY these keys:
  lines_compared, lines_left_out, split_total, vendor_total, vendor_minus_split (negative = vendor cheaper).
  It compares both scenarios over exactly the same lines.
- vendor_totals(lines, basis="price_inr", vendors_allowed=None) -> DataFrame (vendor, vendor_name, qualification,
  lines_priced, lines_with_<basis>, lines_compared, total_on_common_lines), sorted cheapest first. Totals cover
  ONLY lines every listed vendor priced on that basis, so they are comparable. Use it for "who is cheapest overall".
- Use only the keys listed above; do not invent others.

FAIRNESS RULES (a buyer will stake crores on these answers)
- Never rank vendors by totals that cover different sets of lines. Use vendor_totals or same_lines_comparison.
- Unknown freight is UNKNOWN, never zero. For landed-cost questions, say which vendors' freight is unknown and
  compare landed cost only where it is known; otherwise compare basic price and state that freight is missing.
- If the data needed to answer does not exist (e.g. delivery history, past performance, ratings), set
  `result` to say so explicitly and, separately, offer the closest available proxy (e.g. quoted lead time),
  clearly labelled as a proxy. ALWAYS use this when comparing a split with a
  single-vendor award, so the two totals cover the same goods.

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
- When the answer depends on the definition of "qualified", ALSO compute the answer including "conditional"
  vendors and put both in `result`, so the buyer sees what the conditional vendor would change.
- For any award / split / scenario question, `result` MUST include the line-by-line table (line, item, winner,
  unit_price, annual_value, n_eligible) as well as the summary totals, so the buyer can see who wins what.
- `result` must contain EVERY number the answer will need, including totals, differences and counts, as explicit
  values. The writer of the final answer cannot do arithmetic. Best shape: a dict like
  {"summary": {"total_inr": ..., "lines_without_eligible_quote": [...], ...}, "table": <DataFrame>}.
- Keep `result` compact (<= 40 rows). Round money to 2 decimals for unit prices and 0 for totals.

Return JSON: {"interpretation": str, "assumptions": [str], "code": str, "wants_chart": bool}
"""

ANSWER_SYSTEM = """You are a senior procurement analyst writing to the buyer (and their VP). Write the answer
using ONLY the computed results provided. Every number you mention must appear VERBATIM in the results (you may
reformat it as lakh/crore). NEVER add, subtract or total numbers yourself; if a figure you want is not in the
results, leave it out and say it was not computed. Be concise and
decision-oriented: lead with the answer (who wins what, and the total), then the 2-4 facts that matter (e.g. how many
lines each vendor wins, which lines have no eligible quote, WHY vendors are excluded, using VENDOR FACTS), then
caveats that could change the decision (unqualified vendors, suspected errors, missing lines, unknown freight, conditional discounts, late or
expired offers). Money: when a result has a "<name>__say_as" value, quote THAT string exactly (it is already converted to crore/lakh).
Never convert units yourself and never print raw rupee figures like ₹26559500.0. 1 crore = 100 lakh.
Refer to vendors by name (e.g. "Siam Pacific (A)").
If the results are empty or show an error, say plainly what could not be answered and why.
If the results say the requested data does not exist, START by saying so plainly, then present any proxy as a proxy.
If the results show an ERROR, say "I couldn't compute this" and why, never that the data does not exist.
Do not reuse numbers from earlier answers in the conversation; use only this question's computed results.

Return JSON: {"answer_markdown": str, "caveats": [str], "followups": [str]}  (2-3 short follow-up questions)
"""



# ---------------------------------------------------------------- vetted building blocks
def cheapest_split(lines: pd.DataFrame, vendors_allowed=None, basis: str = "price_inr", include_suspect: bool = False) -> pd.DataFrame:
    """Cheapest eligible vendor per RFQ line. Lines with no eligible quote are KEPT with winner=None."""
    df = lines.copy()
    if vendors_allowed is not None:
        df = df[df.vendor.isin(list(vendors_allowed))]
    elig = df[df[basis].notna()]
    if not include_suspect:
        elig = elig[~elig.excluded_from_ranking]
    out = []
    for ln in sorted(lines.line.unique()):
        base = lines[lines.line == ln].iloc[0]
        cand = elig[elig.line == ln].sort_values(basis)
        row = {"line": ln, "item": base["item"], "annual_qty": base["annual_qty"], "n_eligible": len(cand)}
        if len(cand):
            w = cand.iloc[0]
            row.update(winner=w.vendor, winner_name=w.vendor_name, unit_price=round(w[basis], 2),
                       annual_value=round(w[basis] * base["annual_qty"], 0),
                       runner_up=cand.iloc[1].vendor if len(cand) > 1 else None,
                       runner_up_price=round(cand.iloc[1][basis], 2) if len(cand) > 1 else None)
        else:
            row.update(winner=None, winner_name=None, unit_price=None, annual_value=None, runner_up=None, runner_up_price=None)
        out.append(row)
    return pd.DataFrame(out)


def _vendor_key(lines: pd.DataFrame, vendor: str) -> str:
    """Accept a vendor key ('B') or any part of its name ('Deccan')."""
    keys = set(lines.vendor.unique())
    if vendor in keys:
        return vendor
    hits = lines[lines.vendor_name.str.contains(str(vendor), case=False, regex=False)].vendor.unique()
    if len(hits) == 1:
        return hits[0]
    raise ValueError(f"Unknown vendor '{vendor}'. Use one of {sorted(keys)}.")


def single_vendor(lines: pd.DataFrame, vendor: str, basis: str = "price_inr", discount_pct: float = 0.0) -> dict:
    """Award everything to one vendor. Reports exactly which lines are missing or suspect instead of hiding them."""
    vendor = _vendor_key(lines, vendor)
    v = lines[lines.vendor == vendor]
    priced = v[v[basis].notna()]
    ok = priced[~priced.excluded_from_ranking]
    suspect = priced[priced.excluded_from_ranking]
    total_ok = float((ok[basis] * ok.annual_qty).sum())
    return {"vendor": vendor, "lines_priced_reliably": int(len(ok)), "total_reliable_lines": round(total_ok, 0),
            "total_after_discount": round(total_ok * (1 - discount_pct / 100), 0), "discount_pct": discount_pct,
            "lines_missing": sorted(v[v[basis].isna()].line.tolist()),
            "lines_suspect_excluded": sorted(suspect.line.tolist()),
            "note": "Totals cover only reliable lines; compare with other scenarios on the SAME lines."}


def vendor_totals(lines: pd.DataFrame, basis: str = "price_inr", vendors_allowed=None, include_suspect: bool = False) -> pd.DataFrame:
    """Fair vendor-vs-vendor totals: every vendor is totalled over the SAME lines (lines all of them priced on `basis`).
    Also reports each vendor's full coverage so gaps are visible, and how many of its lines lack the basis value."""
    df = lines.copy()
    if vendors_allowed is not None:
        df = df[df.vendor.isin(list(vendors_allowed))]
    ok = df if include_suspect else df[~df.excluded_from_ranking]
    vend = sorted(df.vendor.unique())
    have = ok[ok[basis].notna()].groupby("line").vendor.nunique()
    common = sorted(have[have == len(vend)].index)
    rows = []
    for v in vend:
        d = df[df.vendor == v]
        dv = ok[(ok.vendor == v) & ok.line.isin(common)]
        rows.append({"vendor": v, "vendor_name": d.vendor_name.iloc[0], "qualification": d.qualification.iloc[0],
                     "lines_priced": int(d.price_inr.notna().sum()),
                     f"lines_with_{basis}": int(d[basis].notna().sum()),
                     "lines_compared": len(common),
                     f"total_on_common_lines": round(float((dv[basis] * dv.annual_qty).sum()), 0)})
    out = pd.DataFrame(rows).sort_values("total_on_common_lines")
    out.attrs["common_lines"] = common
    out.attrs["lines_left_out"] = sorted(set(lines.line.unique()) - set(common))
    return out


def same_lines_comparison(split_df: pd.DataFrame, vendor_result: dict, lines: pd.DataFrame, basis: str = "price_inr") -> dict:
    """Compare a split with a single-vendor award over exactly the lines both can cover."""
    if not isinstance(vendor_result, dict) or "vendor" not in vendor_result:
        raise ValueError("Pass the dict returned by single_vendor(...) as the second argument.")
    v = lines[(lines.vendor == vendor_result["vendor"]) & lines[basis].notna() & (~lines.excluded_from_ranking)]
    common = sorted(set(v.line) & set(split_df[split_df.winner.notna()].line))
    split_total = float(split_df[split_df.line.isin(common)].annual_value.sum())
    vend_total = float((v[v.line.isin(common)][basis] * v[v.line.isin(common)].annual_qty).sum()) * (1 - vendor_result.get("discount_pct", 0) / 100)
    return {"lines_compared": len(common), "lines_left_out": sorted(set(range(1, 31)) - set(common)),
            "split_total": round(split_total, 0), "vendor_total": round(vend_total, 0),
            "vendor_minus_split": round(vend_total - split_total, 0)}


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


def run_code(code: str, L, V, I, LY=None) -> dict:
    if BANNED.search(code):
        return {"error": "Code used a disallowed operation (imports, files or system access)."}
    import plotly.express as px
    env = {"pd": pd, "np": np, "px": px, "lines": L.copy(), "vendors": V.copy(), "items": I.copy(),
           "cheapest_split": cheapest_split, "single_vendor": single_vendor, "same_lines_comparison": same_lines_comparison,
           "vendor_totals": vendor_totals, "last_year": LY.copy() if LY is not None else pd.DataFrame()}
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
    return {"result": _tidy(env["result"]), "fig": env.get("fig"), "export": env.get("export")}


def _tidy(obj):
    """Turn lists of row-dicts into DataFrames, recursively, so tables are shown and summarised properly."""
    if isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
        return pd.DataFrame(obj)
    if isinstance(obj, dict):
        return {k: _tidy(v) for k, v in obj.items()}
    return obj


def _facts_about(df: pd.DataFrame) -> str:
    """Counts code computes so the writer never has to count rows itself."""
    out = [f"(table has {len(df)} rows)"]
    if "winner" in df.columns:
        wins = df["winner"].fillna("NO ELIGIBLE QUOTE").value_counts().to_dict()
        out.append("lines won per vendor: " + ", ".join(f"{k}: {v} lines" for k, v in wins.items()))
        if "annual_value" in df.columns:
            by = df.groupby(df["winner"].fillna("none"))["annual_value"].sum().round(0).to_dict()
            out.append("annual value per winner: " + ", ".join(f"{k}: {fmt_inr(v)}" for k, v in by.items()))
            out.append(f"table total annual value: {fmt_inr(float(df['annual_value'].sum()))}")
    return " | ".join(out)


def fmt_inr(x: float) -> str:
    """₹ amount the way an Indian buyer reads it."""
    a = abs(x)
    sign = "-" if x < 0 else ""
    if a >= 1e7:
        return f"{sign}₹{a / 1e7:.2f} Cr"
    if a >= 1e5:
        return f"{sign}₹{a / 1e5:.2f} lakh"
    return f"{sign}₹{a:,.2f}"


def _annotate_money(obj, key=""):
    """Add ready-to-quote crore/lakh strings next to big amounts so the writer never converts units itself."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out[k] = _annotate_money(v, k)
            if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool) and abs(float(v)) >= 1e5 \
                    and not set(str(k).lower().replace("-", "_").split("_")) & {"qty", "quantity", "count", "line", "lines", "n"}:
                out[f"{k}__say_as"] = fmt_inr(float(v))
        return out
    if isinstance(obj, (list, tuple)):
        return [_annotate_money(v) for v in obj]
    return obj


def _render(result) -> str:
    if isinstance(result, dict):
        result = _annotate_money(result)
    if isinstance(result, dict) and any(isinstance(v, (pd.DataFrame, pd.Series)) for v in result.values()):
        parts = []
        for k, v in result.items():
            parts.append(f"--- {k} ---\n{_render(v)}")
        return "\n".join(parts)[:14000]
    if isinstance(result, pd.DataFrame):
        return _facts_about(result) + "\n" + result.head(40).to_csv(index=False) + (
            f"... ({len(result) - 40} more rows not shown; use the counts above)" if len(result) > 40 else "")
    if isinstance(result, pd.Series):
        return result.head(40).to_string()
    try:
        return json.dumps(result, default=str, indent=1, ensure_ascii=False)[:6000]
    except Exception:
        return str(result)[:6000]


NUM = re.compile(r"(?<![A-Za-z0-9])(?:₹\s?)?(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(crore|cr|lakh|lakhs|l|%)?(?![A-Za-z0-9])", re.I)


def _numbers_in(obj, acc=None):
    acc = acc if acc is not None else set()
    if isinstance(obj, pd.DataFrame):
        for v in obj.select_dtypes("number").to_numpy().ravel():
            if pd.notna(v):
                acc.add(float(v))
        for c in obj.columns:
            if not pd.api.types.is_numeric_dtype(obj[c]):
                for v in obj[c].dropna().astype(str):
                    _numbers_in(v, acc)
    elif isinstance(obj, pd.Series):
        _numbers_in(obj.reset_index(), acc)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _numbers_in(v, acc); _numbers_in(str(k), acc)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            _numbers_in(v, acc)
    elif isinstance(obj, (int, float, np.integer, np.floating)) and not isinstance(obj, bool):
        if pd.notna(obj):
            acc.add(float(obj))
    elif isinstance(obj, str):
        for m in NUM.finditer(obj):
            acc.add(float(m.group(1).replace(",", "")))
    return acc


def _frames_in(obj):
    if isinstance(obj, pd.DataFrame):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _frames_in(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _frames_in(v)


def verify_numbers(answer: str, result, question: str = "") -> dict:
    """Check that every figure in the written answer can be found in the computed result (or the question)."""
    known = _numbers_in(result)
    counts = set()   # counts ("N lines") are checked only against real counts, not against any cell value
    for df in _frames_in(result):
        counts.add(float(len(df)))
        for c in df.columns:
            if pd.api.types.is_integer_dtype(df[c]) and any(k in str(c).lower() for k in ("count", "lines", "n_", "num")):
                counts |= {float(v) for v in df[c].dropna().values}
            try:
                if not pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique() <= 12:
                    counts |= {float(v) for v in df[c].fillna("∅").value_counts().values}
            except TypeError:  # columns holding lists
                pass
        if "winner" in df.columns:
            counts.add(float(df["winner"].isna().sum()))
    def _scalar_counts(o):
        if isinstance(o, dict):
            for v in o.values():
                _scalar_counts(v)
        elif isinstance(o, (list, tuple)):
            counts.add(float(len(o)))
            for v in o:
                _scalar_counts(v)
        elif isinstance(o, (int, np.integer)) and not isinstance(o, bool):
            counts.add(float(o))
    _scalar_counts(result if not isinstance(result, pd.DataFrame) else {})
    counts |= _numbers_in(question)
    known |= _numbers_in(question)
    known |= {abs(k) for k in known}
    unverified, checked = [], 0
    for m in NUM.finditer(answer or ""):
        raw, unit = m.group(1), (m.group(2) or "").lower()
        x = float(raw.replace(",", ""))
        after = (answer[m.end():m.end() + 12] or "").lower()
        is_count = bool(re.match(r"\s*(lines?|items?|vendors?|of the|out of)\b", after))
        if x <= 31 and not unit and "." not in raw and not is_count:   # line numbers, dates, small integers
            continue
        if is_count:
            checked += 1
            if x not in counts:
                word = re.sub(r"[^a-z]", "", after.split()[0]) if after.split() else ""
                unverified.append(f"{m.group(0).strip()} {word}".strip())
            continue
        mult = {"crore": 1e7, "cr": 1e7, "lakh": 1e5, "lakhs": 1e5, "l": 1e5}.get(unit, 1)
        val = x * mult
        checked += 1
        tol = 0.006 * abs(val) if mult > 1 else max(0.011, 0.0005 * abs(val))
        if not any(abs(val - k) <= tol or abs(x - k) <= 0.011 for k in known):
            unverified.append(m.group(0).strip())
    return {"checked": checked, "unverified": unverified}


def ask(question: str, lines: pd.DataFrame, vendors: pd.DataFrame, items: list[dict], history: list[dict] | None = None,
        on_status=None, vendor_facts: str = "", last_year: pd.DataFrame | None = None) -> dict:
    L, V, I = _safe_frames(lines, vendors, items)
    LY = None
    if last_year is not None and not last_year.empty:
        LY = pd.DataFrame({
            "line": pd.to_numeric(last_year["line_no"], errors="coerce").astype("Int64"),
            "ly_item": last_year.get("item"),
            "ly_bf": last_year.get("bursting_factor_bf"),
            "ly_annual_qty": pd.to_numeric(last_year.get("annual_qty"), errors="coerce"),
            "ly_price_inr": pd.to_numeric(last_year["price_inr_ex_gst"], errors="coerce"),
        })
    hist = ""
    for h in (history or [])[-4:]:
        hist += f"Q: {h['q']}\nA (summary): {h.get('answer','')[:400]}\n"
    context = (f"Sample of `lines` (first 8 rows):\n{L.head(8).to_csv(index=False)}\n"
               f"`vendors` (all rows):\n{V.to_csv(index=False)}\n"
               f"Previous conversation:\n{hist or '(none)'}\n\nQUESTION: {question}")
    plan = complete_json(PLAN_SYSTEM, [Part(text=context)], max_tokens=6000, fast=True, on_status=on_status).data
    out = run_code(plan.get("code", ""), L, V, I, LY)
    for _ in range(2):  # self-correction: show the model its real error and let it fix the code
        if "error" not in out:
            break
        if on_status:
            on_status("calculation hit an error, fixing it…")
        fix_ctx = context + f"\n\nYour previous code:\n{plan.get('code')}\n\nIt failed with:\n{out['error']}\nFix it."
        plan = complete_json(PLAN_SYSTEM, [Part(text=fix_ctx)], max_tokens=6000, fast=True, on_status=on_status).data
        out = run_code(plan.get("code", ""), L, V, I, LY)
    computed = out.get("error") and f"ERROR: {out['error']}" or _render(out["result"])
    ans = complete_json(ANSWER_SYSTEM, [Part(text=(
        f"QUESTION: {question}\nINTERPRETATION: {plan.get('interpretation')}\n"
        f"ASSUMPTIONS: {plan.get('assumptions')}\nCOMPUTED RESULTS:\n{computed}\n\n"
        f"VENDOR FACTS (from the evaluation, use to explain WHY, e.g. why a vendor is or isn't eligible):\n{vendor_facts or '(none)'}"
        ))], max_tokens=3000, fast=True, on_status=on_status).data
    check = verify_numbers(ans.get("answer_markdown", ""), {"r": out.get("result"), "facts": vendor_facts}, question)
    return {"question": question, "plan": plan, "result": out.get("result"), "fig": out.get("fig"),
            "export": out.get("export"), "error": out.get("error"), "answer": ans, "number_check": check}
