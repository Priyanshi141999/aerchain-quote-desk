"""Quote Desk — Streamlit app. Run: streamlit run app.py"""
from __future__ import annotations

import io
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
DATA = ROOT / "data"
EXTRACTIONS = DATA / "extractions"

st.set_page_config(page_title="Quote Desk", page_icon="📦", layout="wide")

# keys from Streamlit secrets → environment (the AI layer reads env vars)
for k in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_MODEL", "CLAUDE_MODEL"):
    try:
        if k in st.secrets and not os.environ.get(k):
            os.environ[k] = st.secrets[k]
    except Exception:
        pass

from quotedesk import analyst, copilot, llm  # noqa: E402
from quotedesk.ingest import read_vendor_folder  # noqa: E402
from quotedesk.pipeline import load_rfq, run_all  # noqa: E402
from quotedesk.tables import attention_queue, line_table, vendor_table  # noqa: E402

st.markdown("""
<style>
.block-container {padding-top: 1.6rem; max-width: 1400px;}
.qd-badge {display:inline-block; padding:2px 9px; border-radius:10px; font-size:0.78rem; font-weight:600;}
.qd-q {background:#E6F4EA; color:#1E6B34;} .qd-c {background:#FFF4D6; color:#7A5600;} .qd-n {background:#FDE7E7; color:#9B1C1C;}
.qd-card {border:1px solid rgba(128,128,128,.25); border-radius:10px; padding:12px 14px; height:100%;}
.qd-muted {color: #6b7280; font-size: 0.85rem;}
.qd-trail {font-family: ui-monospace, monospace; font-size: 0.85rem; background: rgba(128,128,128,.08); padding: 8px 10px; border-radius: 6px;}
</style>
""", unsafe_allow_html=True)

QUAL_BADGE = {"qualified": ("Qualified", "qd-q"), "conditional": ("Conditional", "qd-c"), "not_qualified": ("Not qualified", "qd-n")}
SEV_ICON = {"blocker": "🛑", "warning": "⚠️", "info": "ℹ️"}
VENDOR_FOLDERS = {p.name.split("_")[0]: p for p in sorted((DATA / "vendors").iterdir()) if p.is_dir()}

# ------------------------------------------------------------------ state
ss = st.session_state
ss.setdefault("overrides", {})       # "A:13" -> {value, reason, by, at}
ss.setdefault("audit", [])           # every human decision, in order
ss.setdefault("acks", {})            # flag id -> note
ss.setdefault("chat", [])            # analyst conversation
ss.setdefault("copilot_msgs", [])
ss.setdefault("draft", None)
ss.setdefault("published", False)

items, questions, rfq_terms, prev = load_rfq(DATA)


def log(action: str, detail: str, by: str = "Priya Raman (buyer)"):
    ss.audit.append({"time": datetime.now().strftime("%d %b %H:%M:%S"), "by": by, "action": action, "detail": detail})


def available_providers():
    out = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        out.append("claude")
    if os.environ.get("GEMINI_API_KEY"):
        out.append("gemini")
    return out


def cached_provider():
    for p in ("claude", "gemini", "mock"):
        if list(EXTRACTIONS.glob(f"raw_*_{p}.json")):
            return p
    return None


