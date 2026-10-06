"""Single source of truth for the fabricated Aerchain demo dataset.

Buyer: Kaveri Home Appliances Pvt Ltd (fictional), Hosur plant.
Category: corrugated packaging, 30 line items, annual contract.
Every vendor document is rendered FROM these numbers, so the answer key is exact.
"""
import math

BUYER = {
    "name": "Kaveri Home Appliances Pvt Ltd",
    "plant": "Plot 42, SIPCOT Phase II, Hosur, Tamil Nadu 635109",
    "buyer_name": "Priya Raman",
    "buyer_title": "Category Manager - Packaging",
    "buyer_email": "priya.raman@kaverihome.in",
    "rfq_no": "KHA/PKG/RFQ/2026-27/014",
    "issued": "2026-09-21",
    "deadline": "2026-10-01 18:00 IST",
    "contract_period": "1 Nov 2026 - 31 Oct 2027",
}

USD_INR_EVAL = 88.50  # buyer's evaluation rate (assumed RBI reference rate, 01-Oct-2026)
GST = 0.18

# Board constructions -> grammage (g/m2). Flute take-up factors B=1.36, C=1.45, E=1.25
BOARD = {
    "2-ply":  {"label": "Single-face, 150 GSM kraft liner / 120 GSM B-flute medium", "gsm": 150 + 120 * 1.36},
    "3-ply B": {"label": "150/120/150 GSM kraft, B-flute", "gsm": 150 + 120 * 1.36 + 150},
    "3-ply E": {"label": "150/100/150 GSM kraft, E-flute (printable white top 150 GSM)", "gsm": 150 + 100 * 1.25 + 150},
    "5-ply BC": {"label": "180/120/120/120/180 GSM kraft, BC-flute", "gsm": 180 + 120 * 1.36 + 120 + 120 * 1.45 + 180},
    "7-ply BCB": {"label": "200/120/150/120/150/120/200 GSM kraft, BCB-flute", "gsm": 200 + 120 * 1.36 + 150 + 120 * 1.45 + 150 + 120 * 1.36 + 200},
}


def rsc_area(L, W, H):
    """Blank area (m2) of a regular slotted carton incl. 35 mm glue flap + 5% trim waste."""
    return ((2 * L + 2 * W + 35) * (H + W)) / 1e6 * 1.05


