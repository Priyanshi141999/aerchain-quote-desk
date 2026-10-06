"""Score the extraction against the answer key.

Usage:  LLM_PROVIDER=gemini python eval/run_eval.py [--cache] [--only A,B]
Writes eval/out/report_<provider>.md and prints a summary. The app itself never reads the answer key.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quotedesk import llm  # noqa: E402
from quotedesk.pipeline import run_all  # noqa: E402

TOL = 0.02  # within 2% (or ₹0.05) counts as correct


def load_key():
    with open(ROOT / "eval/answer_key/answer_key_prices.csv") as f:
        return {(r["vendor"], int(r["line_no"])): r for r in csv.DictReader(f)}


def has(line_or_vendor_flags, code):
    return any(f["code"] == code for f in line_or_vendor_flags)


def score_prices(results, key):
    rows, ok = [], 0
    for (v, ln), k in sorted(key.items()):
        if v not in results:
            continue
        L = results[v]["lines_by_id"][ln]
        exp = float(k["true_inr_per_uom_ex_gst"]) if k["true_inr_per_uom_ex_gst"] else None
        got = L["norm_inr"]
        if "likely_typo_10x" in k["edge_case_flags"]:
            good = has(L["flags"], "price_outlier")
            verdict = "flagged as likely typo ✔" if good else f"typo NOT flagged (got {got})"
        elif exp is None:
            good = got is None
            verdict = "correctly not priced" if good else f"invented a price {got}"
        elif got is None:
            good, verdict = False, f"missed (expected {exp})"
        else:
            good = abs(got - exp) <= max(TOL * exp, 0.05)
            verdict = "ok" if good else f"wrong: got {got}, expected {exp}"
        ok += good
        rows.append((v, ln, k["item"][:32], exp, got, L["confidence"], good, verdict, " → ".join(L["trail"])[-160:]))
    return ok, rows


def edge_checks(R):
    def L(v, n):
        return R[v]["lines_by_id"][n]

    def VF(v):
        return R[v]["vendor_flags"]

    def Q(v, q):
        return R[v]["qualification"]["questions"][q]["status"]

    checks = [
        ("A", "USD converted to INR", lambda: has(L("A", 4)["flags"], "currency_converted")),
        ("A", "Slab pricing detected (lines 1, 2, 16)", lambda: all(has(L("A", n)["flags"], "tiered_pricing") for n in (1, 2, 16))),
        ("A", "Freight conflict email vs Excel flagged", lambda: has(VF("A"), "document_conflict")),
        ("A", "Hidden superseded row ignored (line 7 correct)", lambda: has(VF("A"), "hidden_rows")),
        ("A", "Currency clause flagged", lambda: has(VF("A"), "currency_risk")),
        ("B", "GST-inclusive prices de-taxed", lambda: has(L("B", 1)["flags"], "gst_removed")),
        ("B", "Per-100 units converted (line 21)", lambda: L("B", 21)["norm_inr"] is not None and L("B", 21)["norm_inr"] < 20),
        ("B", "Hidden 'rank us L1' instruction caught", lambda: has(VF("B"), "manipulation_attempt")),
        ("B", "Line 13 typo flagged, excluded from ranking", lambda: has(L("B", 13)["flags"], "price_outlier")),
        ("B", "Conditional 5% discount found", lambda: has(VF("B"), "conditional_discount")),
        ("B", "Expired ISO certificate → Q1 fails", lambda: Q("B", "Q1") == "no"),
        ("B", "Escalation clause flagged", lambda: has(VF("B"), "price_not_firm")),
        ("B", "Freight per box computed from truck rate", lambda: (L("B", 4)["freight_inr"] or 0) > 0),
        ("C", "Lines 19, 28, 29 not quoted", lambda: all(L("C", n)["norm_inr"] is None for n in (19, 28, 29))),
        ("C", "Line 25 'rate on request' not priced", lambda: L("C", 25)["norm_inr"] is None),
        ("C", "Merged partition price flagged", lambda: has(L("C", 21)["flags"], "merged_lines") or has(L("C", 22)["flags"], "merged_lines")),
        ("C", "Price range on line 3 flagged", lambda: has(L("C", 3)["flags"], "price_range")),
        ("C", "Spec deviation on line 10 flagged", lambda: has(L("C", 10)["flags"], "spec_deviation")),
        ("C", "Plate/die one-time charges captured", lambda: has(VF("C"), "one_time_charges")),
        ("C", "Offer expired flagged", lambda: has(VF("C"), "offer_expired")),
        ("C", "45-day payment → Q8 fails", lambda: Q("C", "Q8") == "no"),
        ("C", "ISO only 'applied' → Q1 not passed", lambda: Q("C", "Q1") in ("no", "pending", "partial", "not_answered")),
        ("D", "Handwritten correction used (line 5)", lambda: abs((L("D", 5)["norm_inr"] or 0) - 42.81) < 0.06),
        ("D", "Handwritten correction used (line 18)", lambda: abs((L("D", 18)["norm_inr"] or 0) - 62.64) < 0.06),
        ("D", "Per-sq.ft pads converted (line 25)", lambda: has(L("D", 25)["flags"], "converted_from_area")),
        ("D", "Lines 11, 30 not quoted", lambda: all(L("D", n)["norm_inr"] is None for n in (11, 30))),
        ("D", "Late submission flagged", lambda: has(VF("D"), "late_submission")),
        ("D", "Certificate name mismatch → Q1 review", lambda: Q("D", "Q1") == "partial"),
        ("D", "Freight 'at actuals' flagged", lambda: has(VF("D"), "freight_unknown")),
        ("E", "Revised 5-ply rate ₹44/kg used (line 4)", lambda: abs((L("E", 4)["norm_inr"] or 0) - 35.24) < 0.2),
        ("E", "Per-kg converted with weight assumption", lambda: has(L("E", 1)["flags"], "converted_from_per_kg")),
        ("E", "'Same as last year' resolved from contract (line 11)", lambda: has(L("E", 11)["flags"], "inferred_from_previous_contract")),
        ("E", "Freight per trip without truck size flagged", lambda: has(VF("E"), "freight_unknown")),
        ("E", "Questionnaire not answered → not qualified", lambda: R["E"]["qualification"]["overall"] == "not_qualified"),
        ("*", "Qualification: A qualified", lambda: R["A"]["qualification"]["overall"] == "qualified"),
        ("*", "Qualification: B not qualified", lambda: R["B"]["qualification"]["overall"] == "not_qualified"),
        ("*", "Qualification: C not qualified", lambda: R["C"]["qualification"]["overall"] == "not_qualified"),
        ("*", "Qualification: D conditional", lambda: R["D"]["qualification"]["overall"] == "conditional"),
    ]
    out = []
    for v, name, fn in checks:
        if v != "*" and v not in R:
            continue
        try:
            out.append((v, name, bool(fn())))
        except Exception as e:  # missing vendor etc.
            out.append((v, name, False))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", action="store_true", help="reuse saved AI transcriptions instead of calling the model")
    ap.add_argument("--only", default="", help="comma-separated vendor keys, e.g. A,B")
    a = ap.parse_args()
    only = [x.strip() for x in a.only.split(",") if x.strip()] or None
    out = ROOT / "eval/out"
    print(f"Provider: {llm.provider()}")
    R = run_all(ROOT / "data", out, use_cache=a.cache, only=only, pause=2)
    key = load_key()
    ok, rows = score_prices(R, key)
    total = len(rows)
    edges = edge_checks(R)
    eok = sum(1 for e in edges if e[2])
    if not R:
        print("No vendor could be processed (see errors above)."); sys.exit(1)
    model = ", ".join(sorted({v["meta"].get("model") or "?" for v in R.values()}))
    skipped = [k for k in "ABCDE" if k not in R and (not only or k in only)]

    md = [f"# Extraction accuracy report — {llm.provider()} ({model})\n",
          f"**Prices: {ok}/{total} correct ({ok / total:.0%})** · **Edge cases handled: {eok}/{len(edges)}**"
          + (f" · ⚠️ vendors not processed: {skipped}" if skipped else "") + "\n",
          "## Per vendor", "| Vendor | Prices correct | Time (s) |", "|---|---|---|"]
    for v in R:
        vr = [r for r in rows if r[0] == v]
        md.append(f"| {v} {R[v]['name']} | {sum(r[6] for r in vr)}/{len(vr)} | {R[v]['meta'].get('seconds')} |")
    md += ["\n## Edge cases", "| Vendor | Check | Result |", "|---|---|---|"]
    md += [f"| {v} | {n} | {'✅' if p else '❌'} |" for v, n, p in edges]
    md += ["\n## Price errors", "| Vendor | Line | Item | Expected | Got | Confidence | Verdict | Trail |", "|---|---|---|---|---|---|---|---|"]
    md += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[7]} | {r[8]} |" for r in rows if not r[6]]
    md += ["\n## Vendor-level flags raised"]
    for v in R:
        md.append(f"**{v} {R[v]['name']}** — qualification: {R[v]['qualification']['overall']}")
        for f in R[v]["vendor_flags"]:
            md.append(f"- [{f['severity']}] {f['code']}: {f['message']}")
        for q, s in R[v]["qualification"]["questions"].items():
            if s["must_pass"]:
                md.append(f"  - {q}: {s['status']} — {s['reason']}")
    report = "\n".join(md)
    (out / f"report_{llm.provider()}.md").write_text(report)
    print(f"\nPRICES {ok}/{total} ({ok / total:.0%}) | EDGE CASES {eok}/{len(edges)}")
    for v, n, p in edges:
        if not p:
            print(f"  ❌ {v}: {n}")


if __name__ == "__main__":
    main()