def load_results(force_live=False):
    prov = llm.provider()
    has_cache = len(list(EXTRACTIONS.glob(f"raw_*_{prov}.json"))) >= len(VENDOR_FOLDERS)
    if not force_live and not has_cache:
        cp = cached_provider()
        if cp:
            os.environ["LLM_PROVIDER"] = cp
            prov = cp
    res = run_all(DATA, EXTRACTIONS, use_cache=not force_live)
    ss.results, ss.results_provider, ss.results_at = res, prov, datetime.now().strftime("%d %b %H:%M")
    return res


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("### 📦 Quote Desk")
    st.caption("Kaveri Home Appliances · Corrugated packaging RFQ KHA/PKG/RFQ/2026-27/014")
    page = st.radio("Go to", ["1 · Draft RFQ with co-pilot", "2 · Vendor responses", "3 · Comparison",
                              "4 · Needs your attention", "5 · Ask the analyst", "6 · Vendor portal (vendor view)",
                              "7 · Audit log & export"], label_visibility="collapsed")
    st.divider()
    provs = available_providers()
    if provs:
        choice = st.selectbox("AI model provider", provs, index=0,
                              format_func=lambda p: {"claude": "Claude (Anthropic)", "gemini": "Gemini (Google)"}[p])
        os.environ["LLM_PROVIDER"] = choice
    else:
        st.warning("No API key configured. Showing saved AI readings; live AI features are disabled.")
    st.caption("The AI reads documents and plans analyses. Code does every calculation, so each number is traceable.")

if "results" not in ss:
    with st.spinner("Loading the AI's readings of the vendor responses…"):
        try:
            load_results()
        except Exception as e:
            ss.results = {}
            st.error(f"Could not load vendor readings: {e}")
R = ss.get("results", {})
L = line_table(R, items, ss.overrides) if R else pd.DataFrame()
V = vendor_table(R) if R else pd.DataFrame()


def badge(qual):
    t, c = QUAL_BADGE.get(qual, (qual, "qd-c"))
    return f'<span class="qd-badge {c}">{t}</span>'


def inr(x, dec=2):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    if dec == 0:
        s = f"{int(round(x)):,}"
        # Indian grouping
        neg = s.startswith("-"); s = s.lstrip("-").replace(",", "")
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        return ("-" if neg else "") + "₹" + (",".join(parts) + "," if parts else "") + tail
    return f"₹{x:,.2f}"


def crore(x):
    return f"₹{x / 1e7:.2f} Cr"


