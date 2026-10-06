"""Send a one-word request to every candidate model and report which ones answer (and how fast)."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quotedesk import llm

if llm.provider() == "gemini":
    from google.genai import types
    c = llm._gemini_client()
    names = sorted({m.name.split("/")[-1] for m in c.models.list()})
    print("All models on this key:", [n for n in names if "gemini" in n])
    for m in llm.gemini_candidates(c) + ["gemini-2.5-flash-lite", "gemini-3.5-flash-lite", "gemini-2.5-pro"]:
        t0 = time.time()
        try:
            r = c.models.generate_content(model=m, contents="Reply with the single word OK.",
                                          config=types.GenerateContentConfig(max_output_tokens=20))
            print(f"PING {m}: OK in {time.time()-t0:.1f}s -> {(r.text or '').strip()[:20]}")
        except Exception as e:
            print(f"PING {m}: FAIL in {time.time()-t0:.1f}s -> {str(e)[:150]}")
