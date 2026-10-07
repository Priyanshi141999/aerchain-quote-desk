"""One small interface over two AI providers (Gemini and Claude).

Everything else in the app calls `complete_json(...)` and never cares which model answered.
Switch with the env var LLM_PROVIDER = "gemini" | "claude".
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass, field


@dataclass
class Part:
    """A piece of model input: plain text, or a binary file (image / PDF)."""
    text: str | None = None
    data: bytes | None = None
    mime: str | None = None


@dataclass
class LLMResult:
    data: dict
    provider: str
    model: str
    seconds: float
    raw_text: str = field(repr=False, default="")


GEMINI_PREFERENCE = [
    "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash",
    "gemini-3-flash-preview", "gemini-2.5-flash",
]
CLAUDE_DEFAULT = "claude-sonnet-5-5"

_gemini_model_cache: str | None = None


def provider() -> str:
    return os.environ.get("LLM_PROVIDER", "gemini").lower()


def _secret(name: str) -> str | None:
    v = os.environ.get(name)
    if v:
        return v
    try:  # Streamlit Cloud secrets, when running inside the app
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Model did not return JSON. First 300 chars: {text[:300]}")
    return json.loads(text[start:end + 1])


# ---------------------------------------------------------------- Gemini
def _gemini_client(timeout_s: float | None = None):
    from google import genai
    from google.genai import types
    key = _secret("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    if timeout_s:
        return genai.Client(api_key=key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))
    return genai.Client(api_key=key)


def gemini_candidates(client=None) -> list[str]:
    """Best-first list of Flash models this key can use. Names change often, so we ask the API."""
    global _gemini_model_cache
    if _gemini_model_cache:
        return _gemini_model_cache
    client = client or _gemini_client()
    try:
        available = {m.name.split("/")[-1] for m in client.models.list()}
    except Exception:
        available = set()
    picks = [n for n in GEMINI_PREFERENCE if n in available]
    extra = sorted((n for n in available if "flash" in n and not any(x in n for x in ("lite", "tts", "live", "audio", "image", "embed", "transcribe"))
                    and n not in picks), reverse=True)
    picks += extra
    # last resort: lighter models (faster, less accurate) so a busy day never stops the demo
    picks += sorted((n for n in available if "flash-lite" in n and "preview" not in n), reverse=True)
    if os.environ.get("GEMINI_MODEL"):
        first = os.environ["GEMINI_MODEL"]
        picks = [first] + [p for p in picks if p != first]
    _gemini_model_cache = picks or ["gemini-3.5-flash-lite"]
    print(f"[llm] Gemini models usable by this key, best first: {_gemini_model_cache[:6]}", flush=True)
    return _gemini_model_cache


def gemini_model(client=None) -> str:
    return gemini_candidates(client)[0]


def _call_gemini(system: str, parts: list[Part], max_tokens: int, model: str, timeout_s: float | None = None) -> tuple[str, str]:
    from google.genai import types
    client = _gemini_client(timeout_s)
    contents = []
    for p in parts:
        if p.text is not None:
            contents.append(types.Part.from_text(text=p.text))
        else:
            contents.append(types.Part.from_bytes(data=p.data, mime_type=p.mime))
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0,
        max_output_tokens=max_tokens,
        response_mime_type="application/json",
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    resp = client.models.generate_content(model=model, contents=contents, config=cfg)
    return resp.text or "", model


# ---------------------------------------------------------------- Claude
def _call_claude(system: str, parts: list[Part], max_tokens: int, model: str = CLAUDE_DEFAULT, timeout_s: float | None = None) -> tuple[str, str]:
    import anthropic
    key = _secret("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    client = anthropic.Anthropic(api_key=key, timeout=timeout_s or 600, max_retries=0)
    content = []
    for p in parts:
        if p.text is not None:
            content.append({"type": "text", "text": p.text})
        elif p.mime == "application/pdf":
            content.append({"type": "document", "source": {"type": "base64", "media_type": p.mime,
                                                            "data": base64.b64encode(p.data).decode()}})
        else:
            content.append({"type": "image", "source": {"type": "base64", "media_type": p.mime,
                                                         "data": base64.b64encode(p.data).decode()}})
    content.append({"type": "text", "text": "Respond with the JSON object only."})
    msg = client.messages.create(model=model, max_tokens=max_tokens, temperature=0, system=system,
                                 messages=[{"role": "user", "content": content}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text"), model


BUSY = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "overloaded", "high demand", "rate limit", "529",
        "timed out", "timeout", "deadline")
_cooldown: dict[str, float] = {}   # model -> time until which we skip it (it was busy / out of quota)
COOLDOWN_S = 300


def _ordered_models(prov: str, fast: bool) -> list[str]:
    if prov == "claude":
        return [os.environ.get("CLAUDE_MODEL", CLAUDE_DEFAULT), "claude-opus-5-5"]
    models = list(gemini_candidates())
    if fast:  # interactive features: a quick good answer beats a slow perfect one
        lite = [m for m in models if "lite" in m]
        models = lite + [m for m in models if m not in lite]
    now = time.time()
    ready = [m for m in models if _cooldown.get(m, 0) <= now]
    resting = [m for m in models if m not in ready]
    return ready + resting


def complete_json(system: str, parts: list[Part], max_tokens: int = 16000, retries: int = 2,
                  fast: bool = False, budget_s: float | None = None, on_status=None) -> LLMResult:
    """Call the model; if it is busy, move on quickly to the next model. Never hang longer than budget_s.

    fast=True is for interactive screens: lighter models first, short per-call timeout, ~2 minute total budget.
    """
    prov = provider()
    models = _ordered_models(prov, fast)
    budget_s = budget_s or (150 if fast else 900)
    per_call = 90 if fast else 420
    start, errors = time.time(), []

    def say(msg):
        print(f"[llm] {msg}", flush=True)
        if on_status:
            try:
                on_status(msg)
            except Exception:
                pass

    for model in models[:8]:
        for attempt in range(retries):
            left = budget_s - (time.time() - start)
            if left < 10:
                raise RuntimeError(f"The AI service didn't answer within {budget_s:.0f}s (models busy or out of free quota). "
                                   "Please try again in a minute. Tried: " + "; ".join(errors[-3:]))
            t0 = time.time()
            say(f"Asking {model}…" if attempt == 0 else f"Retrying {model}…")
            try:
                if prov == "claude":
                    text, used = _call_claude(system, parts, max_tokens, model, timeout_s=min(per_call, left))
                else:
                    text, used = _call_gemini(system, parts, max_tokens, model, timeout_s=min(per_call, left))
                return LLMResult(data=_parse_json(text), provider=prov, model=used,
                                 seconds=round(time.time() - t0, 1), raw_text=text)
            except Exception as e:
                msg = str(e)
                errors.append(f"{model}: {msg[:140]}")
                busy = any(b.lower() in msg.lower() for b in BUSY)
                bad_json = "JSON" in msg or "Expecting" in msg
                if busy:
                    _cooldown[model] = time.time() + COOLDOWN_S
                    say(f"{model} is busy or out of quota, switching model…")
                    break  # don't wait on a busy model: go straight to the next one
                if not bad_json:
                    say(f"{model} failed ({msg[:80]}), switching model…")
                    break
                time.sleep(2)
    raise RuntimeError(f"{prov}: all models failed. " + " | ".join(errors[-4:]))
