"""RFQ co-pilot: the buyer talks, the AI keeps a structured RFQ draft up to date and asks what's missing."""
from __future__ import annotations

import json

from .llm import Part, complete_json

SYSTEM = """You are an experienced procurement co-pilot helping a category buyer at an Indian manufacturer draft an
RFQ (request for quotation). You maintain a STRUCTURED DRAFT and update it on every turn.

How you work:
- Start from whatever the buyer gives you (last year's contract, an item list, a description). Never discard
  lines the buyer did not ask to remove.
- Apply the buyer's changes precisely (add, remove, upgrade a spec, change quantities).
- For every line, capture what a vendor needs to quote unambiguously: item name, form (RSC box, die-cut, pad,
  partition, roll...), board grade / construction, dimensions with units, quality grade (e.g. BF), print
  colours, annual quantity, unit of measure. For other categories use the equivalent essentials.
- Spot gaps and risks a good buyer would catch (missing dimensions on a new item, ambiguous UoM, no freight
  basis, no quality evidence) and ASK about them, max 3 questions per turn, most important first.
- Propose a supplier questionnaire with must-pass questions where it protects the buyer (certification,
  test reports, payment terms), and commercial terms (price basis, GST, freight, firmness, validity,
  payment, one-time charges, deviations).
- Make sensible assumptions to keep moving, but list each one so the buyer can override it.
- Propose a COMPLETE supplier questionnaire on the first turn: 8-10 questions covering quality certification
  (must-pass, with certificate), test reports (must-pass), capacity and utilisation, lead time, raw material
  source, printing capability, relevant customer references, payment terms (must-pass), tax registration
  (GSTIN) and rejection/replacement policy. For non-packaging categories use the equivalent essentials.
- Commercial terms must be specific: price basis (per unit, ex-GST), delivery basis (FOR buyer plant or freight
  stated separately), price firmness for the contract period, quote validity (90 days), payment days,
  one-time charges quoted separately, partial quotes allowed, deviations declared line-wise.
- Line numbers are the buyer's ITEM CODES. Keep every line from an attached contract with its own number,
  dimensions, quality grade and annual quantity unless the buyer changes them. Give new items numbers that are
  free in the existing sequence (gaps first, in the order the buyer mentions the items), then the next numbers.
- Do NOT state counts of lines or items in your reply (software adds an exact summary).
- Be brief and concrete in your reply to the buyer. No filler.

Return JSON:
{"reply": str,                       // what you say to the buyer (markdown, short)
 "draft": {"title": str, "category": str, "delivery_location": str, "contract_period": str,
           "lines": [{"id": int, "name": str, "form": str, "board": str, "dims": str, "bf": number|null,
                      "print_colours": int, "annual_qty": number, "uom": str, "notes": str|null, "status": "unchanged"|"new"|"changed"}],
           "questionnaire": [{"id": str, "text": str, "must_pass": bool, "why": str}],
           "terms": [str]},
 "assumptions": [str],
 "open_questions": [str]}
"""


def turn(message: str, draft: dict | None, attachment_text: str | None, history: list[dict], on_status=None) -> dict:
    from datetime import date
    today = date.today()
    convo = "\n".join(f"{h['role'].upper()}: {h['content']}" for h in history[-8:])
    parts = [Part(text=f"TODAY'S DATE: {today:%d %B %Y}. Dates the buyer mentions without a year refer to the next such date.\n"),
             Part(text=f"CURRENT DRAFT (JSON):\n{json.dumps(draft or {}, ensure_ascii=False)}\n")]
    if attachment_text:
        parts.append(Part(text=f"ATTACHED BY BUYER:\n{attachment_text[:15000]}\n"))
    parts.append(Part(text=f"CONVERSATION SO FAR:\n{convo or '(start)'}\n\nBUYER: {message}"))
    out = complete_json(SYSTEM, parts, max_tokens=16000, fast=True, budget_s=180, on_status=on_status).data
    return _tidy_draft(out, attachment_text)


def _contract_ids(attachment_text: str | None) -> list[int]:
    """Line numbers present in an attached CSV contract (counted by code, not by the AI)."""
    if not attachment_text:
        return []
    import csv, io
    try:
        rows = list(csv.DictReader(io.StringIO(attachment_text)))
        key = next((k for k in ("line_no", "line", "id", "item_code") if rows and k in rows[0]), None)
        return sorted(int(float(r[key])) for r in rows if key and str(r.get(key, "")).strip())
    except Exception:
        return []


def _tidy_draft(out: dict, attachment_text: str | None) -> dict:
    """Deterministic clean-up: renumber new items into free item codes and write an exact summary."""
    d = out.get("draft") or {}
    lines = d.get("lines") or []
    if not lines:
        return out
    contract = _contract_ids(attachment_text)
    new = [l for l in lines if l.get("status") == "new"]
    keep = [l for l in lines if l.get("status") != "new"]
    used = {int(l["id"]) for l in keep if str(l.get("id", "")).lstrip("-").isdigit()}
    top = max(used | set(contract) | {0})
    free = [n for n in range(1, top + 1) if n not in used] + list(range(top + 1, top + 1 + len(new)))
    for l, n in zip(new, free):
        l["id"] = n
    d["lines"] = sorted(keep + new, key=lambda l: int(l.get("id") or 0))
    n_new = len(new)
    n_chg = sum(1 for l in keep if l.get("status") == "changed")
    summary = f"**Draft: {len(d['lines'])} lines**"
    if contract:
        summary += f" · {len(contract)} carried over from last year's contract"
    summary += f" · {n_chg} changed · {n_new} new"
    if new:
        summary += " (" + ", ".join(f"line {l['id']}: {l.get('name', '')}" for l in new) + ")"
    import re
    prose = re.sub(r"\b(all|the)\s+\d+\s+(items|lines|line items)\b", r"\1 \2", out.get("reply") or "", flags=re.I)
    out["reply"] = summary + "\n\n" + prose
    out["draft"] = d
    return out