# ================================================================== 1. CO-PILOT
if page.startswith("1"):
    st.header("Draft the RFQ with the co-pilot")
    st.caption("Talk the RFQ into existence. Start from last year's contract, say what changes, and the co-pilot keeps a structured draft and asks what's missing.")
    left, right = st.columns([5, 6], gap="large")
    with left:
        attach = st.toggle("Attach last year's contract (Annapurna FY25-26, 28 lines)", value=True)
        attach_text = (DATA / "buyer/last_year_contract_annapurna_FY25-26.csv").read_text() if attach else None
        up = st.file_uploader("…or attach your own item list (CSV / TXT)", type=["csv", "txt"])
        if up:
            attach_text = up.read().decode("utf-8", "ignore")
        for m in ss.copilot_msgs:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
        starter = ("Same as last year for the Hosur plant, but add a printed accessory kit mailer (die-cut, E-flute, 4 colours, "
                   "about 60,000 a year) and an E-flute die-cut insert for the induction cooktop (65,000 a year), and upgrade the "
                   "750W mixer box to 22 BF. One-year rate contract from 1 Nov.")
        if not ss.copilot_msgs:
            st.info(f"**Try:** {starter}")
            if st.button("Use this example"):
                ss.pending_copilot = starter
                st.rerun()
        msg = st.chat_input("Tell the co-pilot what you need…") or ss.pop("pending_copilot", None)
        if msg:
            if not available_providers():
                st.error("Add an API key to use the co-pilot live.")
            else:  # show the buyer's message immediately, then work on the reply
                ss.copilot_msgs.append({"role": "user", "content": msg})
                ss.copilot_working = msg
                st.rerun()
        if ss.get("copilot_working"):
            msg = ss.copilot_working
            with st.status("Co-pilot is drafting the RFQ…", expanded=True) as status:
                st.write("Reading last year's contract and applying your changes (usually 20–60 s).")
                try:
                    out = copilot.turn(msg, ss.draft, attach_text if len(ss.copilot_msgs) <= 2 else None, ss.copilot_msgs[:-1],
                                       on_status=lambda m: status.update(label=f"Co-pilot is drafting… {m}"))
                    ss.draft = out.get("draft") or ss.draft
                    reply = out.get("reply", "")
                    if out.get("open_questions"):
                        reply += "\n\n**Questions for you:**\n" + "\n".join(f"- {q}" for q in out["open_questions"])
                    if out.get("assumptions"):
                        reply += "\n\n**Assumptions I made (change any):**\n" + "\n".join(f"- {a}" for a in out["assumptions"])
                    ss.copilot_msgs.append({"role": "assistant", "content": reply})
                    status.update(label="Draft updated", state="complete")
                except Exception as e:
                    ss.copilot_msgs.append({"role": "assistant", "content": f"⚠️ I couldn't reach the AI just now: {e}"})
                    status.update(label="AI call failed", state="error")
            ss.copilot_working = None
            st.rerun()
    with right:
        d = ss.draft
        if not d:
            st.markdown("#### Draft will appear here")
            st.caption("Line items, questionnaire and terms update after every message.")
        else:
            st.markdown(f"#### {d.get('title', 'RFQ draft')}")
            st.caption(f"{d.get('category','')} · {d.get('delivery_location','')} · {d.get('contract_period','')}")
            dl = pd.DataFrame(d.get("lines", []))
            if not dl.empty:
                n_new = int((dl.get("status") == "new").sum()) if "status" in dl else 0
                n_chg = int((dl.get("status") == "changed").sum()) if "status" in dl else 0
                st.markdown(f"**{len(dl)} line items** · {n_new} new · {n_chg} changed")
                edited = st.data_editor(dl, hide_index=True, width="stretch", height=360, key="draft_editor")
                ss.draft["lines"] = edited.to_dict("records")
            with st.expander(f"Questionnaire ({len(d.get('questionnaire', []))} questions)", expanded=False):
                for q in d.get("questionnaire", []):
                    st.markdown(f"- **{q.get('id')}** {q.get('text')} {'`MUST-PASS`' if q.get('must_pass') else ''}  \n  <span class='qd-muted'>{q.get('why','')}</span>", unsafe_allow_html=True)
            with st.expander("Commercial terms", expanded=False):
                for t in d.get("terms", []):
                    st.markdown(f"- {t}")
            c1, c2 = st.columns(2)
            if c1.button("📤 Publish RFQ to 5 vendors", type="primary", disabled=ss.published):
                ss.published = True
                log("RFQ published", f"{len(dl)} lines sent to 5 vendors by email (stubbed channel)")
                st.rerun()
            if ss.published:
                st.success("Sent by email to Siam Pacific, Deccan Packaging, Vijay Box Works, Sri Murugan and Annapurna. "
                           "Vendors can reply in any format. **Nine days later →** see *2 · Vendor responses*.")
                st.caption("Email is stubbed for the demo. The responses in this demo answer the published packaging RFQ "
                           "KHA/PKG/RFQ/2026-27/014 (30 lines).")