# id, name, form, board, dims (mm) or area spec, BF, colours, annual qty, UoM, use
_ITEMS = [
    (1, "Kettle 1.5L unit carton", "RSC", "3-ply B", (230, 190, 250), 16, 1, 120000, "piece"),
    (2, "Steam iron unit carton", "RSC", "3-ply B", (310, 150, 170), 16, 2, 150000, "piece"),
    (3, "Hair dryer retail carton (printed)", "RSC", "3-ply E", (260, 110, 220), 18, 4, 90000, "piece"),
    (4, "Mixer grinder 500W unit carton", "RSC", "5-ply BC", (390, 300, 360), 20, 2, 80000, "piece"),
    (5, "Mixer grinder 750W unit carton", "RSC", "5-ply BC", (420, 320, 390), 22, 2, 70000, "piece"),
    (6, "Mixer grinder master carton (2 units)", "RSC", "5-ply BC", (650, 430, 410), 22, 1, 35000, "piece"),
    (7, "Induction cooktop unit carton", "RSC", "5-ply BC", (410, 340, 120), 20, 2, 65000, "piece"),
    (8, "Pressure cooker 3L carton", "RSC", "3-ply B", (280, 260, 250), 18, 2, 100000, "piece"),
    (9, "Pressure cooker 5L carton", "RSC", "5-ply BC", (330, 310, 290), 20, 2, 75000, "piece"),
    (10, "RO water purifier carton", "RSC", "5-ply BC", (480, 330, 560), 22, 2, 40000, "piece"),
    (11, "Air cooler 40L carton", "RSC", "7-ply BCB", (640, 460, 1050), 24, 1, 18000, "piece"),
    (12, "Ceiling fan blade carton", "RSC", "5-ply BC", (1250, 180, 110), 20, 1, 60000, "piece"),
    (13, "Ceiling fan motor carton", "RSC", "5-ply BC", (380, 380, 220), 20, 1, 60000, "piece"),
    (14, "Table fan carton", "RSC", "5-ply BC", (440, 240, 480), 20, 1, 30000, "piece"),
    (15, "Toaster unit carton", "RSC", "3-ply B", (320, 200, 220), 18, 2, 45000, "piece"),
    (16, "Spares shipper - small (plain)", "RSC", "3-ply B", (300, 200, 150), 16, 0, 200000, "piece"),
    (17, "Spares shipper - medium (plain)", "RSC", "3-ply B", (450, 300, 250), 16, 0, 120000, "piece"),
    (18, "E-commerce outer carton - large", "RSC", "5-ply BC", (600, 400, 400), 20, 1, 50000, "piece"),
    (19, "Export master carton - mixer (4 units)", "RSC", "7-ply BCB", (820, 640, 430), 26, 1, 8000, "piece"),
    (20, "Accessory kit mailer, die-cut (printed)", "Die-cut mailer", "3-ply E", (250, 180, 70), 18, 4, 60000, "piece"),
    (21, "Partition, 12-cell (kettle master)", "Partition set", "3-ply B", 0.42, 16, 0, 20000, "set"),
    (22, "Partition, 6-cell (spares)", "Partition set", "3-ply B", 0.26, 16, 0, 30000, "set"),
    (23, "Die-cut insert tray - mixer jar", "Die-cut insert", "3-ply B", 0.30, 16, 0, 80000, "piece"),
    (24, "Die-cut insert - induction cooktop", "Die-cut insert", "3-ply E", 0.24, 18, 0, 65000, "piece"),
    (25, "Layer pad 1200 x 1000 mm", "Pad", "3-ply B", 1.20, 16, 0, 25000, "piece"),
    (26, "Layer pad 800 x 600 mm", "Pad", "3-ply B", 0.48, 16, 0, 40000, "piece"),
    (27, "Corner protector pad 150 x 150 mm, die-cut", "Die-cut pad", "5-ply BC", 0.0250, 20, 0, 140000, "piece"),
    (28, "Single-face corrugated roll 1000 mm x 50 m", "Roll", "2-ply", 50.0, 0, 0, 1500, "roll"),
    (29, "Single-face corrugated roll 1200 mm x 50 m", "Roll", "2-ply", 60.0, 0, 0, 900, "roll"),
    (30, "Air cooler base tray / sleeve, heavy duty", "Die-cut tray", "7-ply BCB", 0.95, 24, 1, 18000, "piece"),
]

ITEMS = []
for iid, name, form, board, dims, bf, col, qty, uom in _ITEMS:
    if isinstance(dims, tuple):
        area = rsc_area(*dims)
        dim_str = f"{dims[0]} x {dims[1]} x {dims[2]} mm (internal, L x W x H)"
    else:
        area = dims
        dim_str = {
            21: "Fits 460 x 380 x 260 mm master; 12 cells; 2 x 5 slotted strips",
            22: "Fits 450 x 300 x 250 mm shipper; 6 cells",
            23: "Flat 520 x 480 mm die-cut, folds to cradle 2 jars",
            24: "Flat 560 x 420 mm die-cut, E-flute",
            25: "1200 x 1000 mm flat sheet",
            26: "800 x 600 mm flat sheet",
            27: "150 x 150 mm flat, 5-ply, die-cut with V-notch",
            28: "1000 mm wide x 50 m long, rolled on 75 mm core",
            29: "1200 mm wide x 50 m long, rolled on 75 mm core",
            30: "Flat 1180 x 800 mm die-cut, folds to 660 x 480 x 200 mm tray",
        }[iid]
    weight = area * BOARD[board]["gsm"] / 1000  # kg
    ITEMS.append({
        "id": iid, "name": name, "form": form, "board": board,
        "construction": BOARD[board]["label"], "dims": dim_str, "bf": bf,
        "print_colours": col, "annual_qty": qty, "uom": uom,
        "area_m2": round(area, 4), "weight_kg": round(weight, 3),
    })

