# Extraction accuracy report — gemini (gemini-3.5-flash)

**Prices: 30/30 correct (100%)** · **Edge cases handled: 6/9** · ⚠️ vendors not processed: ['B', 'C', 'D', 'E']

## Per vendor
| Vendor | Prices correct | Time (s) |
|---|---|---|
| A Siam Pacific Packaging (India) Pvt Ltd | 30/30 | 183.1 |

## Edge cases
| Vendor | Check | Result |
|---|---|---|
| A | USD converted to INR | ✅ |
| A | Slab pricing detected (lines 1, 2, 16) | ✅ |
| A | Freight conflict email vs Excel flagged | ✅ |
| A | Hidden superseded row ignored (line 7 correct) | ✅ |
| A | Currency clause flagged | ✅ |
| * | Qualification: A qualified | ✅ |
| * | Qualification: B not qualified | ❌ |
| * | Qualification: C not qualified | ❌ |
| * | Qualification: D conditional | ❌ |

## Price errors
| Vendor | Line | Item | Expected | Got | Confidence | Verdict | Trail |
|---|---|---|---|---|---|---|---|

## Vendor-level flags raised
**A Siam Pacific Packaging (India) Pvt Ltd** — qualification: qualified
- [warning] short_validity: Validity 60 days; RFQ asked for 90.
- [warning] price_not_firm: Price variation clause: Firm for 6 months; thereafter linked to IPPTA kraft index, reviewed quarterly.
- [warning] currency_risk: Currency clause: Prices quoted in USD. Invoicing in INR at RBI reference rate on invoice date. If INR/USD moves beyond +/-2% of 88.20, price revision to buyer's account.
- [info] one_time_charges: One-time: Printing plates and dies (first set) ₹0 set
- [warning] freight_unknown: Freight is extra but cannot be calculated per unit; landed cost is incomplete.
- [blocker] document_conflict: freight: "Price basis: FOR Hosur plant, inclusive of freight and unloading." (SPPI_Offer_KHA_Corrugated_29Sep26.xlsx - Sheet: Terms & Conditions, Row 3) vs "Freight will be extra at actuals." (email.eml). Clarify before award.
- [info] revised_quote: Revision: Price for SPP-5R-149 (Line 7) (earlier: 362.9; later: 339.2)
- [info] hidden_rows: SPPI_Offer_KHA_Corrugated_29Sep26.xlsx has hidden rows ['Offer!row 36']; ignored as superseded.
  - Q1: yes — Valid certificate QMS/IN/48812 until 2028-02-14.
  - Q2: yes — Unconditional agreement to provide reports.
  - Q8: yes — Accepts 60 days.