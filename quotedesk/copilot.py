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
- QUESTIONNAIRE: if a STANDARD SUPPLIER QUESTIONNAIRE is provided, use it exactly (same ids, texts and
  must-pass flags) unless the buyer asks to change it; add new questions only on request, with ids after the
  last one. Otherwise propose 8-10 questions covering certification, test reports, capacity, lead time, raw
  material, printing, references, payment terms, tax registration and rejection policy.
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


def turn(message: str, draft: dict | None, attachment_text: str | None, history: list[dict], on_status=None,
         baseline_text: str | None = None, standard_questions: list | None = None) -> dict:
    """attachment_text is sent to the AI (first turn only); baseline_text is what code compares the draft against."""
    from datetime import date
    today = date.today()
    convo = "\n".join(f"{h['role'].upper()}: {h['content']}" for h in history[-8:])
    parts = [Part(text=f"TODAY'S DATE: {today:%d %B %Y}. Dates the buyer mentions without a year refer to the next such date.\n"),
             Part(text=f"CURRENT DRAFT (JSON):\n{json.dumps(draft or {}, ensure_ascii=False)}\n")]
    if attachment_text:
        parts.append(Part(text=f"ATTACHED BY BUYER:\n{attachment_text[:15000]}\n"))
    if standard_questions and not (draft or {}).get("questionnaire"):
        sq = [{"id": q["id"], "text": q["text"], "must_pass": q["must_pass"], "why": q.get("pass_rule", "")} for q in standard_questions]
        parts.append(Part(text=f"STANDARD SUPPLIER QUESTIONNAIRE (company default):\n{json.dumps(sq, ensure_ascii=False)}\n"))
    parts.append(Part(text=f"CONVERSATION SO FAR:\n{convo or '(start)'}\n\nBUYER: {message}"))
    out = complete_json(SYSTEM, parts, max_tokens=16000, fast=True, budget_s=180, on_status=on_status).data
    return _tidy_draft(out, baseline_text or attachment_text, draft)


def _rows(text: str | None) -> list[dict]:
    if not text:
        return []
    import csv, io
    try:
        return list(csv.DictReader(io.StringIO(text)))
    except Exception:
        return []


def _num(x):
    try:
        return round(float(str(x).replace(",", "")), 3)
    except Exception:
        return None


def _dims(x) -> tuple:
    import re
    return tuple(int(float(n)) for n in re.findall(r"\d+(?:\.\d+)?", str(x or ""))[:3])


def _ply(x) -> str:
    import re
    m = re.search(r"(\d)\s*-?\s*ply", str(x or ""), re.I)
    return m.group(1) if m else ""


def _sig(line: dict) -> dict:
    """The spec fields a vendor prices on, normalised so formatting differences don't count as changes."""
    return {"dims": _dims(line.get("dims") or line.get("dimensions")),
            "bf": _num(line.get("bf") if "bf" in line else line.get("bursting_factor_bf")),
            "qty": _num(line.get("annual_qty")),
            "colours": _num(line.get("print_colours")),
            "ply": _ply(line.get("board") or line.get("board_grade"))}


def _diff(a: dict, b: dict) -> list[str]:
    names = {"dims": "dimensions", "bf": "BF", "qty": "quantity", "colours": "print colours", "ply": "ply"}
    sa, sb = _sig(a), _sig(b)
    return [names[k] for k in sa if sa[k] not in (None, "", ()) and sb[k] not in (None, "", ()) and sa[k] != sb[k]] + \
           [names[k] for k in sa if sa[k] in (None, "", ()) and sb[k] not in (None, "", ())]


def _tidy_draft(out: dict, baseline_text: str | None, prev_draft: dict | None = None) -> dict:
    """Deterministic clean-up. Code, not the AI, decides line numbers and what is new / changed."""
    import re
    d = out.get("draft") or {}
    lines = d.get("lines") or []
    if not lines:
        return out
    base = {}
    for r in _rows(baseline_text):
        k = next((r[c] for c in ("line_no", "line", "id", "item_code") if c in r and str(r[c]).strip()), None)
        if k is not None:
            base[int(float(k))] = r
    prev = {int(l["id"]): l for l in (prev_draft or {}).get("lines", []) if str(l.get("id", "")).isdigit()}

    # 1. numbering: lines that are neither in the contract nor in the previous draft are new and take free item codes
    def known(l):
        i = l.get("id")
        return str(i).isdigit() and (int(i) in base or int(i) in prev)
    fresh = [l for l in lines if not known(l)]
    keep = [l for l in lines if known(l)]
    used = {int(l["id"]) for l in keep}
    top = max(used | set(base) | {0})
    free = [n for n in range(1, top + 1) if n not in used] + list(range(top + 1, top + 1 + len(fresh)))
    for l, n in zip(fresh, free):
        l["id"] = n
    lines = sorted(keep + fresh, key=lambda l: int(l["id"]))

    # 2. status against last year's contract (computed, never taken from the AI)
    for l in lines:
        i = int(l["id"])
        if base:
            if i not in base:
                l["status"] = "new"
            else:
                ch = _diff(base[i], l)
                l["status"] = "changed" if ch else "unchanged"
                l["notes"] = (f"Changed vs last year: {', '.join(ch)}. " if ch else "") + (l.get("notes") or "").replace("Changed vs last year:", "").strip()
    d["lines"] = lines
    out["draft"] = d

    # 3. what changed in THIS message (vs the previous draft)
    turn_bits = []
    if prev:
        added = [l for l in lines if int(l["id"]) not in prev]
        removed = [i for i in prev if i not in {int(l['id']) for l in lines}]
        edited = [(l, _diff(prev[int(l["id"])], l)) for l in lines if int(l["id"]) in prev]
        edited = [(l, c) for l, c in edited if c]
        if added:
            turn_bits.append("added " + ", ".join(f"line {l['id']}" for l in added))
        if removed:
            turn_bits.append("removed " + ", ".join(f"line {i}" for i in removed))
        for l, c in edited:
            turn_bits.append(f"line {l['id']}: {', '.join(c)} updated")

    new = [l for l in lines if l.get("status") == "new"]
    chg = [l for l in lines if l.get("status") == "changed"]
    summary = f"**Draft: {len(lines)} lines**"
    if base:
        summary += f" · {len(lines) - len(new)} from last year's contract · {len(chg)} changed" + \
                   (f" ({', '.join(f'line {l[chr(105) + chr(100)]}' for l in chg)})" if chg else "") + \
                   f" · {len(new)} new" + (f" ({', '.join(f'line {l[chr(105) + chr(100)]}' for l in new)})" if new else "")
    if prev:
        summary += "  \n**This message:** " + ("; ".join(turn_bits) if turn_bits else "no change to the line items")
    prose = re.sub(r"\b(all|the)\s+\d+\s+(items|lines|line items)\b", r"\1 \2", out.get("reply") or "", flags=re.I)
    out["reply"] = summary + "\n\n" + prose
    return out