# ================================================================== 2. RESPONSES
elif page.startswith("2"):
    st.header("Vendor responses")
    st.caption("Five vendors, five formats. Nobody was forced into the template. The AI reads each response in whatever shape it arrived.")
    top = st.columns([3, 2])
    with top[0]:
        st.markdown(f"Readings shown: **{ss.get('results_provider', '—')}** · loaded {ss.get('results_at', '—')}")
    with top[1]:
        if st.button("🔄 Re-read all responses with AI now (live)", disabled=not available_providers()):
            with st.spinner("AI is reading 5 vendors' documents (≈1–3 min)…"):
                try:
                    load_results(force_live=True)
                    log("AI re-read", f"All responses re-read live with {llm.provider()}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Live re-read failed: {e}")
    import pdfplumber
    for vk, folder in VENDOR_FOLDERS.items():
        v = R.get(vk)
        name = v["name"] if v else folder.name
        with st.expander(f"**{vk} · {name}**" + (f" — {v['qualification']['overall'].replace('_', ' ')}" if v else ""), expanded=(vk == "D")):
            docs = read_vendor_folder(folder)
            if v:
                priced = sum(1 for l in v["lines"] if l["norm_inr"] is not None)
                bl = sum(1 for f in v["vendor_flags"] if f["severity"] == "blocker")
                st.markdown(f"{badge(v['qualification']['overall'])} &nbsp; **{priced}/30** lines priced · "
                            f"{bl} blocker(s) · read by `{v['meta'].get('model')}` in {v['meta'].get('seconds')} s", unsafe_allow_html=True)
            tabs = st.tabs([d.file for d in docs])
            for t, d in zip(tabs, docs):
                with t:
                    if d.kind == "image":
                        st.image(d.binary, caption=d.file, width=520)
                    elif d.kind == "pdf":
                        with pdfplumber.open(folder / d.file) as pdf:
                            imgs = [p.to_image(resolution=70).original for p in pdf.pages[:3]]
                        cols = st.columns(len(imgs))
                        for c, im in zip(cols, imgs):
                            c.image(im)
                        if d.meta.get("invisible_text"):
                            st.error("🛑 This PDF contains text invisible to people (white or tiny): "
                                     f"\"{d.meta['invisible_text'][0]['text'][:180]}…\". It is treated as data and ignored.")
                    else:
                        st.text(d.text[:4000])
                        if d.meta.get("hidden_rows"):
                            st.warning(f"Hidden rows found by software: {d.meta['hidden_rows']}")

