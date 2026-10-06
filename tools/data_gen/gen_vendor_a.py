import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from spec import ITEMS, BUYER, PLY_GROUP
from truth import TRUTH, VENDORS, A_VENDOR_FX

OUT = "/home/claude/aerchain/dataset/vendors/A_siam_pacific"
os.makedirs(OUT, exist_ok=True)

def inch(mm):
    return round(mm / 25.4, 1)

def desc(it):
    # Vendor's own wording; dims converted to inches, no buyer item names for most rows
    d = it["dims"]
    if it["form"] == "RSC":
        L, W, H = [int(x) for x in d.split(" mm")[0].split(" x ")]
        word = {"3-ply": "3 Ply RSC Box", "5-ply": "5 Ply RSC Carton", "7-ply": "7 Ply Heavy Duty RSC"}[PLY_GROUP[it["board"]]]
        pr = "Plain" if it["print_colours"] == 0 else f"{it['print_colours']}C Flexo"
        return f"{word} {inch(L)}\" x {inch(W)}\" x {inch(H)}\" ID, {pr}", f"{inch(L)}x{inch(W)}x{inch(H)}"
    custom = {
        20: ("E-Flute Die Cut Mailer, 4C print, 9.8\"x7.1\"x2.8\"", "9.8x7.1x2.8"),
        21: ("Partition 12 Cell (for 18.1\"x15\"x10.2\" box)", "set"),
        22: ("Partition 6 Cell (for 17.7\"x11.8\"x9.8\" box)", "set"),
        23: ("Die Cut Jar Cradle, flat 20.5\"x18.9\"", "20.5x18.9"),
        24: ("E-Flute Die Cut Insert, flat 22\"x16.5\"", "22x16.5"),
        25: ("Corrugated Layer Pad 47.2\"x39.4\"", "47.2x39.4"),
        26: ("Corrugated Layer Pad 31.5\"x23.6\"", "31.5x23.6"),
        27: ("Corner Pad 5.9\"x5.9\" V-notch 5 Ply", "5.9x5.9"),
        28: ("SF Roll 39.4\" wide x 164 ft", "roll"),
        29: ("SF Roll 47.2\" wide x 164 ft", "roll"),
        30: ("7 Ply Base Tray, flat 46.5\"x31.5\"", "46.5x31.5"),
    }
    return custom[it["id"]]

thin = Side(style="thin", color="999999")
box = Border(left=thin, right=thin, top=thin, bottom=thin)
HDR = PatternFill("solid", fgColor="0B3D2E")
SEC = PatternFill("solid", fgColor="D9EAD3")

wb = Workbook()
ws = wb.active; ws.title = "Offer"
ws.merge_cells("A1:J1"); ws["A1"] = "SIAM PACIFIC PACKAGING (INDIA) PVT LTD"; ws["A1"].font = Font(bold=True, size=16, color="0B3D2E")
ws.merge_cells("A2:J2"); ws["A2"] = "A member of the Siam Pacific Group, Bangkok | Plot B-7, SIPCOT Industrial Park, Sriperumbudur 602105 | GSTIN 33AAKCS8812R1ZQ"
ws.merge_cells("A3:J3"); ws["A3"] = "COMMERCIAL OFFER - CORRUGATED PACKAGING"; ws["A3"].font = Font(bold=True, size=13)
ws["A4"] = "Customer:"; ws["B4"] = BUYER["name"]
ws["A5"] = "Your Ref:"; ws["B5"] = BUYER["rfq_no"]; ws["F5"] = "Offer No:"; ws["G5"] = "SPPI/BLR/OF/26-0917"
ws["A6"] = "Date:"; ws["B6"] = "29-Sep-2026"; ws["F6"] = "Currency:"; ws["G6"] = "USD (see T&C clause 4)"
for r in (4, 5, 6):
    ws[f"A{r}"].font = Font(bold=True); ws[f"F{r}"].font = Font(bold=True)

