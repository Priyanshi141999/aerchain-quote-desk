# Extraction accuracy report — gemini (gemini-3.5-flash-lite)

**Prices: 65/90 correct (72%)** · **Edge cases handled: 20/25**

## Per vendor
| Vendor | Prices correct | Time (s) |
|---|---|---|
| C VIJAY BOX WORKS | 30/30 | 41.8 |
| D Sri Murugan Corrugated Boxes | 30/30 | 41.3 |
| E Annapurna Packers | 5/30 | 39.1 |

## Edge cases
| Vendor | Check | Result |
|---|---|---|
| C | Lines 19, 28, 29 not quoted | ✅ |
| C | Line 25 'rate on request' not priced | ✅ |
| C | Merged partition price flagged | ✅ |
| C | Price range on line 3 flagged | ✅ |
| C | Spec deviation on line 10 flagged | ✅ |
| C | Plate/die one-time charges captured | ✅ |
| C | Offer expired flagged | ✅ |
| C | 45-day payment → Q8 fails | ✅ |
| C | ISO only 'applied' → Q1 not passed | ✅ |
| D | Handwritten correction used (line 5) | ✅ |
| D | Handwritten correction used (line 18) | ✅ |
| D | Per-sq.ft pads converted (line 25) | ✅ |
| D | Lines 11, 30 not quoted | ✅ |
| D | Late submission flagged | ✅ |
| D | Certificate name mismatch → Q1 review | ✅ |
| D | Freight 'at actuals' flagged | ✅ |
| E | Revised 5-ply rate ₹44/kg used (line 4) | ❌ |
| E | Per-kg converted with weight assumption | ❌ |
| E | 'Same as last year' resolved from contract (line 11) | ✅ |
| E | Freight per trip without truck size flagged | ✅ |
| E | Questionnaire not answered → not qualified | ❌ |
| * | Qualification: A qualified | ❌ |
| * | Qualification: B not qualified | ❌ |
| * | Qualification: C not qualified | ✅ |
| * | Qualification: D conditional | ✅ |

