"""
Thin, optional wrapper around an LLM provider.

Two providers sit behind the same interface, chosen by configuration alone:

    LLM_PROVIDER=anthropic   ANTHROPIC_API_KEY, LLM_MODEL       (Claude API, via the anthropic SDK)
    LLM_PROVIDER=gemini      GEMINI_API_KEY,    GEMINI_MODEL    (Google Gemini API, via HTTPS)

Every caller treats the LLM as an enhancement: each function returns None when
no key is configured for the selected provider, the call fails, times out, or
the model declines, and the caller then falls back to its deterministic path.
Nothing in the application depends on this module succeeding.

Callers build message content in one neutral shape (a string, or a list of
text / image / document blocks from the helpers below); each provider adapter
translates that shape for its own API.
"""
import base64
import json
import logging
import urllib.error
import urllib.request
from typing import Optional, Union

from . import config

log = logging.getLogger("campusone.llm")

_client = None
# Claude models that accept the effort setting and server-side refusal fallbacks.
_CURRENT_GEN = ("claude-opus-5", "claude-sonnet-5-5", "claude-fable-5")
last_model: Optional[str] = None   # which Gemini model answered the most recent call
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def provider() -> str:
    return config.LLM_PROVIDER


def available() -> bool:
    """True when the selected provider has a key configured."""
    if config.LLM_PROVIDER == "gemini":
        return bool(config.GEMINI_API_KEY)
    if config.LLM_PROVIDER == "anthropic":
        return bool(config.ANTHROPIC_API_KEY)
    return False


def image_block(data: bytes, media_type: str) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                        "data": base64.standard_b64encode(data).decode("ascii")}}


def pdf_block(data: bytes) -> dict:
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                           "data": base64.standard_b64encode(data).decode("ascii")}}


# ---------------------------------------------------------------------------
# Anthropic (Claude API)
# ---------------------------------------------------------------------------

def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=40.0, max_retries=1)
    return _client


def _call_anthropic(system: str, content: Union[str, list], schema: Optional[dict] = None,
                    max_tokens: int = 2000) -> Optional[str]:
    try:
        import anthropic
    except ImportError:
        return None
    model = config.LLM_MODEL
    kwargs = dict(model=model, max_tokens=max_tokens, system=system,
                  messages=[{"role": "user", "content": content}])
    output_config = {}
    if model.startswith(_CURRENT_GEN):
        # These tasks are short rewrites/extractions: low effort keeps them fast and cheap.
        output_config["effort"] = "low"
        # If a safety classifier declines, let the API retry on its default fallback model.
        kwargs["betas"] = ["server-side-fallback-2026-07-01"]
        kwargs["fallbacks"] = "default"
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    if output_config:
        kwargs["output_config"] = output_config
    try:
        client = _get_client()
        create = client.beta.messages.create if "betas" in kwargs else client.messages.create
        response = create(**kwargs)
    except anthropic.RateLimitError:
        log.warning("LLM rate limited; using the deterministic path.")
        return None
    except anthropic.APIStatusError as exc:
        log.warning("LLM API error %s; using the deterministic path.", exc.status_code)
        return None
    except anthropic.APIConnectionError:
        log.warning("LLM unreachable; using the deterministic path.")
        return None
    except Exception as exc:  # never let an optional enhancement break a request
        log.warning("LLM call failed (%s); using the deterministic path.", type(exc).__name__)
        return None
    if response.stop_reason in ("refusal", "max_tokens"):
        return None
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return text or None


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------

def _gemini_schema(schema: dict) -> dict:
    """Translate JSON Schema into the subset Gemini's responseSchema accepts.

    Gemini has no `additionalProperties` and expresses "string or null" as
    nullable rather than a type list.
    """
    if not isinstance(schema, dict):
        return schema
    out = {}
    for key, value in schema.items():
        if key == "additionalProperties":
            continue
        if key == "type" and isinstance(value, list):
            kinds = [v for v in value if v != "null"]
            out["type"] = kinds[0] if kinds else "string"
            if "null" in value:
                out["nullable"] = True
        elif key == "properties":
            out[key] = {name: _gemini_schema(sub) for name, sub in value.items()}
        elif key == "items":
            out[key] = _gemini_schema(value)
        else:
            out[key] = value
    return out


