"""Thin async client for the Meta Model API (OpenAI-compatible chat, image generation, speech-to-text)."""

import asyncio
import base64
import json
import logging
import os

import httpx

BASE = os.environ.get("MUSE_BASE_URL", "https://api.meta.ai/v1")
FAST = os.environ.get("MUSE_FAST_MODEL", "muse-spark-1.3")
AGENT = os.environ.get("MUSE_AGENT_MODEL", "muse-wonder-1.0")
IMAGE = "muse-image-1.0"
ASR = "muse-voice-transcribe-1.0"

log = logging.getLogger("muse")
_client: httpx.AsyncClient | None = None


class MuseError(RuntimeError):
    pass


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        key = os.environ.get("MUSE_API_KEY", "")
        _client = httpx.AsyncClient(base_url=BASE, headers={"Authorization": f"Bearer {key}"},
                                    timeout=httpx.Timeout(120, connect=10))
    return _client


async def _post(path: str, **kw) -> dict:
    for attempt in range(3):
        try:
            r = await client().post(path, **kw)
        except httpx.TransportError as e:
            err = str(e)
        else:
            if r.status_code < 400:
                return r.json()
            err = f"{r.status_code} {r.text[:300]}"
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        log.warning("muse %s failed (attempt %d): %s", path, attempt + 1, err)
        await asyncio.sleep(1.5 * (attempt + 1))
    raise MuseError(err)


async def chat(messages: list, *, model: str = FAST, tools: list | None = None, schema: dict | None = None,
               effort: str | None = "low") -> dict:
    """Returns the assistant message dict (content, tool_calls)."""
    body: dict = {"model": model, "messages": messages}
    if effort:
        body["reasoning_effort"] = effort
    if tools:
        body["tools"] = tools
    if schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "strict": True, "schema": schema}}
    data = await _post("/chat/completions", json=body)
    u = data.get("usage") or {}
    log.info("muse chat model=%s prompt=%s completion=%s", model, u.get("prompt_tokens"), u.get("completion_tokens"))
    return data["choices"][0]["message"]


async def json_call(system: str, user, schema: dict, *, model: str = FAST, images: list[str] | None = None,
                    effort: str = "low") -> dict:
    """One structured call. `images` are data URLs. The user payload is always data, never instructions."""
    text = user if isinstance(user, str) else json.dumps(user, ensure_ascii=False)
    content = [{"type": "text", "text": text}] + [{"type": "image_url", "image_url": {"url": u}} for u in images or []]
    msg = await chat([{"role": "system", "content": system}, {"role": "user", "content": content}],
                     model=model, schema=schema, effort=effort)
    try:
        return json.loads(msg.get("content") or "")
    except json.JSONDecodeError as e:
        raise MuseError(f"bad json from model: {e}") from e


async def image(prompt: str) -> bytes:
    data = await _post("/images/generations", json={"model": IMAGE, "prompt": prompt, "n": 1})
    return base64.b64decode(data["data"][0]["b64_json"])


async def transcribe(wav: bytes) -> dict:
    """wav must be mono s16le at 16 or 24 kHz. Returns {transcript, audioDurationMs, turns}."""
    files = {"request": (None, json.dumps({"model": ASR, "audioEncoding": "WAV"}), "application/json"),
             "audio": ("audio.wav", wav, "audio/wav")}
    data = await _post("/asr/transcribe", files=files)
    if "error" in data:
        raise MuseError(data["error"].get("message", "asr error"))
    return data
