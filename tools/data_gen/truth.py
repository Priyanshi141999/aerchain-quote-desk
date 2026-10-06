"""What each vendor actually says, and what it means once normalized.

For every vendor x line we keep:
  raw       - the value exactly as it appears in the vendor's document
  raw_unit  - the vendor's own basis (USD/1000 pcs, INR incl GST, per 100, per kg, per sq ft ...)
  norm      - INR per RFQ UoM, ex-GST, ex-freight (the comparable number)
  flags     - edge cases a good system must surface
"""
from spec import ITEMS, base_price, last_year_price, USD_INR_EVAL, GST, PLY_GROUP

SQFT_PER_M2 = 10.7639
BY_ID = {it["id"]: it for it in ITEMS}

VENDORS = {
    "A": {"name": "Siam Pacific Packaging (India) Pvt Ltd", "short": "Siam Pacific", "city": "Sriperumbudur, Chennai",
          "channel": "Email with Excel attachment", "received": "2026-09-29 16:12"},
    "B": {"name": "Deccan Packaging Industries", "short": "Deccan Packaging", "city": "Peenya, Bengaluru",
          "channel": "Email with PDF quotation + ISO certificate", "received": "2026-09-30 19:48"},
    "C": {"name": "Vijay Box Works", "short": "Vijay Box Works", "city": "Hosur",
          "channel": "Email with Word document", "received": "2026-09-24 11:05"},
    "D": {"name": "Sri Murugan Corrugated Boxes", "short": "Sri Murugan", "city": "Krishnagiri",
          "channel": "Email with phone photo of rate card + ISO certificate", "received": "2026-10-02 11:40"},
    "E": {"name": "Annapurna Packers", "short": "Annapurna (incumbent)", "city": "Hoskote, Bengaluru",
          "channel": "Two plain-text emails, no attachment", "received": "2026-09-30 21:17 (revised 2026-10-01 09:02)"},
}

A_VENDOR_FX = 88.20
TRUTH = {v: {} for v in VENDORS}

# ---------------- Vendor A: USD per 1000 pcs, tiered, freight conflict --------------
for it in ITEMS:
    b = base_price("A", it)
    if it["uom"] == "roll":
        usd = round(b / A_VENDOR_FX, 2); unit = "USD / roll"; norm = usd * USD_INR_EVAL
    else:
        usd = round(b * 1000 / A_VENDOR_FX, 1); unit = f"USD / 1000 {'sets' if it['uom']=='set' else 'pcs'}"
        norm = usd / 1000 * USD_INR_EVAL
    rec = {"raw": usd, "raw_unit": unit, "norm": round(norm, 2), "flags": ["currency_usd"]}
    if it["id"] in (1, 2, 16):
        t2 = round(usd * 0.96, 1)
        rec.update(raw_tier2=t2, norm=round(t2 / 1000 * USD_INR_EVAL, 2),
                   tier_note="Slab: up to 1,00,000 pcs vs above 1,00,000 pcs; annual qty > 1 lakh so lower slab used, but slab basis (per PO vs annual) not stated")
        rec["flags"].append("tiered_pricing")
    if it["id"] == 7:
        rec["hidden_old_raw"] = round(usd * 1.07, 1); rec["flags"].append("hidden_row_old_price")
    TRUTH["A"][it["id"]] = rec

# ---------------- Vendor B: INR incl. GST, per-100 & per-kg units, typo, conditional discount -------
for it in ITEMS:
    b = base_price("B", it)
    if it["id"] in (21, 22, 27):
        raw = round(b * (1 + GST) * 100, 0); unit = "INR / 100 pcs, incl. 18% GST"; norm = raw / 100 / (1 + GST)
        flags = ["gst_inclusive", "per_100_units"]
    elif it["uom"] == "roll":
        raw = round(b / it["weight_kg"] * (1 + GST), 2); unit = "INR / kg, incl. 18% GST"; norm = raw / (1 + GST) * it["weight_kg"]
        flags = ["gst_inclusive", "per_kg_needs_weight"]
    else:
        raw = round(b * (1 + GST), 2); unit = "INR / pc, incl. 18% GST"; norm = raw / (1 + GST)
        flags = ["gst_inclusive"]
    rec = {"raw": raw, "raw_unit": unit, "norm": round(norm, 2), "flags": flags}
    if it["id"] == 13:
        rec["raw"] = round(raw / 10, 2)  # misplaced decimal as printed
        rec["flags"] = flags + ["likely_typo_10x"]
        rec["note"] = f"Printed {rec['raw']}; peers ~INR 35-40; probably {raw}"
    TRUTH["B"][it["id"]] = rec