def _gemini_parts(content: Union[str, list]) -> list:
    if isinstance(content, str):
        return [{"text": content}]
    parts = []
    for block in content:
        if block.get("type") == "text":
            parts.append({"text": block["text"]})
        elif block.get("type") in ("image", "document"):
            source = block["source"]
            parts.append({"inline_data": {"mime_type": source["media_type"], "data": source["data"]}})
    return parts


def _gemini_post(model: str, payload: dict) -> dict:
    """POST one generateContent request. Raises urllib errors; returns the decoded JSON."""
    request = urllib.request.Request(
        GEMINI_ENDPOINT.format(model=model), data=json.dumps(payload).encode("utf-8"), method="POST",
        # The key goes in a header, never in the URL, so it cannot end up in access logs.
        headers={"Content-Type": "application/json", "x-goog-api-key": config.GEMINI_API_KEY})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read())


def _call_gemini(system: str, content: Union[str, list], schema: Optional[dict] = None,
                 max_tokens: int = 2000) -> Optional[str]:
    global last_model
    generation = {
        "maxOutputTokens": max(max_tokens, 1024),
        "temperature": 0.2,
        # These are short rewrites and extractions: skip the model's internal reasoning
        # pass, which otherwise triples the response time.
        "thinkingConfig": {"thinkingBudget": 0},
    }
    if schema is not None:
        generation["responseMimeType"] = "application/json"
        generation["responseSchema"] = _gemini_schema(schema)
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": _gemini_parts(content)}],
        "generationConfig": generation,
    }

    # GEMINI_MODEL may list several models, tried in order. Google's newest models are
    # sometimes overloaded (HTTP 503) or rate limited (429); the next one then answers.
    models = [m.strip() for m in config.GEMINI_MODEL.split(",") if m.strip()]
    data = None
    for model in models:
        try:
            try:
                data = _gemini_post(model, payload)
            except urllib.error.HTTPError as exc:
                if exc.code != 400:
                    raise
                # A model that cannot switch reasoning off rejects that setting: retry without
                # it, with room in the token budget for the reasoning it will now do.
                relaxed = dict(generation, maxOutputTokens=generation["maxOutputTokens"] + 4096)
                relaxed.pop("thinkingConfig")
                data = _gemini_post(model, dict(payload, generationConfig=relaxed))
            last_model = model
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404, 429, 500, 503) and model != models[-1]:
                log.info("Gemini model %s returned %s; trying the next configured model.", model, exc.code)
                continue
            log.warning("LLM API error %s; using the deterministic path.", exc.code)
            return None
        except (urllib.error.URLError, TimeoutError, OSError):
            log.warning("LLM unreachable; using the deterministic path.")
            return None
        except Exception as exc:  # never let an optional enhancement break a request
            log.warning("LLM call failed (%s); using the deterministic path.", type(exc).__name__)
            return None
    if data is None:
        return None
    try:
        candidate = data["candidates"][0]
    except (KeyError, IndexError, TypeError):
        return None   # blocked prompt or empty response
    if candidate.get("finishReason") not in (None, "STOP"):
        return None   # MAX_TOKENS, SAFETY, RECITATION...: do not trust a partial or blocked answer
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    return text or None


# ---------------------------------------------------------------------------
# Provider-neutral entry points
# ---------------------------------------------------------------------------

def _call(system: str, content: Union[str, list], schema: Optional[dict] = None,
          max_tokens: int = 2000) -> Optional[str]:
    """One request to the configured provider. Returns the reply text, or None on any failure."""
    if not available():
        return None
    if config.LLM_PROVIDER == "gemini":
        return _call_gemini(system, content, schema, max_tokens)
    return _call_anthropic(system, content, schema, max_tokens)


def complete_text(system: str, content: Union[str, list], max_tokens: int = 2000) -> Optional[str]:
    return _call(system, content, None, max_tokens)


def complete_json(system: str, content: Union[str, list], schema: dict, max_tokens: int = 2000) -> Optional[dict]:
    text = _call(system, content, schema, max_tokens)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None
