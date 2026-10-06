"""Run the whole thing: read every vendor's files → AI transcription → code normalization → checks."""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import llm
from .checks import qualification, vendor_checks
from .extract import code_facts_for, extract_vendor
from .ingest import read_vendor_folder, scan_injection
from .normalize import SETTINGS, add_outlier_flags, freight_per_uom, load_previous_contract, normalize_line


def load_rfq(data_dir: Path):
    b = data_dir / "buyer"
    items = json.loads((b / "rfq_line_items.json").read_text())
    questions = json.loads((b / "questionnaire.json").read_text())
    terms = (b / "rfq_document.md").read_text()
    prev = load_previous_contract(b / "last_year_contract_annapurna_FY25-26.csv")
    return items, questions, terms, prev


def process_vendor(folder: Path, items, questions, terms, prev, raw_cache: Path | None = None, use_cache=False):
    docs = read_vendor_folder(folder)
    inj = scan_injection(docs)
    facts = code_facts_for(docs)
    meta = {}
    if use_cache and raw_cache and raw_cache.exists():
        cached = json.loads(raw_cache.read_text())
        ex, meta = cached["extraction"], cached["meta"]
    else:
        ex, meta = extract_vendor(docs, items, questions, terms, facts)
        if raw_cache:
            raw_cache.write_text(json.dumps({"extraction": ex, "meta": meta}, indent=2, ensure_ascii=False))

    by_line = {int(l["rfq_line"]): l for l in ex.get("lines", []) if l.get("rfq_line") is not None}
    ct = ex.get("commercial_terms") or {}
    lines = []
    for it in items:
        L = by_line.get(it["id"], {"status": "not_quoted", "confidence": "high",
                                   "reading_notes": "AI returned no entry for this line"})
        n = normalize_line(L, it, ct, prev)
        fr, fr_note = freight_per_uom(ct, it) if n["norm_inr"] is not None else (None, "")
        n["freight_inr"], n["freight_note"] = fr, fr_note
        n["landed_inr"] = round(n["norm_inr"] + fr, 2) if (n["norm_inr"] is not None and fr is not None) else None
        lines.append(n)

    name = (ex.get("vendor") or {}).get("legal_name") or folder.name
    if name.isupper():
        name = name.title()
    return {
        "key": folder.name.split("_")[0],
        "folder": folder.name,
        "name": name,
        "documents": [{"file": d.file, "kind": d.kind, "meta": {k: v for k, v in d.meta.items()}} for d in docs],
        "extraction": ex,
        "meta": meta,
        "lines": lines,
        "lines_by_id": {l["rfq_line"]: l for l in lines},
        "vendor_flags": vendor_checks(folder.name, docs, ex, lines, items, inj),
        "qualification": qualification(ex, questions, name),
    }


def run_all(data_dir: Path, out_dir: Path, use_cache=False, only: list[str] | None = None, pause=0.0) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    items, questions, terms, prev = load_rfq(data_dir)
    results = {}
    for folder in sorted((data_dir / "vendors").iterdir()):
        if not folder.is_dir():
            continue
        key = folder.name.split("_")[0]
        if only and key not in only:
            continue
        cache = out_dir / f"raw_{folder.name}_{llm.provider()}.json"
        t0 = time.time()
        try:
            results[key] = process_vendor(folder, items, questions, terms, prev, cache, use_cache)
        except Exception as e:  # one vendor failing must not lose the others
            print(f"  {folder.name}: FAILED - {str(e)[:300]}", flush=True)
            continue
        print(f"  {folder.name}: {time.time() - t0:.0f}s ({results[key]['meta'].get('model')})", flush=True)
        if pause:
            time.sleep(pause)
    add_outlier_flags(results, items)
    snapshot = {"provider": llm.provider(), "settings": {k: str(v) for k, v in SETTINGS.items()},
                "vendors": {k: {kk: vv for kk, vv in v.items() if kk != "lines_by_id"} for k, v in results.items()}}
    (out_dir / f"results_{llm.provider()}.json").write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, default=str))
    return results
