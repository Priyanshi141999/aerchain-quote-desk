"""Vendor-level rules that code checks exactly: deadlines, validity, certificates, qualification."""
from __future__ import annotations

import re
from datetime import datetime, date, timedelta

from rapidfuzz import fuzz

from .normalize import SETTINGS, flag


def _d(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _clean(name: str) -> str:
    n = (name or "").lower()
    n = re.sub(r"\b(pvt|private|ltd|limited|llp|m/s|the|india|\(india\))\b|[.,()]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def vendor_checks(vendor_key: str, docs, ex: dict, lines: list[dict], items: list[dict], injection_hits: list[dict]) -> list[dict]:
    F = []
    terms = ex.get("commercial_terms") or {}
    deadline = SETTINGS["deadline"]

    # submission time (from email headers, read by code)
    sent = [datetime.fromisoformat(d.meta["sent"]) for d in docs if d.kind == "email" and d.meta.get("sent")]
    if sent:
        latest = max(sent)
        if latest > deadline:
            hrs = (latest - deadline).total_seconds() / 3600
            F.append(flag("late_submission", "blocker",
                          f"Last message received {latest:%d %b %H:%M}, {hrs:.0f} h after the deadline "
                          f"({deadline:%d %b %H:%M}). Accepting it is the buyer's decision."))
        if len(sent) > 1:
            F.append(flag("multiple_messages", "info", f"{len(sent)} messages from this vendor; the latest values were used."))

    # validity
    qd = _d((ex.get("vendor") or {}).get("quote_date"))
    vu = _d(terms.get("valid_until"))
    if not vu and qd and terms.get("validity_days"):
        vu = qd + timedelta(days=int(terms["validity_days"]))
    ev = SETTINGS["evaluation_date"]
    if vu and vu < ev:
        F.append(flag("offer_expired", "blocker", f"Offer validity ended {vu:%d %b %Y}; today is {ev:%d %b %Y}. Ask vendor to extend before award."))
    elif terms.get("validity_days") and terms["validity_days"] < SETTINGS["min_validity_days"]:
        F.append(flag("short_validity", "warning", f"Validity {terms['validity_days']} days; RFQ asked for {SETTINGS['min_validity_days']}."))

    if terms.get("price_firmness"):
        F.append(flag("price_not_firm", "warning", f"Price variation clause: {terms['price_firmness']}"))
    if terms.get("currency_clause"):
        F.append(flag("currency_risk", "warning", f"Currency clause: {terms['currency_clause']}"))
    pd = terms.get("payment_days")
    if pd and pd != SETTINGS["required_payment_days"]:
        F.append(flag("payment_terms_deviation", "warning", f"Payment {pd} days vs required {SETTINGS['required_payment_days']}."))
    for disc in terms.get("discounts") or []:
        if disc.get("condition"):
            F.append(flag("conditional_discount", "warning",
                          f"Conditional discount: {disc.get('percent') or ''}% — {disc['condition']}. Applied only in scenarios that meet it."))
    for c in terms.get("one_time_charges") or []:
        if not c.get("amount"):
            continue
        F.append(flag("one_time_charges", "info", f"One-time: {c['description']} ₹{c['amount']:,.0f} {c.get('per','')}"))
    fr = terms.get("freight") or {}
    if fr.get("basis") in ("extra_at_actuals", "extra_unspecified") or (fr.get("basis") == "extra_per_trip" and not fr.get("truck_payload_kg")):
        F.append(flag("freight_unknown", "warning", "Freight is extra but cannot be calculated per unit; landed cost is incomplete."))
    for cf in ex.get("conflicts") or []:
        F.append(flag("document_conflict", "blocker",
                      f"{cf['topic']}: \"{cf['statement_a']}\" ({cf['source_a']}) vs \"{cf['statement_b']}\" ({cf['source_b']}). Clarify before award."))
    for rv in ex.get("revisions") or []:
        F.append(flag("revised_quote", "info", f"Revision: {rv['what_changed']} (earlier: {rv['earlier']}; later: {rv['later']})"))
    for r in ex.get("references_outside_documents") or []:
        F.append(flag("external_reference", "warning", f"Vendor referred to \"{r['phrase']}\" — affects {r['affects']}."))

    # documents
    for d in docs:
        if d.meta.get("hidden_rows"):
            F.append(flag("hidden_rows", "info", f"{d.file} has hidden rows {d.meta['hidden_rows']}; ignored as superseded."))
    manip = list(injection_hits)
    for s in ex.get("suspicious_content") or []:
        manip.append({"file": s.get("file"), "snippet": s.get("text", "")[:200]})
    invisible = [(d.file, i) for d in docs for i in d.meta.get("invisible_text", [])]
    if manip or invisible:
        files = sorted({m["file"] for m in manip} | {f for f, _ in invisible})
        snippet = (manip[0]["snippet"] if manip else invisible[0][1]["text"])[:220]
        F.append(flag("manipulation_attempt", "blocker",
                      f"{', '.join(files)} contains text aimed at automated evaluation"
                      f"{' (invisible to people)' if invisible else ''}: \"{snippet}\". It was ignored. Consider raising with the vendor."))

    quoted = sum(1 for l in lines if l["norm_inr"] is not None)
    if quoted < len(items):
        missing = [l["rfq_line"] for l in lines if l["norm_inr"] is None]
        F.append(flag("partial_quote", "warning", f"Priced {quoted} of {len(items)} lines. No usable price for lines {missing}."))
    return F


def qualification(ex: dict, questions: dict, vendor_name: str) -> dict:
    deadline = SETTINGS["deadline"].date()
    answers = {q.get("qid"): q for q in ex.get("questionnaire") or []}
    terms = ex.get("commercial_terms") or {}
    res = {}
    for q in questions["questions"]:
        a = answers.get(q["id"], {})
        status = a.get("meets_requirement") or "not_answered"
        reason = a.get("reason") or ""
        if not a.get("answered", False) and status != "no":
            status, reason = "not_answered", reason or "No answer given."
        res[q["id"]] = {"status": status, "reason": reason, "answer": a.get("answer_summary"), "must_pass": q["must_pass"]}

    # Q1: decide on evidence, not on the claim
    certs = [c for c in ex.get("certificates") or [] if "9001" in (c.get("standard") or "")]
    q1 = res.get("Q1")
    if q1 and q1["status"] != "not_answered":
        if not certs:
            if q1["status"] == "yes":
                q1.update(status="partial", reason="Vendor claims certification but no certificate was found in the documents.")
        else:
            c = certs[0]
            vu = _d(c.get("valid_until"))
            sim = fuzz.token_set_ratio(_clean(c.get("certificate_holder")), _clean(vendor_name))
            if vu and vu < deadline:
                q1.update(status="no", reason=f"Certificate {c.get('certificate_no')} expired on {vu:%d %b %Y}.")
            elif sim < 90:
                q1.update(status="partial",
                          reason=f"Certificate is issued to '{c.get('certificate_holder')}', not '{vendor_name}' "
                                 f"(name match {sim:.0f}%). Possibly a sister company; verify legal entity.")
            else:
                q1.update(status="yes", reason=f"Valid certificate {c.get('certificate_no')} until {c.get('valid_until')}.")
    # Q8: decide on stated payment days
    q8 = res.get("Q8")
    pd = terms.get("payment_days")
    if q8 and pd:
        if pd >= SETTINGS["required_payment_days"]:
            q8.update(status="yes", reason=f"Accepts {pd} days.")
        else:
            q8.update(status="no", reason=f"Asks for {pd} days; requirement is {SETTINGS['required_payment_days']}.")

    must = [res[q["id"]] for q in questions["questions"] if q["must_pass"]]
    if any(m["status"] in ("no", "not_answered") for m in must):
        overall = "not_qualified"
    elif all(m["status"] == "yes" for m in must):
        overall = "qualified"
    else:
        overall = "conditional"
    return {"overall": overall, "questions": res}