hdr = ["S.No", "SPP Code", "Cust. Ref", "Description", "Size (inch)", "Board", "BF", "Price USD per 1000\n(upto 1,00,000 pcs)", "Price USD per 1000\n(above 1,00,000 pcs)", "Remarks"]
ws.merge_cells("H8:I8"); ws["H8"] = "PRICE (FOR Hosur, ex-GST)"; ws["H8"].alignment = Alignment(horizontal="center"); ws["H8"].font = Font(bold=True)
for c, h in enumerate(hdr, 1):
    cell = ws.cell(row=9, column=c, value=h)
    cell.font = Font(bold=True, color="FFFFFF"); cell.fill = HDR; cell.alignment = Alignment(wrap_text=True, vertical="center"); cell.border = box
ws.row_dimensions[9].height = 42

row = 10
sno = 1
hidden_rows = []
groups = [("3-PLY", "3-ply"), ("5-PLY", "5-ply"), ("7-PLY", "7-ply"), ("2-PLY / SINGLE FACE ROLLS", "2-ply")]
for title, ply in groups:
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=10)
    c = ws.cell(row=row, column=1, value=f"SECTION: {title}"); c.font = Font(bold=True); c.fill = SEC
    row += 1
    items = [it for it in ITEMS if PLY_GROUP[it["board"]] == ply]
    # vendor sorts by its own code, not buyer line order
    items.sort(key=lambda it: (it["form"] != "RSC", -it["weight_kg"]))
    for it in items:
        t = TRUTH["A"][it["id"]]
        d, size = desc(it)
        code = f"SPP-{ply[0]}{'R' if it['form']=='RSC' else 'D'}-{100 + it['id'] * 7}"
        ref = f"L-{it['id']}" if it["id"] % 3 == 0 else ""  # only some rows carry buyer ref
        if it["uom"] == "roll":
            p1, p2, rem = None, None, f"USD {t['raw']:.2f} per roll"
        elif "raw_tier2" in t:
            p1, p2, rem = t["raw"], t["raw_tier2"], "Slab pricing"
        else:
            p1, p2, rem = t["raw"], t["raw"], ""
        if it["uom"] == "set":
            rem = "per 1000 sets"
        if it["id"] == 7:
            # hidden superseded row placed just above the live one
            old = [sno, code, ref, d + " (OLD RATE - superseded)", size, it["board"], it["bf"], t["hidden_old_raw"], t["hidden_old_raw"], "Superseded 26-Sep"]
            for ci, v in enumerate(old, 1):
                ws.cell(row=row, column=ci, value=v).border = box
            hidden_rows.append(row); row += 1
        vals = [sno, code, ref, d, size, it["board"], it["bf"] or "-", p1, p2, rem]
        for ci, v in enumerate(vals, 1):
            cell = ws.cell(row=row, column=ci, value=v); cell.border = box
            if ci in (8, 9) and v is not None:
                cell.number_format = "#,##0.0"
        sno += 1; row += 1
    ws.cell(row=row, column=4, value=f"Sub-total {title}: {len(items)} items").font = Font(italic=True)
    row += 1

for r in hidden_rows:
    ws.row_dimensions[r].hidden = True

row += 1
ws.cell(row=row, column=4, value="TOTAL ITEMS OFFERED").font = Font(bold=True)
ws.cell(row=row, column=5, value=30).font = Font(bold=True)
row += 2
notes = [
    "Notes:",
    "1. Prices are FOR Hosur plant, packed on pallets. GST @18% extra as applicable.",
    "2. Slab pricing applies on cumulative annual off-take.",
    f"3. USD prices converted for reference at INR {A_VENDOR_FX:.2f}/USD. See T&C clause 4.",
    "4. Printing plates and dies: no charge for first set.",
]
for n in notes:
    ws.cell(row=row, column=1, value=n).font = Font(bold=(n == "Notes:"), size=9); row += 1