# ================================================================== 3. COMPARISON
elif page.startswith("3"):
    st.header("Side-by-side comparison")
    if L.empty:
        st.stop()
    c = st.columns([2, 2, 2, 3])
    basis = c[0].radio("Price basis", ["Basic price", "Landed (incl. freight)"], horizontal=False)
    scope = c[1].radio("Vendors", ["All vendors", "Qualified + conditional", "Qualified only"])
    show_low = c[2].checkbox("Highlight low-confidence readings", value=True)
    col = "price_inr" if basis == "Basic price" else "landed_inr"

    # vendor cards
    cards = st.columns(len(V))
    for cc, (_, vr) in zip(cards, V.iterrows()):
        q = R[vr["vendor"]]["qualification"]["questions"]
        mp = " ".join(f"{qid}:{'✅' if q[qid]['status'] == 'yes' else '❌' if q[qid]['status'] in ('no', 'not_answered') else '🟡'}"
                      for qid in ("Q1", "Q2", "Q8"))
        tot = L[(L.vendor == vr["vendor"])]["annual_value_inr"].sum()
        cc.markdown(f"""<div class="qd-card"><b>{vr['vendor']} · {vr['vendor_name']}</b><br>{badge(vr['qualification'])}
        <div class="qd-muted" style="margin-top:6px">{mp}<br>{vr['lines_priced']}/30 lines · {crore(tot)} quoted<br>
        {SEV_ICON['blocker']} {vr['blockers']} &nbsp; {SEV_ICON['warning']} {vr['warnings']}</div></div>""", unsafe_allow_html=True)
    st.write("")

    sel = L.copy()
    if scope == "Qualified only":
        sel = sel[sel.qualification == "qualified"]
    elif scope == "Qualified + conditional":
        sel = sel[sel.qualification.isin(["qualified", "conditional"])]
    vendors_in = list(dict.fromkeys(sel.vendor))
    ranked = sel[(~sel.excluded_from_ranking) & sel[col].notna()]
    best = ranked.loc[ranked.groupby("line")[col].idxmin()] if not ranked.empty else ranked
    best_by_line = dict(zip(best.line, best.vendor))

    piv = sel.pivot(index="line", columns="vendor", values=col)
    meta = {(r.vendor, r.line): r for r in sel.itertuples()}
    disp = pd.DataFrame(index=piv.index)
    disp["Item"] = [next(it["name"] for it in items if it["id"] == ln) for ln in piv.index]
    disp["Qty"] = [f"{next(it['annual_qty'] for it in items if it['id'] == ln):,}" for ln in piv.index]
    for v in vendors_in:
        vals = []
        for ln in piv.index:
            m = meta.get((v, ln))
            x = piv.loc[ln, v] if v in piv else None
            if m is None:
                vals.append("")
            elif x is None or pd.isna(x):
                vals.append("not quoted" if m.status in ("not_quoted", "price_on_request") else
                            ("freight ?" if col == "landed_inr" and m.price_inr is not None else "—"))
            else:
                mark = " 🛑" if m.worst_flag == 0 else (" ⚠️" if m.worst_flag == 1 else "")
                vals.append(f"{x:,.2f}{mark}")
        disp[f"{v}"] = vals
    disp["L1"] = [best_by_line.get(ln, "—") for ln in piv.index]

    def style(df):
        s = pd.DataFrame("", index=df.index, columns=df.columns)
        for ln in df.index:
            for v in vendors_in:
                m = meta.get((v, ln))
                if not m:
                    continue
                if best_by_line.get(ln) == v:
                    s.loc[ln, v] = "background-color: rgba(34,139,34,.18); font-weight:600"
                if m.excluded_from_ranking:
                    s.loc[ln, v] = "color: #b91c1c; text-decoration: line-through"
                elif show_low and m.confidence == "low":
                    s.loc[ln, v] += "; outline: 2px solid #f59e0b"
        return s
    st.markdown(f"**₹ per unit, ex-GST{' + freight' if col == 'landed_inr' else ''}** · green = lowest eligible · "
                "🛑 needs a decision · ⚠️ check · strikethrough = suspected error, excluded from ranking")
    st.dataframe(disp.style.apply(style, axis=None), width="stretch", height=560,
                 column_config={"Item": st.column_config.TextColumn(width="large")})
    if not best.empty:
        l1_total = (best[col] * best.annual_qty).sum()
        n_l1 = best.line.nunique()
        st.caption(f"Cheapest-per-line across shown vendors: **{crore(l1_total)}** for {n_l1}/30 lines. "
                   f"Lines with no eligible price: {sorted(set(range(1, 31)) - set(best.line)) or 'none'}.")

    st.subheader("Inspect any number")
    ic = st.columns([1, 3])
    vsel = ic[0].selectbox("Vendor", list(R.keys()), format_func=lambda k: f"{k} · {R[k]['name']}")
    lsel = ic[1].selectbox("Line", [it["id"] for it in items], format_func=lambda i: f"{i} · {next(x['name'] for x in items if x['id'] == i)}")
    row = L[(L.vendor == vsel) & (L.line == lsel)].iloc[0]
    a, b = st.columns([3, 2], gap="large")
    with a:
        st.markdown(f"**Vendor wrote:** `{row["as_written"] or '—'}`  \n**Vendor's description:** {row["vendor_description"] or '—'}")
        src = row["source"] or {}
        st.markdown(f"**Found in:** `{src.get('file', '—')}` · {src.get('location', '')}  \n> {src.get('quote', '')}")
        st.markdown(f"**How we got to the comparable number** (confidence: **{row["confidence"]}**)")
        st.markdown("<div class='qd-trail'>" + "<br>".join(row["trail"] or ["no price"]) + "</div>", unsafe_allow_html=True)
        if row["freight_note"]:
            st.caption(f"Freight: {row["freight_note"]}")
        for f in row["flags"]:
            st.markdown(f"{SEV_ICON[f['severity']]} **{f['code'].replace('_', ' ')}** — {f['message']}")
        if vsel == "D" and src.get("file", "").endswith(".jpg"):
            st.image(str(VENDOR_FOLDERS["D"] / src["file"]), width=420, caption="Source photo")
    with b:
        st.markdown("**Correct or confirm this value**")
        with st.form(f"fix_{vsel}_{lsel}"):
            nv = st.number_input("₹ per unit, ex-GST", value=float(row["price_inr"]) if row["price_inr"] is not None and not pd.isna(row["price_inr"]) else 0.0, step=0.01, format="%.2f")
            reason = st.text_input("Reason (required)", placeholder="e.g. Confirmed with vendor by phone, 6 Oct")
            if st.form_submit_button("Save correction"):
                if not reason.strip():
                    st.error("A reason is required. It goes into the audit log.")
                else:
                    ss.overrides[f"{vsel}:{lsel}"] = {"value": nv, "reason": reason, "by": "Priya Raman (buyer)", "at": datetime.now().isoformat()}
                    log("Value corrected", f"{vsel} line {lsel}: {row["price_inr"]} → {nv:.2f} ({reason})")
                    st.rerun()

