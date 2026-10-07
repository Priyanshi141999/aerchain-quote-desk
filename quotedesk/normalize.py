"""Code step: turn what each vendor wrote into comparable numbers, showing every step.

Comparable basis = INR per RFQ unit of measure, excluding GST, excluding freight.
Every conversion appends a human-readable step to `trail`, and every assumption raises a flag.
"""
from __future__ import annotations

import csv
import statistics
from datetime import datetime, date
from pathlib import Path

SQFT_PER_M2 = 10.7639

SETTINGS = {
    "fx": {"USD": 88.50, "EUR": 95.0},  # buyer's evaluation rate (assumed RBI reference rate on deadline day)
    "fx_note": "RBI reference rate assumed for 01-Oct-2026",
    "default_gst": 18.0,
    "deadline": datetime.fromisoformat("2026-10-01T18:00:00+05:30"),
    "evaluation_date": date(2026, 10, 6),  # the day the buyer is comparing quotes
    "required_payment_days": 60,
    "min_validity_days": 90,
    "outlier_low": 0.4,    # price below 40% of other vendors' median -> likely error
    "outlier_high": 2.5,
}

SEV = {"blocker": 3, "warning": 2, "info": 1}


def flag(code, severity, message):
    return {"code": code, "severity": severity, "message": message}