for col, wdt in zip("ABCDEFGHIJ", [5, 13, 8, 46, 13, 10, 5, 16, 16, 18]):
    ws.column_dimensions[col].width = wdt
ws.freeze_panes = "A10"

# --- Terms sheet ---
t = wb.create_sheet("Terms & Conditions")
terms = [
    ("1. Price basis", "FOR Hosur plant, inclusive of freight and unloading."),
    ("2. Taxes", "GST @18% extra."),
    ("3. Payment", "60 days from date of invoice."),
    ("4. Currency", f"Prices quoted in USD. Invoicing in INR at RBI reference rate on invoice date. If INR/USD moves beyond +/-2% of {A_VENDOR_FX:.2f}, price revision to buyer's account."),
    ("5. Validity", "60 days from offer date."),
    ("6. Lead time", "18 days from PO / schedule."),
    ("7. Price firmness", "Firm for 6 months; thereafter linked to IPPTA kraft index, reviewed quarterly."),
    ("8. Tolerance", "Supply quantity +/- 5% per schedule."),
]
t["A1"] = "TERMS & CONDITIONS"; t["A1"].font = Font(bold=True, size=13)
for i, (k, v) in enumerate(terms, 3):
    t[f"A{i}"] = k; t[f"A{i}"].font = Font(bold=True); t[f"B{i}"] = v; t[f"B{i}"].alignment = Alignment(wrap_text=True)
t.column_dimensions["A"].width = 20; t.column_dimensions["B"].width = 100

# --- Questionnaire sheet ---
q = wb.create_sheet("Tech Questionnaire")
qa = [
    ("Q1", "ISO 9001:2015", "Yes. Certificate no. QMS/IN/48812, valid to 14-Feb-2028 (attached as separate PDF)."),
    ("Q2", "Test reports", "Yes, lot-wise BCT, burst and moisture reports with every dispatch."),
    ("Q3", "Capacity", "2,400 MT/month; current utilisation 72%."),
    ("Q4", "Lead time", "18 days."),
    ("Q5", "Paper", "Mixed (60% virgin). FSC certified board available at +6%."),
    ("Q6", "In-house printing", "Yes, 6-colour flexo and 4-colour offset lamination."),
    ("Q7", "Experience", "15 years in India. Customers include two leading kitchen-appliance and AC OEMs (names on NDA)."),
    ("Q8", "Payment 60 days", "Accepted."),
    ("Q9", "GSTIN", "33AAKCS8812R1ZQ"),
    ("Q10", "Rejection replacement", "Yes, within 5 working days at our cost."),
]
q.append(["Q.No", "Topic", "Response"])
for c in q[1]:
    c.font = Font(bold=True, color="FFFFFF"); c.fill = HDR
for r in qa:
    q.append(list(r))
q.column_dimensions["B"].width = 22; q.column_dimensions["C"].width = 100

wb.save(f"{OUT}/SPPI_Offer_KHA_Corrugated_29Sep26.xlsx")

email = f"""From: Arvind Menon <arvind.menon@siampacific.co.in>
To: {BUYER['buyer_name']} <{BUYER['buyer_email']}>
Date: Tue, 29 Sep 2026 16:12:08 +0530
Subject: RE: {BUYER['rfq_no']} - Corrugated packaging annual contract - our offer
Attachments: SPPI_Offer_KHA_Corrugated_29Sep26.xlsx, SPPI_ISO9001_Certificate.pdf

Dear Ms. Raman,

Thank you for the opportunity. Please find attached our commercial offer for all 30 items along with the
technical questionnaire response and our ISO certificate.

Kindly note our prices are in USD as per group policy. Freight will be extra at actuals.

We would be glad to arrange a plant visit to Sriperumbudur at your convenience.

Warm regards,
Arvind Menon
Key Account Manager - South
Siam Pacific Packaging (India) Pvt Ltd
+91 98400 11872
"""
open(f"{OUT}/email.eml", "w").write(email)
print("A done")
