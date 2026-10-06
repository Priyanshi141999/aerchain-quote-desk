# Extraction accuracy report — gemini (gemini-3.5-flash-lite)

**Prices: 30/30 correct (100%)** · **Edge cases handled: 5/9**

## Per vendor
| Vendor | Prices correct | Time (s) |
|---|---|---|
| E Annapurna Packers | 30/30 | 21.2 |

## Edge cases
| Vendor | Check | Result |
|---|---|---|
| E | Revised 5-ply rate ₹44/kg used (line 4) | ✅ |
| E | Per-kg converted with weight assumption | ✅ |
| E | 'Same as last year' resolved from contract (line 11) | ✅ |
| E | Freight per trip without truck size flagged | ✅ |
| E | Questionnaire not answered → not qualified | ✅ |
| * | Qualification: A qualified | ❌ |
| * | Qualification: B not qualified | ❌ |
| * | Qualification: C not qualified | ❌ |
| * | Qualification: D conditional | ❌ |

## Price errors
| Vendor | Line | Item | Expected | Got | Confidence | Verdict | Trail |
|---|---|---|---|---|---|---|---|

## Vendor-level flags raised
**E Annapurna Packers** — qualification: not_qualified
- [info] multiple_messages: 2 messages from this vendor; the latest values were used.
- [warning] freight_unknown: Freight is extra but cannot be calculated per unit; landed cost is incomplete.
- [info] revised_quote: Revision: 5-ply price per kg (earlier: ₹42/kg; later: ₹44/kg)
- [warning] external_reference: Vendor referred to "rest same as last year" — affects Lines 11, 19, 28, 29, 30 (non 3-ply/5-ply lines).
- [warning] external_reference: Vendor referred to "Questionnaire same as last year, you have all our documents already." — affects All questionnaire items (Q1-Q10).
  - Q1: not_answered — Answered by reference to an earlier submission; no evidence for this RFQ.
  - Q2: not_answered — Answered by reference to an earlier submission; no evidence for this RFQ.
  - Q8: not_answered — Answered by reference to an earlier submission; no evidence for this RFQ.