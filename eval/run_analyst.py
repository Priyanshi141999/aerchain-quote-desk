"""Ask the analyst the demo questions on the saved readings and write the answers + code to a report.
Usage: LLM_PROVIDER=gemini python eval/run_analyst.py
"""
import os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402
from quotedesk import analyst, llm  # noqa: E402
from quotedesk.pipeline import load_rfq, run_all  # noqa: E402
from quotedesk.tables import line_table, vendor_table  # noqa: E402

QUESTIONS = [
    "What if we split it, cheapest per line, but only among vendors who cleared the quality questionnaire?",
    "Who is cheapest overall on a like-for-like basis, and where is freight unknown?",
    "If we gave everything to Deccan to get their 5% discount, how would that compare with the best split?",
    "Which lines have only one or no eligible quote among qualified and conditional vendors?",
    "Chart the price spread per line across vendors for the 5-ply boxes.",
    "Export a line-wise award recommendation to Excel.",
    # off-script questions an interviewer might ask
    "Which vendor has the best on-time delivery record?",
    "How much more are we paying this year versus last year's contract for the same items?",
    "Is Vendor B really the cheapest on line 13?",
]

items, *_ = load_rfq(ROOT / "data")
R = run_all(ROOT / "data", ROOT / "data/extractions", use_cache=True)
L, V = line_table(R, items), vendor_table(R)
FACTS = "\n".join(
    f"{k} {v['name']}: {v['qualification']['overall']} | "
    + "; ".join(f"{q} {s['status']}: {s['reason'][:110]}" for q, s in v["qualification"]["questions"].items() if s["must_pass"])
    + " | blockers: " + ("; ".join(f["message"][:120] for f in v["vendor_flags"] if f["severity"] == "blocker") or "none")
    for k, v in R.items())
out = [f"# Analyst test — {llm.provider()}\n"]
hist = []
for q in QUESTIONS:
    t0 = time.time()
    try:
        a = analyst.ask(q, L, V, items, hist, vendor_facts=FACTS, last_year=pd.read_csv(ROOT / "data/buyer/last_year_contract_annapurna_FY25-26.csv"))
        res = a["result"]
        frames = [res] if isinstance(res, pd.DataFrame) else [v for v in (res.values() if isinstance(res, dict) else []) if isinstance(v, pd.DataFrame)]
        tbl = "\n\n".join(f.head(12).to_markdown(index=False) for f in frames) or str(res)[:2500]
        out += [f"## Q: {q}", f"*{time.time() - t0:.0f}s*", "", a["answer"].get("answer_markdown", ""), "",
                "**Caveats:** " + "; ".join(a["answer"].get("caveats", [])), "",
                f"**Number check:** {a.get('number_check')}", "", f"**Chart:** {'yes' if a.get('fig') is not None else 'no'} · **Export:** {'yes' if a.get('export') is not None else 'no'}", "",
                f"**Interpretation:** {a['plan'].get('interpretation')}", "",
                "```python\n" + a["plan"].get("code", "") + "\n```", "", "**Computed result:**", "", tbl,
                f"\n{'ERROR: ' + a['error'] if a.get('error') else ''}\n"]
        hist.append({"q": q, "answer": a["answer"].get("answer_markdown", "")})
    except Exception as e:
        out += [f"## Q: {q}", f"FAILED: {e}"]
    time.sleep(float(os.environ.get("EVAL_PAUSE", "5")))
(ROOT / "eval/out").mkdir(parents=True, exist_ok=True)
(ROOT / f"eval/out/analyst_{llm.provider()}.md").write_text("\n".join(out))
print("\n".join(out)[:3000])