PLY_GROUP = {"2-ply": "2-ply", "3-ply B": "3-ply", "3-ply E": "3-ply", "5-ply BC": "5-ply", "7-ply BCB": "7-ply"}

# ---------------------------------------------------------------------------
# Vendor economics: basic price per UoM in INR, ex-GST, ex-freight.
# price = weight * rate_per_kg[ply] + print_adder * colours + conversion adder
# ---------------------------------------------------------------------------
VENDOR_RATES = {
    # A Siam Pacific: premium MNC, consistent quality
    "A": {"kg": {"2-ply": 54, "3-ply": 46.5, "5-ply": 48.0, "7-ply": 51.5}, "print": 0.55, "diecut": 0.9},
    # B Deccan: aggressive pricer
    "B": {"kg": {"2-ply": 50, "3-ply": 41.0, "5-ply": 43.0, "7-ply": 46.0}, "print": 0.45, "diecut": 0.7},
    # C Vijay: local MSME, cheapest on simple boxes, weaker on printed
    "C": {"kg": {"2-ply": 49, "3-ply": 39.5, "5-ply": 42.5, "7-ply": 47.0}, "print": 0.70, "diecut": 1.1},
    # D Sri Murugan: mid
    "D": {"kg": {"2-ply": 51, "3-ply": 42.5, "5-ply": 44.5, "7-ply": 47.5}, "print": 0.50, "diecut": 0.8},
    # E Annapurna (incumbent): headline per-kg prices in email
    "E": {"kg": {"2-ply": 52, "3-ply": 38.0, "5-ply": 44.0, "7-ply": 49.0}, "print": 0.0, "diecut": 0.0},
}

# small deterministic per-item noise so vendors don't look formulaic
def _noise(vendor, iid):
    seed = (ord(vendor) * 131 + iid * 977) % 1000
    return 1 + ((seed / 1000) - 0.5) * 0.06  # +/-3%


def base_price(vendor, item):
    r = VENDOR_RATES[vendor]
    ply = PLY_GROUP[item["board"]]
    p = item["weight_kg"] * r["kg"][ply]
    p += r["print"] * item["print_colours"]
    if item["form"] not in ("RSC", "Pad", "Roll"):
        p += r["diecut"]
    if vendor != "E":
        p *= _noise(vendor, item["id"])
    return round(p, 2)


# Last year's contract (incumbent Annapurna, FY2025-26), per UoM, INR ex-GST.
# Items 20 and 24 are NEW this year. Item 5 spec changed (20 BF -> 22 BF).
def last_year_price(item):
    if item["id"] in (20, 24):
        return None
    ply = PLY_GROUP[item["board"]]
    ly_kg = {"2-ply": 50, "3-ply": 37.0, "5-ply": 41.0, "7-ply": 47.0}[ply]
    p = item["weight_kg"] * ly_kg + 0.5 * item["print_colours"]
    if item["form"] not in ("RSC", "Pad", "Roll"):
        p += 0.75
    if item["id"] == 5:
        p *= 0.96  # was quoted on 20 BF board last year
    return round(p, 2)


if __name__ == "__main__":
    tot = {}
    for it in ITEMS:
        print(it["id"], it["name"][:34].ljust(34), it["board"], it["weight_kg"],
              *[base_price(v, it) for v in "ABCD"])
    for v in "ABCD":
        tot[v] = sum(base_price(v, it) * it["annual_qty"] for it in ITEMS)
    print({k: round(x / 1e7, 2) for k, x in tot.items()}, "crore")