def load_previous_contract(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    with open(path) as f:
        return {int(r["line_no"]): r for r in csv.DictReader(f)}


def _fmt(x):
    return f"₹{x:,.2f}"


def normalize_line(L: dict, item: dict, terms: dict, prev: dict[int, dict]) -> dict:
    trail, flags = [], []
    status = L.get("status") or "unclear"
    conf = L.get("confidence") or "medium"
    out = {"rfq_line": item["id"], "status": status, "norm_inr": None, "trail": trail, "flags": flags,
           "confidence": conf, "source": L.get("source") or {}, "as_written": L.get("price_as_written"),
           "vendor_description": L.get("vendor_description"), "reading_notes": L.get("reading_notes")}

    if status == "refers_to_previous_contract" and L.get("price_value") is not None:
        status = "quoted"  # an explicit price always beats a reference to an old contract
        flags.append(flag("status_corrected", "info", "AI marked this as 'same as last year' but also read an explicit price; the explicit price is used."))
    if status == "refers_to_previous_contract":
        p = prev.get(item["id"])
        if not p:
            out["status"] = "not_quoted"
            flags.append(flag("previous_contract_missing", "warning",
                              "Vendor said 'same as last year', but this line was not in last year's contract (new item)."))
            return out
        val = float(p["price_inr_ex_gst"])
        trail.append(f"Vendor wrote \"{L.get('price_as_written') or 'same as last year'}\" → looked up FY25-26 contract "
                     f"{p['contract_no']}: {_fmt(val)} per {p['uom']}")
        if str(p.get("bursting_factor_bf")) not in ("", str(item["bf"])):
            flags.append(flag("previous_spec_differs", "warning",
                              f"Last year's price was for {p['bursting_factor_bf']} BF; this RFQ asks {item['bf']} BF."))
        flags.append(flag("inferred_from_previous_contract", "warning",
                          "Price inferred from last year's contract, not stated in this quote. Confirm with vendor."))
        out.update(norm_inr=round(val, 2), status="quoted_by_reference", confidence="medium")
        return out

    if status in ("not_quoted", "price_on_request") or L.get("price_value") is None:
        if status == "price_on_request":
            flags.append(flag("price_on_request", "info", "Vendor wrote 'rate on request'; no price to compare."))
        out["status"] = status if status != "quoted" else "unclear"
        return out

    v = float(L["price_value"])
    trail.append(f"As written: {L.get('price_as_written') or v}")

    # price range
    if L.get("price_value_max"):
        hi = float(L["price_value_max"])
        flags.append(flag("price_range", "warning", f"Vendor gave a range {v:g}–{hi:g}; the upper bound is used (conservative)."))
        trail.append(f"Range {v:g}–{hi:g} → use upper bound {hi:g}")
        v = hi

    # slab / tier pricing
    tiers = L.get("tiers") or []
    if tiers:
        q = item["annual_qty"]
        chosen = None
        for t in tiers:
            lo, up = t.get("min_qty") or 0, t.get("max_qty") or float("inf")
            if lo <= q <= up or (lo < q and up == float("inf")):
                chosen = t
        if chosen:
            v = float(chosen["price_value"])
            trail.append(f"Slab pricing: annual qty {q:,} falls in slab {chosen.get('min_qty') or 0:,}–"
                         f"{chosen.get('max_qty') or '∞'} → {v:g}")
        flags.append(flag("tiered_pricing", "info",
                          "Slab pricing: slab chosen on annual quantity. If slabs apply per purchase order, the higher slab applies."))

    # per-quantity basis
    per_q = L.get("price_per_quantity") or 1
    if per_q != 1:
        v = v / per_q
        trail.append(f"÷ {per_q:g} (quoted per {per_q:g}) → {v:,.4f} each")

    # unit conversion to the RFQ unit
    unit = (L.get("price_unit") or "piece").lower()
    if unit == "kg":
        w = item["weight_kg"]
        v = v * w
        how = ""
        if item.get("area_m2"):
            gsm = w * 1000 / item["area_m2"]
            how = f" = {item['area_m2']:.3f} m² of board × {gsm:.0f} g/m² ({item.get('board','')})"
        trail.append(f"× {w:.3f} kg per {item['uom']}{how}, estimated from the RFQ spec → {v:,.2f}")
        flags.append(flag("converted_from_per_kg", "warning",
                          f"Quoted per kg; converted with the estimated weight {w:.3f} kg per {item['uom']} "
                          f"(board area × board grammage from the RFQ spec). The vendor's actual weight may differ — ask them to confirm."))
    elif unit in ("sqft", "sqm"):
        area = item["area_m2"] * (SQFT_PER_M2 if unit == "sqft" else 1)
        v = v * area
        trail.append(f"× {area:.3f} {unit} per {item['uom']} → {v:,.2f}")
        flags.append(flag("converted_from_area", "info", f"Quoted per {unit}; converted using RFQ size ({area:.2f} {unit})."))
    elif unit not in ("piece", "set", "roll", "box", "nos", "no", "each"):
        flags.append(flag("unit_unclear", "warning", f"Vendor unit '{unit}' could not be mapped to {item['uom']}."))
        out["confidence"] = "low"

    # currency
    cur = (L.get("currency") or "INR").upper()
    if cur != "INR":
        fx = SETTINGS["fx"].get(cur)
        if fx:
            v = v * fx
            trail.append(f"× {fx} INR/{cur} ({SETTINGS['fx_note']}) → {_fmt(v)}")
            flags.append(flag("currency_converted", "info", f"Quoted in {cur}; converted at {fx}."))
        else:
            flags.append(flag("currency_unknown", "blocker", f"No exchange rate configured for {cur}."))

    # GST
    if L.get("gst_treatment") == "included":
        rate = terms.get("gst_rate_percent") or SETTINGS["default_gst"]
        v = v / (1 + rate / 100)
        trail.append(f"÷ {1 + rate / 100:.2f} (remove {rate:g}% GST included in price) → {_fmt(v)}")
        flags.append(flag("gst_removed", "info", f"Price included {rate:g}% GST; removed for like-for-like comparison."))

    if L.get("spec_deviation"):
        flags.append(flag("spec_deviation", "blocker", f"Not like-for-like: {L['spec_deviation']}. Excluded from 'cheapest' until the buyer accepts the deviation."))
        out["excluded_from_ranking"] = True
    if L.get("shared_price_with_lines"):
        flags.append(flag("merged_lines", "warning",
                          f"One price given for lines {sorted(set([item['id']] + L['shared_price_with_lines']))} together."))
    for s in L.get("superseded_values") or []:
        flags.append(flag("superseded_value", "info", f"Replaced value {s.get('value')}: {s.get('why')}"))
    if conf == "low":
        flags.append(flag("low_confidence_reading", "warning", L.get("reading_notes") or "AI was not sure of this reading."))

    trail.append(f"= {_fmt(v)} per {item['uom']}, ex-GST, ex-freight")
    out["norm_inr"] = round(v, 2)
    if out["status"] not in ("quoted",):
        out["status"] = "quoted"
    return out


def freight_per_uom(terms: dict, item: dict) -> tuple[float | None, str]:
    fr = (terms or {}).get("freight") or {}
    basis = fr.get("basis") or "not_stated"
    if basis == "included":
        return 0.0, "Freight included (FOR Hosur)"
    if basis == "extra_per_unit" and fr.get("amount") is not None:
        return float(fr["amount"]), f"Freight ₹{fr['amount']} per unit"
    if basis == "extra_per_trip" and fr.get("amount") and fr.get("truck_payload_kg"):
        per_kg = fr["amount"] / fr["truck_payload_kg"]
        return round(per_kg * item["weight_kg"], 2), (f"₹{fr['amount']:,.0f} per trip ÷ {fr['truck_payload_kg']:,.0f} kg payload "
                                                       f"× {item['weight_kg']:.3f} kg")
    if basis == "extra_per_trip":
        return None, f"Freight ₹{fr.get('amount')} per trip, but truck size not stated, cannot spread per box"
    if basis == "extra_at_actuals":
        return None, "Freight extra at actuals, amount unknown"
    if basis == "extra_unspecified":
        return None, "Freight extra, amount not stated"
    return None, "Freight not stated"


def add_outlier_flags(results: dict[str, dict], items: list[dict]):
    """A price far from every other vendor's is more likely a typo than a bargain."""
    for it in items:
        prices = {v: r["lines_by_id"][it["id"]]["norm_inr"] for v, r in results.items()
                  if r["lines_by_id"][it["id"]]["norm_inr"] is not None}
        for v, p in prices.items():
            others = [x for k, x in prices.items() if k != v]
            if len(others) < 2:
                continue
            med = statistics.median(others)
            ratio = p / med if med else 1
            line = results[v]["lines_by_id"][it["id"]]
            if ratio < SETTINGS["outlier_low"] or ratio > SETTINGS["outlier_high"]:
                guess = ""
                for m in (10, 100, 0.1):
                    if 0.8 <= p * m / med <= 1.25:
                        guess = f" A misplaced decimal ({_fmt(p)} → {_fmt(p * m)}) would put it in line with others."
                line["flags"].append(flag("price_outlier", "blocker",
                                          f"{_fmt(p)} is {ratio:.0%} of other vendors' median {_fmt(med)}.{guess} "
                                          "Excluded from 'cheapest' until confirmed."))
                line["confidence"] = "low"
                line["excluded_from_ranking"] = True