# ---------------- Vendor C: Word letter, 27/30, merged, range, ROR, deviation -------------
C_MISSING = {19, 28, 29}
for it in ITEMS:
    if it["id"] in C_MISSING:
        TRUTH["C"][it["id"]] = {"raw": None, "raw_unit": None, "norm": None, "flags": ["not_quoted"]}
        continue
    b = base_price("C", it)
    rec = {"raw": round(b, 2), "raw_unit": "INR / pc + GST", "norm": round(b, 2), "flags": []}
    if it["id"] in (21, 22):
        rec.update(raw=6.40, norm=6.40, flags=["merged_lines"], note="Single price quoted for both partition types")
    if it["id"] == 3:
        rec.update(raw="7.20 - 7.80", norm=7.80, flags=["price_range"], note="Range depends on final artwork; upper bound used")
    if it["id"] == 25:
        rec.update(raw="Rate on request", norm=None, flags=["price_on_request"])
    if it["id"] == 10:
        rec.update(raw=49.80, norm=49.80, flags=["spec_deviation"], note="Offered 18 BF instead of specified 22 BF")
    TRUTH["C"][it["id"]] = rec
C_ONE_TIME = {"plate_per_colour_per_design": 2500, "die_per_design": 8000}

# ---------------- Vendor D: angled photo, handwritten corrections, per sq ft, per kg, late ---------
D_MISSING = {11, 30}
D_HANDWRITTEN = {5: 44.50, 18: 64.00}  # printed (struck-through) value; handwritten = truth
for it in ITEMS:
    if it["id"] in D_MISSING:
        TRUTH["D"][it["id"]] = {"raw": None, "raw_unit": None, "norm": None, "flags": ["not_quoted"]}
        continue
    b = base_price("D", it)
    if it["id"] in (25, 26):
        sqft = it["area_m2"] * SQFT_PER_M2
        raw = round(b / sqft, 2); unit = "INR / sq.ft"; norm = raw * sqft; flags = ["per_sqft"]
    elif it["uom"] == "roll":
        raw = round(b / it["weight_kg"], 2); unit = "INR / kg"; norm = raw * it["weight_kg"]; flags = ["per_kg_needs_weight"]
    else:
        raw = round(b, 2); unit = "INR / pc + GST"; norm = raw; flags = []
    rec = {"raw": raw, "raw_unit": unit, "norm": round(norm, 2), "flags": flags}
    if it["id"] in D_HANDWRITTEN:
        rec["printed_struck"] = D_HANDWRITTEN[it["id"]]; rec["flags"] = flags + ["handwritten_correction"]
    TRUTH["D"][it["id"]] = rec

# ---------------- Vendor E: per-kg email, "rest same as last year", revision --------------
E_KG = {"3-ply": 38.0, "5-ply": 44.0}
E_KG_V1 = {"3-ply": 38.0, "5-ply": 42.0}
for it in ITEMS:
    ply = PLY_GROUP[it["board"]]
    if ply in E_KG:
        norm = it["weight_kg"] * E_KG[ply]
        rec = {"raw": E_KG[ply], "raw_unit": "INR / kg (email)", "norm": round(norm, 2),
               "flags": ["per_kg_needs_weight", "assumed_rate_covers_all_items_of_ply"],
               "v1_raw": E_KG_V1[ply]}
        if ply == "5-ply":
            rec["flags"].append("revised_quote")
        if it["print_colours"] or it["form"] not in ("RSC", "Pad", "Roll"):
            rec["flags"].append("print_or_diecut_cost_unclear")
    else:
        ly = last_year_price(it)
        rec = {"raw": "same as last year", "raw_unit": "reference to FY25-26 contract", "norm": ly,
               "flags": ["same_as_last_year"]}
    TRUTH["E"][it["id"]] = rec


def freight_per_uom(v, it):
    """Freight INR per UoM where derivable; None where vendor gave no basis."""
    if v == "A":
        return 0.0  # Excel says FOR included (email contradicts)
    if v == "B":
        return round(6500 / 7000 * it["weight_kg"], 2)  # INR 6,500 per 7 MT truck
    if v == "C":
        return 0.0  # free delivery within 25 km
    return None  # D at actuals; E per trip with no payload stated


if __name__ == "__main__":
    for v in VENDORS:
        q = sum(1 for r in TRUTH[v].values() if r["norm"] is not None)
        tot = sum((r["norm"] or 0) * BY_ID[i]["annual_qty"] for i, r in TRUTH[v].items())
        print(v, "priced lines", q, "spend ex-GST ex-freight (cr)", round(tot / 1e7, 3))
