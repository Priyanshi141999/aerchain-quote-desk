"""Turn pipeline results into the two flat tables every screen and the analyst work from."""
from __future__ import annotations

import pandas as pd

SEV_ORDER = {"blocker": 0, "warning": 1, "info": 2}


def line_table(results: dict, items: list[dict], overrides: dict | None = None, disputes: dict | None = None) -> pd.DataFrame:
    overrides = overrides or {}
    disputes = disputes or {}
    item_by = {it["id"]: it for it in items}
    rows = []
    for vk, v in results.items():
        qual = v["qualification"]["overall"]
        for L in v["lines"]:
            it = item_by[L["rfq_line"]]
            price, conf, flags = L["norm_inr"], L["confidence"], list(L["flags"])
            ov = overrides.get(f"{vk}:{it['id']}")
            verification = "unverified"   # read by AI, not yet confirmed by anyone
            if ov:
                src = ov.get("source", "buyer")
                changed = L["norm_inr"] is None or abs((L["norm_inr"] or 0) - ov["value"]) > 0.005
                verification = f"{src}_{'corrected' if changed else 'confirmed'}"
                price, conf = ov["value"], "confirmed"
                # a value confirmed at source settles doubts about the READING; spec/commercial blockers stay
                settled = {"price_outlier", "low_confidence_reading", "converted_from_per_kg", "converted_from_area",
                           "price_range", "unit_unclear", "inferred_from_previous_contract"}
                flags = [f for f in flags if f["code"] not in settled] + [
                    {"code": verification, "severity": "info",
                     "message": f"₹{ov['value']:,.2f} {'confirmed' if not changed else 'set'} by {ov['by']} on {str(ov.get('at',''))[:10]} ({ov['reason']})"}]
            dp = disputes.get(f"{vk}:{it['id']}")
            if dp and not ov:
                verification = "vendor_disputed"
                flags = flags + [{"code": "vendor_disputed", "severity": "warning",
                                  "message": f"Vendor says this reading is wrong ({str(dp.get('at', ''))[:10]}): \"{dp['explanation']}\". "
                                             "Review their working and set the value under Inspect any number."}]
            elif dp and ov:
                flags = flags + [{"code": "dispute_resolved", "severity": "info",
                                  "message": f"Vendor's explanation: \"{dp['explanation']}\" — resolved by {ov['by']}."}]
            excluded = bool(L.get("excluded_from_ranking")) and not ov
            fr = L.get("freight_inr")
            rows.append({
                "vendor": vk, "vendor_name": v["name"], "qualification": qual,
                "line": it["id"], "item": it["name"], "board": it["board"], "annual_qty": it["annual_qty"], "uom": it["uom"],
                "status": L["status"] if price is not None or L["status"] != "quoted" else "unclear",
                "price_inr": price,
                "freight_inr": fr,
                "landed_inr": round(price + fr, 2) if (price is not None and fr is not None) else None,
                "annual_value_inr": round(price * it["annual_qty"], 0) if price is not None else None,
                "confidence": conf,
                "verification": verification,
                "excluded_from_ranking": excluded,
                "flag_codes": ",".join(sorted({f["code"] for f in flags})),
                "worst_flag": min((SEV_ORDER[f["severity"]] for f in flags), default=3),
                "flags": flags,
                "as_written": L.get("as_written"),
                "trail": L.get("trail", []),
                "source": L.get("source") or {},
                "freight_note": L.get("freight_note"),
                "vendor_description": L.get("vendor_description"),
            })
    df = pd.DataFrame(rows)
    return df


def vendor_table(results: dict) -> pd.DataFrame:
    rows = []
    for vk, v in results.items():
        ct = (v["extraction"].get("commercial_terms") or {})
        fl = v["vendor_flags"]
        q = v["qualification"]["questions"]
        priced = sum(1 for l in v["lines"] if l["norm_inr"] is not None)
        rows.append({
            "vendor": vk, "vendor_name": v["name"], "qualification": v["qualification"]["overall"],
            **{f"{qid}_status": s["status"] for qid, s in q.items()},
            "lines_priced": priced,
            "payment_days": ct.get("payment_days"), "lead_time_days": ct.get("lead_time_days"),
            "validity_days": ct.get("validity_days"),
            "freight_basis": (ct.get("freight") or {}).get("basis"),
            "discounts": "; ".join(f"{d.get('percent') or ''}% {d.get('condition') or d.get('description')}"
                                   for d in ct.get("discounts") or []) or None,
            "one_time_charges": "; ".join(f"₹{c['amount']:,.0f} {c['description']} {c.get('per','')}"
                                          for c in ct.get("one_time_charges") or []) or None,
            "late_submission": any(f["code"] == "late_submission" for f in fl),
            "offer_expired": any(f["code"] == "offer_expired" for f in fl),
            "blockers": sum(1 for f in fl if f["severity"] == "blocker"),
            "warnings": sum(1 for f in fl if f["severity"] == "warning"),
            "model": v.get("meta", {}).get("model"),
        })
    return pd.DataFrame(rows)


def attention_queue(results: dict, lines: pd.DataFrame) -> list[dict]:
    """Everything a buyer must look at before trusting the comparison, worst first."""
    out = []
    for vk, v in results.items():
        for f in v["vendor_flags"]:
            if f["severity"] in ("blocker", "warning"):
                out.append({"vendor": vk, "vendor_name": v["name"], "line": None, **f})
    for _, r in lines.iterrows():
        for f in r["flags"]:
            if f["severity"] in ("blocker", "warning") and f["code"] not in ("converted_from_per_kg",):
                out.append({"vendor": r["vendor"], "vendor_name": r["vendor_name"], "line": r["line"], **f})
    out.sort(key=lambda x: (SEV_ORDER[x["severity"]], x["vendor"], x["line"] or 0))
    return out
