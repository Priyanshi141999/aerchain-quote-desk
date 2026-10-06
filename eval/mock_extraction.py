"""Build the transcription a *perfect* reader would produce, to test the code path without any AI.
Run: python eval/mock_extraction.py && LLM_PROVIDER=mock python eval/run_eval.py --cache
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/data_gen"))
from truth import TRUTH, VENDORS  # noqa: E402
from spec import ITEMS  # noqa: E402

FOLDER = {"A": "A_siam_pacific", "B": "B_deccan", "C": "C_vijay", "D": "D_sri_murugan", "E": "E_annapurna"}
out = ROOT / "eval/out"; out.mkdir(parents=True, exist_ok=True)

UNIT = {"USD / 1000 pcs": ("USD", 1000, "piece"), "USD / 1000 sets": ("USD", 1000, "set"), "USD / roll": ("USD", 1, "roll"),
        "INR / 100 pcs, incl. 18% GST": ("INR", 100, "piece"), "INR / kg, incl. 18% GST": ("INR", 1, "kg"),
        "INR / pc, incl. 18% GST": ("INR", 1, "piece"), "INR / pc + GST": ("INR", 1, "piece"), "INR / sq.ft": ("INR", 1, "sqft"),
        "INR / kg": ("INR", 1, "kg"), "INR / kg (email)": ("INR", 1, "kg")}

for v, t in TRUTH.items():
    lines = []
    for it in ITEMS:
        r = t[it["id"]]
        L = {"rfq_line": it["id"], "status": "quoted", "price_as_written": str(r["raw"]), "price_value": None,
             "price_value_max": None, "currency": "INR", "price_per_quantity": 1, "price_unit": "piece",
             "gst_treatment": "excluded", "tiers": [], "spec_deviation": None, "shared_price_with_lines": [],
             "superseded_values": [], "source": {"file": "x", "location": "y", "quote": "z"}, "confidence": "high"}
        if r["raw"] is None:
            L["status"] = "not_quoted"
        elif r["raw"] == "Rate on request":
            L["status"] = "price_on_request"
        elif r["raw"] == "same as last year":
            L["status"] = "refers_to_previous_contract"
        else:
            cur, pq, unit = UNIT[r["raw_unit"]]
            L.update(currency=cur, price_per_quantity=pq, price_unit=unit,
                     gst_treatment="included" if "incl" in r["raw_unit"] else "excluded")
            if isinstance(r["raw"], str):  # range
                lo, hi = [float(x) for x in r["raw"].split("-")]
                L.update(price_value=lo, price_value_max=hi)
            else:
                L["price_value"] = r["raw"]
            if "raw_tier2" in r:
                L["tiers"] = [{"min_qty": 0, "max_qty": 100000, "price_value": r["raw"]},
                              {"min_qty": 100001, "max_qty": None, "price_value": r["raw_tier2"]}]
            if "merged_lines" in r["flags"]:
                L["shared_price_with_lines"] = [22 if it["id"] == 21 else 21]
            if "spec_deviation" in r["flags"]:
                L["spec_deviation"] = "18 BF offered instead of 22 BF"
            if "printed_struck" in r:
                L["superseded_values"] = [{"value": str(r["printed_struck"]), "why": "struck through, handwritten correction"}]
        lines.append(L)
    terms = {"A": {"freight": {"basis": "included"}, "payment_days": 60, "validity_days": 60, "currency_clause": "revision beyond ±2%"},
             "B": {"freight": {"basis": "extra_per_trip", "amount": 6500, "truck_payload_kg": 7000}, "gst_rate_percent": 18,
                   "payment_days": 60, "validity_days": 30, "price_firmness": "kraft >5% passed on",
                   "discounts": [{"description": "special", "percent": 5, "condition": "all 30 lines awarded", "source": "footnote"}]},
             "C": {"freight": {"basis": "included"}, "payment_days": 45, "validity_days": 7,
                   "one_time_charges": [{"description": "plates", "amount": 2500, "per": "colour per design", "source": "p6"}]},
             "D": {"freight": {"basis": "extra_at_actuals"}, "payment_days": 60},
             "E": {"freight": {"basis": "extra_per_trip", "amount": 4500}}}[v]
    qd = {"A": "2026-09-29", "B": "2026-09-30", "C": "2026-09-24", "D": "2026-10-01", "E": "2026-09-30"}[v]
    yes = lambda q: {"qid": q, "answered": True, "meets_requirement": "yes", "reason": "ok"}
    qn = {"A": [yes("Q1"), yes("Q2"), yes("Q8")],
          "B": [yes("Q1"), yes("Q2"), yes("Q8")],
          "C": [{"qid": "Q1", "answered": True, "meets_requirement": "no", "reason": "applied"},
                {"qid": "Q2", "answered": True, "meets_requirement": "pending", "reason": "later"}, {"qid": "Q8", "answered": True, "meets_requirement": "no", "reason": "45"}],
          "D": [yes("Q1"), yes("Q2"), yes("Q8")], "E": []}[v]
    certs = {"A": [{"standard": "ISO 9001:2015", "certificate_holder": "Siam Pacific Packaging (India) Pvt Ltd", "valid_until": "2028-02-14", "certificate_no": "48812"}],
             "B": [{"standard": "ISO 9001:2015", "certificate_holder": "Deccan Packaging Industries", "valid_until": "2026-03-31", "certificate_no": "22907"}],
             "D": [{"standard": "ISO 9001:2015", "certificate_holder": "Murugan Packaging Industries", "valid_until": "2028-08-09", "certificate_no": "39150"}]}.get(v, [])
    ex = {"vendor": {"legal_name": VENDORS[v]["name"], "quote_date": qd}, "lines": lines, "commercial_terms": terms,
          "questionnaire": qn, "certificates": certs,
          "conflicts": [{"topic": "freight", "statement_a": "extra", "source_a": "email", "statement_b": "included", "source_b": "xlsx"}] if v == "A" else [],
          "suspicious_content": [], "revisions": [], "references_outside_documents": []}
    (out / f"raw_{FOLDER[v]}_mock.json").write_text(json.dumps({"extraction": ex, "meta": {"provider": "mock", "model": "perfect-reader", "seconds": 0}}))
print("mock transcriptions written")