# ================================================================== 4. ATTENTION
elif page.startswith("4"):
    st.header("Needs your attention")
    st.caption("Everything the system was unsure about, or that could change the award, worst first. Nothing here was silently decided for you.")
    Q = attention_queue(R, L)
    done = sum(1 for i, x in enumerate(Q) if f"{x['vendor']}|{x['line']}|{x['code']}|{i}" in ss.acks)
    st.progress(done / max(len(Q), 1), text=f"{done} of {len(Q)} reviewed")
    sev_f = st.multiselect("Show", ["blocker", "warning"], default=["blocker", "warning"],
                           format_func=lambda s: f"{SEV_ICON[s]} {s}s")
    for qi, x in enumerate(Q):
        if x["severity"] not in sev_f:
            continue
        key = f"{x['vendor']}|{x['line']}|{x['code']}|{qi}"
        acked = key in ss.acks
        c1, c2 = st.columns([8, 2])
        where = f" · line {x['line']}" if x["line"] else ""
        c1.markdown(f"{SEV_ICON[x['severity']]} **{x['vendor']} · {x['vendor_name']}**{where} — "
                    f"**{x['code'].replace('_', ' ')}**: {x['message']}" + ("  ✅ *reviewed*" if acked else ""))
        if not acked and c2.button("Mark reviewed", key="ack" + key):
            ss.acks[key] = datetime.now().isoformat()
            log("Flag reviewed", f"{x['vendor']} line {x['line'] or '-'}: {x['code']}")
            st.rerun()