## Price errors
| Vendor | Line | Item | Expected | Got | Confidence | Verdict | Trail |
|---|---|---|---|---|---|---|---|
| E | 1 | Kettle 1.5L unit carton | 7.11 | 7.42 | medium | wrong: got 7.42, expected 7.11 | Vendor wrote "38" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹7.42 per piece |
| E | 2 | Steam iron unit carton | 5.66 | 6.51 | medium | wrong: got 6.51, expected 5.66 | Vendor wrote "38" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹6.51 per piece |
| E | 3 | Hair dryer retail carton (printe | 4.33 | 6.22 | medium | wrong: got 6.22, expected 4.33 | Vendor wrote "38" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹6.22 per piece |
| E | 4 | Mixer grinder 500W unit carton | 35.24 | 33.84 | medium | wrong: got 33.84, expected 35.24 | Vendor wrote "44/kg" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹33.84 per piece |
| E | 5 | Mixer grinder 750W unit carton | 40.61 | 37.29 | medium | wrong: got 37.29, expected 40.61 | Vendor wrote "44/kg" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹37.29 per piece |
| E | 6 | Mixer grinder master carton (2 u | 69.61 | 65.36 | medium | wrong: got 65.36, expected 69.61 | Vendor wrote "44/kg" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹65.36 per piece |
| E | 7 | Induction cooktop unit carton | 26.66 | 25.85 | medium | wrong: got 25.85, expected 26.66 | Vendor wrote "44/kg" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹25.85 per piece |
| E | 8 | Pressure cooker 3L carton | 10.53 | 11.25 | medium | wrong: got 11.25, expected 10.53 | Vendor wrote "38" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹11.25 per piece |
| E | 9 | Pressure cooker 5L carton | 29.79 | 28.76 | medium | wrong: got 28.76, expected 29.79 | Vendor wrote "44/kg" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹28.76 per piece |
| E | 10 | RO water purifier carton | 55.62 | 52.82 | medium | wrong: got 52.82, expected 55.62 | Vendor wrote "44/kg" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹52.82 per piece |
| E | 12 | Ceiling fan blade carton | 31.68 | 30.02 | medium | wrong: got 30.02, expected 31.68 | Vendor wrote "44/kg" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹30.02 per piece |
| E | 13 | Ceiling fan motor carton | 35.24 | 33.34 | medium | wrong: got 33.34, expected 35.24 | Vendor wrote "44/kg" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹33.34 per piece |
| E | 14 | Table fan carton | 37.93 | 35.84 | medium | wrong: got 35.84, expected 37.93 | Vendor wrote "44/kg" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹35.84 per piece |
| E | 15 | Toaster unit carton | 8.36 | 9.14 | medium | wrong: got 9.14, expected 8.36 | Vendor wrote "38" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹9.14 per piece |
| E | 16 | Spares shipper - small (plain) | 6.69 | 6.51 | medium | wrong: got 6.51, expected 6.69 | Vendor wrote "38" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹6.51 per piece |
| E | 17 | Spares shipper - medium (plain) | 15.62 | 15.21 | medium | wrong: got 15.21, expected 15.62 | Vendor wrote "38" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹15.21 per piece |
| E | 18 | E-commerce outer carton - large | 61.47 | 57.78 | medium | wrong: got 57.78, expected 61.47 | Vendor wrote "44/kg" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹57.78 per piece |
| E | 20 | Accessory kit mailer, die-cut (p | 3.8 | None | low | missed (expected 3.8) |  |
| E | 21 | Partition, 12-cell (kettle maste | 7.41 | 7.96 | medium | wrong: got 7.96, expected 7.41 | Vendor wrote "38" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹7.96 per set |
| E | 22 | Partition, 6-cell (spares) | 4.56 | 5.19 | medium | wrong: got 5.19, expected 4.56 | Vendor wrote "38" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹5.19 per set |
| E | 23 | Die-cut insert tray - mixer jar | 5.28 | 5.89 | medium | wrong: got 5.89, expected 5.28 | Vendor wrote "38" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹5.89 per piece |
| E | 24 | Die-cut insert - induction cookt | 3.88 | None | low | missed (expected 3.88) |  |
| E | 25 | Layer pad 1200 x 1000 mm | 21.13 | 20.57 | medium | wrong: got 20.57, expected 21.13 | Vendor wrote "38" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹20.57 per piece |
| E | 26 | Layer pad 800 x 600 mm | 8.44 | 8.21 | medium | wrong: got 8.21, expected 8.44 | Vendor wrote "38" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹8.21 per piece |
| E | 27 | Corner protector pad 150 x 150 m | 0.88 | 1.57 | medium | wrong: got 1.57, expected 0.88 | Vendor wrote "44/kg" → looked up FY25-26 contract KHA/PKG/CT/2025-26/003: ₹1.57 per piece |

## Vendor-level flags raised
**C VIJAY BOX WORKS** — qualification: not_qualified
- [blocker] offer_expired: Offer validity ended 01 Oct 2026; today is 06 Oct 2026. Ask vendor to extend before award.
- [warning] payment_terms_deviation: Payment 45 days vs required 60.
- [info] one_time_charges: One-time: Printing plate charges ₹2,500 per colour per design
- [info] one_time_charges: One-time: Die charges ₹8,000 per die
- [warning] partial_quote: Priced 26 of 30 lines. No usable price for lines [19, 25, 28, 29].
  - Q1: no — Certificate not yet available; audit is scheduled in November 2026.
  - Q2: partial — Vendor states they will share test reports later, not provided with quote.
  - Q8: no — Asks for 45 days; requirement is 60.
**D Sri Murugan Corrugated Boxes** — qualification: conditional
- [blocker] late_submission: Last message received 02 Oct 11:40, 18 h after the deadline (01 Oct 18:00). Accepting it is the buyer's decision.
- [warning] freight_unknown: Freight is extra but cannot be calculated per unit; landed cost is incomplete.
- [info] revised_quote: Revision: Rate for line item 5 (Mixer grinder 750W unit carton) changed from 44.50 to 42.81 (earlier: 44.50; later: 42.81)
- [info] revised_quote: Revision: Rate for line item 18 (E-commerce outer carton) changed from 64.00 to 62.64 (earlier: 64.00; later: 62.64)
- [warning] partial_quote: Priced 28 of 30 lines. No usable price for lines [11, 30].
  - Q1: partial — Certificate is issued to 'Murugan Packaging Industries', not 'Sri Murugan Corrugated Boxes' (name match 50%). Possibly a sister company; verify legal entity.
  - Q2: yes — Vendor confirmed providing test reports for every lot.
  - Q8: yes — Accepts 60 days.
**E Annapurna Packers** — qualification: conditional
- [info] multiple_messages: 2 messages from this vendor; the latest values were used.
- [warning] freight_unknown: Freight is extra but cannot be calculated per unit; landed cost is incomplete.
- [info] revised_quote: Revision: 5-ply price per kg (earlier: ₹42/kg; later: ₹44/kg)
- [warning] external_reference: Vendor referred to "rest same as last year" — affects All commercial terms, pricing structure, and questionnaire responses.
- [warning] external_reference: Vendor referred to "Questionnaire same as last year, you have all our documents already" — affects Questionnaire responses and certificates.
- [warning] partial_quote: Priced 28 of 30 lines. No usable price for lines [20, 24].
  - Q1: pending — Vendor stated questionnaire is same as last year and documents are already with buyer
  - Q2: pending — Vendor stated questionnaire is same as last year
  - Q8: pending — Vendor stated questionnaire is same as last year