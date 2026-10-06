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
def _gemini_client():
    from google import genai
    key = _secret("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=key)


def gemini_model(client=None) -> str:
    """Pick the best Flash model this key can use (names change often, so we ask the API)."""
    global _gemini_model_cache
    if os.environ.get("GEMINI_MODEL"):
        return os.environ["GEMINI_MODEL"]
    if _gemini_model_cache:
        return _gemini_model_cache
    client = client or _gemini_client()
    try:
        available = {m.name.split("/")[-1] for m in client.models.list()}
    except Exception:
        available = set()
    for name in GEMINI_PREFERENCE:
        if name in available:
            _gemini_model_cache = name
            return name
    flash = sorted(n for n in available if "flash" in n and "lite" not in n and "tts" not in n
                   and "live" not in n and "audio" not in n and "image" not in n)
    _gemini_model_cache = flash[-1] if flash else "gemini-2.5-flash"
    return _gemini_model_cache


def _call_gemini(system: str, parts: list[Part], max_tokens: int) -> tuple[str, str]:
    from google.genai import types
    client = _gemini_client()
    model = gemini_model(client)
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
    )
    resp = client.models.generate_content(model=model, contents=contents, config=cfg)
    return resp.text or "", model


# ---------------------------------------------------------------- Claude
def _call_claude(system: str, parts: list[Part], max_tokens: int) -> tuple[str, str]:
    import anthropic
    key = _secret("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    client = anthropic.Anthropic(api_key=key)
    model = os.environ.get("CLAUDE_MODEL", CLAUDE_DEFAULT)
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


def complete_json(system: str, parts: list[Part], max_tokens: int = 16000, retries: int = 3) -> LLMResult:
    prov = provider()
    last = None
    for attempt in range(retries):
        t0 = time.time()
        try:
            if prov == "claude":
                text, model = _call_claude(system, parts, max_tokens)
            else:
                text, model = _call_gemini(system, parts, max_tokens)
            return LLMResult(data=_parse_json(text), provider=prov, model=model,
                             seconds=round(time.time() - t0, 1), raw_text=text)
        except Exception as e:  # rate limits, transient errors, malformed JSON
            last = e
            time.sleep(8 * (attempt + 1))
    raise RuntimeError(f"{prov} call failed after {retries} attempts: {last}")