# ================================================================== 5. ANALYST
elif page.startswith("5"):
    st.header("Ask the analyst")
    st.caption("Plain-English questions over the whole comparison. The AI writes the calculation, code runs it on the extracted data, and the AI explains only what was computed.")
    examples = {
        "Split it: cheapest per line, qualified vendors only": "What if we split it, cheapest per line, but only among vendors who cleared the quality questionnaire?",
        "Who's cheapest on landed cost? Where is freight unknown?": "Who is cheapest overall on landed cost, and where is freight unknown?",
        "Everything to Deccan for 5% off vs the best split": "If we gave everything to Deccan to get their 5% discount, how would that compare with the best split?",
        "Which lines have one or no eligible quote?": "Which lines have only one or no eligible quote among qualified and conditional vendors?",
        "Chart the price spread for 5-ply boxes": "Chart the price spread per line across vendors for the 5-ply boxes.",
        "Export a line-wise award recommendation": "Export a line-wise award recommendation to Excel.",
    }
    st.caption("Try one of these, or type your own below:")
    ec = st.columns(2)
    for i, (label, full) in enumerate(examples.items()):
        if ec[i % 2].button(label, key=f"ex{i}", width="stretch", help=full):
            ss.pending_q = full
            st.rerun()
    for i, h in enumerate(ss.chat):
        with st.chat_message("user"):
            st.markdown(h["q"])
        with st.chat_message("assistant"):
            st.markdown(h["answer"])
            nc = h.get("number_check") or {}
            if nc.get("checked"):
                if nc["unverified"]:
                    st.warning(f"⚠️ {len(nc['unverified'])} of {nc['checked']} figures could not be traced to the calculation: "
                               + ", ".join(nc["unverified"]) + ". Treat them with caution.")
                else:
                    st.caption(f"✓ All {nc['checked']} figures in this answer trace back to the computed results.")
            if h.get("caveats"):
                st.markdown("**Caveats:** " + " · ".join(h["caveats"]))
            if h.get("fig") is not None:
                st.plotly_chart(h["fig"], width="stretch", key=f"fig{i}")
            if isinstance(h.get("table"), pd.DataFrame):
                st.dataframe(h["table"], width="stretch", hide_index=True)
            exp = h.get("export") if isinstance(h.get("export"), pd.DataFrame) else (h.get("table") if isinstance(h.get("table"), pd.DataFrame) else None)
            if exp is not None:
                buf = io.BytesIO(); exp.to_excel(buf, index=False)
                st.download_button("⬇️ Download as Excel", buf.getvalue(), file_name=f"analysis_{i + 1}.xlsx", key=f"dl{i}")
            if h.get("plan"):
                with st.expander("How I worked this out"):
                    st.markdown(f"**Interpretation:** {h['plan'].get('interpretation')}")
                    for a_ in h["plan"].get("assumptions", []):
                        st.markdown(f"- {a_}")
                    st.code(h["plan"].get("code", ""), language="python")
                    if h.get("error"):
                        st.error(h["error"])
            if h.get("followups"):
                st.caption("You could ask next: " + " · ".join(h["followups"]))
    q = st.chat_input("Ask anything about the quotes…") or ss.pop("pending_q", None)
    if q:
        if not available_providers():
            st.error("Add an API key to ask questions live.")
        else:
            ss.analyst_working = q
            st.rerun()
    if ss.get("analyst_working"):
        q = ss.analyst_working
        with st.chat_message("user"):
            st.markdown(q)
        with st.status("Working on it…", expanded=True) as status:
            st.write("1. AI plans the calculation → 2. code runs it on the extracted quotes → 3. AI writes up only what was computed.")
            try:
                facts = []
                for vk_, v_ in R.items():
                    qq = v_["qualification"]["questions"]
                    must = "; ".join(f"{qid} {qq[qid]['status']}: {qq[qid]['reason'][:110]}" for qid in ("Q1", "Q2", "Q8") if qid in qq)
                    blk = "; ".join(f["message"][:120] for f in v_["vendor_flags"] if f["severity"] == "blocker")
                    facts.append(f"{vk_} {v_['name']}: {v_['qualification']['overall']} | must-pass: {must} | blockers: {blk or 'none'}")
                out = analyst.ask(q, L, V, items, ss.chat, on_status=lambda m: status.update(label=f"Working on it… {m}"),
                                  vendor_facts="\n".join(facts))
                res = out["result"]
                if isinstance(res, dict):
                    frames = [v for v in res.values() if isinstance(v, (pd.DataFrame, pd.Series))]
                    res = max(frames, key=len) if frames else None
                tbl = res if isinstance(res, pd.DataFrame) else (res.reset_index() if isinstance(res, pd.Series) else None)
                ss.chat.append({"q": q, "answer": out["answer"].get("answer_markdown", ""), "caveats": out["answer"].get("caveats", []),
                                "followups": out["answer"].get("followups", []), "plan": out["plan"], "fig": out["fig"],
                                "table": tbl, "export": out.get("export"), "error": out.get("error"),
                                "number_check": out.get("number_check")})
                log("Analyst question", q)
                status.update(label="Done", state="complete")
            except Exception as e:
                ss.chat.append({"q": q, "answer": f"⚠️ I couldn't reach the AI just now: {e}", "caveats": [], "followups": [],
                                "plan": {}, "fig": None, "table": None, "export": None, "error": None, "number_check": None})
                status.update(label="AI call failed", state="error")
        ss.analyst_working = None
        st.rerun()

