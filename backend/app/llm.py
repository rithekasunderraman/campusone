"""
Thin, optional wrapper around the Claude API.

Every caller treats the LLM as an enhancement: each function returns None when
no API key is configured, the call fails, times out, or the model declines, and
the caller then falls back to its deterministic path. Nothing in the
application depends on this module succeeding.
"""
import base64
import json
import logging
from typing import Optional, Union

from . import config

log = logging.getLogger("campusone.llm")

_client = None
# Models that accept the effort setting and server-side refusal fallbacks.
_CURRENT_GEN = ("claude-opus-5", "claude-sonnet-5-5", "claude-fable-5")


def available() -> bool:
    return bool(config.ANTHROPIC_API_KEY)


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=40.0, max_retries=1)
    return _client


def image_block(data: bytes, media_type: str) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                        "data": base64.standard_b64encode(data).decode("ascii")}}


def pdf_block(data: bytes) -> dict:
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                           "data": base64.standard_b64encode(data).decode("ascii")}}


def _call(system: str, content: Union[str, list], schema: Optional[dict] = None,
          max_tokens: int = 2000) -> Optional[str]:
    """One request to Claude. Returns the text of the reply, or None on any failure."""
    if not available():
        return None
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