# ================================================================== 6. VENDOR PORTAL
elif page.startswith("6"):
    st.header("Vendor portal: confirm what we read")
    st.caption("Each vendor gets a private link showing how their quote was read. They confirm or correct their own numbers, and the vendor, who knows what they meant, does the checking.")
    vk = st.selectbox("Viewing as", list(R.keys()), format_func=lambda k: f"{R[k]['name']} (vendor)")
    v = R[vk]
    st.markdown(f"Dear **{v['name']}**, thank you for your quote against **RFQ KHA/PKG/RFQ/2026-27/014**. "
                "Here is how we read it. Please confirm or correct the lines marked for review.")
    rows = []
    for l in v["lines"]:
        it = next(x for x in items if x["id"] == l["rfq_line"])
        needs = any(f["severity"] in ("blocker", "warning") for f in l["flags"]) or l["confidence"] == "low"
        rows.append({"Line": it["id"], "Item": it["name"], "You wrote": l.get("as_written") or "—",
                     "We read it as (₹/unit ex-GST)": l["norm_inr"], "Please review": "⚠️" if needs else ""})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=380)
    review = [r for r in rows if r["Please review"]]
    if review:
        st.markdown(f"**{len(review)} line(s) need your confirmation**")
        with st.form("vendor_confirm"):
            entries = {}
            for r in review[:8]:
                cA, cB = st.columns([3, 2])
                cA.markdown(f"**Line {r['Line']} · {r['Item']}** — you wrote `{r['You wrote']}`, we read **{inr(r['We read it as (₹/unit ex-GST)'])}**")
                entries[r["Line"]] = cB.number_input("Correct ₹/unit ex-GST", key=f"vc{vk}{r['Line']}",
                                                     value=float(r["We read it as (₹/unit ex-GST)"] or 0.0), step=0.01, format="%.2f")
            if st.form_submit_button("Confirm these values", type="primary"):
                for ln, val in entries.items():
                    ss.overrides[f"{vk}:{ln}"] = {"value": val, "reason": "confirmed by vendor via portal", "by": f"{v['name']} (vendor)",
                                                 "at": datetime.now().isoformat()}
                    log("Vendor confirmation", f"{vk} line {ln}: {val:.2f}", by=f"{v['name']} (vendor)")
                st.success("Thank you. Your confirmations were sent to the buyer.")
    else:
        st.success("Nothing needs your confirmation.")

# ================================================================== 7. AUDIT & EXPORT
elif page.startswith("7"):
    st.header("Audit log & export")
    st.caption("Every human decision is recorded: corrections, vendor confirmations, reviewed flags and questions asked. That's what makes an award defensible.")
    st.dataframe(pd.DataFrame(ss.audit or [{"time": "—", "by": "—", "action": "No actions yet", "detail": ""}]),
                 hide_index=True, width="stretch")
    if not L.empty:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            piv = L.pivot(index=["line", "item", "annual_qty", "uom"], columns="vendor", values="price_inr").reset_index()
            piv.to_excel(xw, sheet_name="Comparison (INR ex-GST)", index=False)
            L.drop(columns=["flags", "trail", "source"]).to_excel(xw, sheet_name="All readings", index=False)
            V.to_excel(xw, sheet_name="Vendors", index=False)
            pd.DataFrame(attention_queue(R, L)).to_excel(xw, sheet_name="Flags", index=False)
            pd.DataFrame(ss.audit).to_excel(xw, sheet_name="Audit log", index=False)
        st.download_button("⬇️ Download the full comparison workbook (Excel)", buf.getvalue(),
                           file_name="KHA_RFQ014_comparison.xlsx", type="primary")
