"""Provider selection and the Gemini adapter (HTTP is intercepted; no real call is made here)."""
import io
import json
import urllib.error

import pytest

from app import config, llm
from app.od_intelligence import LLM_SCHEMA


class FakeHTTP:
    """Replaces urllib.request.urlopen: records requests and plays back scripted replies."""

    def __init__(self, monkeypatch, replies):
        self.requests = []
        self.replies = list(replies)
        monkeypatch.setattr(llm.urllib.request, "urlopen", self)

    def __call__(self, request, timeout=None):
        self.requests.append({"url": request.full_url, "headers": dict(request.header_items()),
                              "body": json.loads(request.data)})
        reply = self.replies.pop(0)
        if isinstance(reply, int):
            raise urllib.error.HTTPError(request.full_url, reply, "error", {}, io.BytesIO(b'{"error":{}}'))
        if isinstance(reply, Exception):
            raise reply
        return _Response(reply)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def reply(text, finish="STOP"):
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}]}


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(config, "GEMINI_MODEL", "model-a,model-b")


# --------------------------------------------------------------------- selection

def test_provider_is_selected_by_configuration_alone(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    for name in ("anthropic", "gemini"):
        monkeypatch.setattr(config, "LLM_PROVIDER", name)
        assert llm.available() is False and llm.complete_text("s", "u") is None

    monkeypatch.setattr(config, "GEMINI_API_KEY", "g-key")
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    assert llm.available() is False            # a Gemini key does not enable the Anthropic provider
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    assert llm.available() is True

    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "a-key")
    assert llm.available() is False            # ...and the reverse
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    assert llm.available() is True
    monkeypatch.setattr(config, "LLM_PROVIDER", "something-else")
    assert llm.available() is False


def test_each_provider_gets_only_its_own_calls(monkeypatch):
    seen = []
    monkeypatch.setattr(llm, "_call_gemini", lambda *a, **k: seen.append("gemini") or "g")
    monkeypatch.setattr(llm, "_call_anthropic", lambda *a, **k: seen.append("anthropic") or "a")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "g-key")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "a-key")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    assert llm.complete_text("s", "u") == "g"
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    assert llm.complete_text("s", "u") == "a"
    assert seen == ["gemini", "anthropic"]


# --------------------------------------------------------------------- Gemini request shape

def test_gemini_request_shape_and_key_in_header_not_url(gemini, monkeypatch):
    http = FakeHTTP(monkeypatch, [reply("Hello there")])
    assert llm.complete_text("You are helpful.", "Hi", max_tokens=300) == "Hello there"
    sent = http.requests[0]
    assert sent["url"].endswith("/models/model-a:generateContent") and "test-key" not in sent["url"]
    assert sent["headers"]["X-goog-api-key"] == "test-key"
    assert sent["body"]["systemInstruction"] == {"parts": [{"text": "You are helpful."}]}
    assert sent["body"]["contents"] == [{"role": "user", "parts": [{"text": "Hi"}]}]
    assert "responseSchema" not in sent["body"]["generationConfig"]
    assert llm.last_model == "model-a"


def test_gemini_structured_output_translates_the_json_schema(gemini, monkeypatch):
    payload = {"event_name": {"value": "X", "source": "extracted", "confidence": "high"}}
    http = FakeHTTP(monkeypatch, [reply(json.dumps(payload))])
    assert llm.complete_json("sys", "doc", LLM_SCHEMA) == payload
    gen = http.requests[0]["body"]["generationConfig"]
    assert gen["responseMimeType"] == "application/json"
    schema = gen["responseSchema"]
    assert "additionalProperties" not in json.dumps(schema)                 # unsupported by Gemini
    value = schema["properties"]["date"]["properties"]["value"]
    assert value == {"type": "string", "nullable": True}                    # was ["string", "null"]
    assert schema["required"] == ["event_name", "organizer", "date", "venue"]
    assert schema["properties"]["venue"]["properties"]["source"]["enum"] == ["extracted", "inferred", "not_found"]


def test_gemini_images_and_pdfs_are_sent_inline(gemini, monkeypatch):
    http = FakeHTTP(monkeypatch, [reply("transcript")])
    content = [llm.image_block(b"\x89PNGdata", "image/png"), llm.pdf_block(b"%PDF-1"),
               {"type": "text", "text": "Transcribe"}]
    assert llm.complete_text("sys", content) == "transcript"
    parts = http.requests[0]["body"]["contents"][0]["parts"]
    assert parts[0]["inline_data"]["mime_type"] == "image/png"
    assert parts[1]["inline_data"]["mime_type"] == "application/pdf"
    assert parts[2] == {"text": "Transcribe"}


# --------------------------------------------------------------------- Gemini failure handling

def test_gemini_falls_through_to_the_next_model_when_one_is_overloaded(gemini, monkeypatch):
    http = FakeHTTP(monkeypatch, [503, reply("from the second model")])
    assert llm.complete_text("s", "u") == "from the second model"
    assert [r["url"].split("/models/")[1] for r in http.requests] == ["model-a:generateContent", "model-b:generateContent"]
    assert llm.last_model == "model-b"


def test_gemini_retries_without_the_reasoning_setting_if_a_model_rejects_it(gemini, monkeypatch):
    http = FakeHTTP(monkeypatch, [400, reply("ok")])
    assert llm.complete_text("s", "u") == "ok"
    first, second = (r["body"]["generationConfig"] for r in http.requests)
    assert "thinkingConfig" in first and "thinkingConfig" not in second
    assert second["maxOutputTokens"] > first["maxOutputTokens"]
    assert all("model-a" in r["url"] for r in http.requests)


@pytest.mark.parametrize("replies", [
    [503, 503],                                   # every model overloaded
    [429, 429],                                   # rate limited
    [401],                                        # bad or revoked key
    [urllib.error.URLError("no network")],
    [TimeoutError()],
    [reply("partial answ", finish="MAX_TOKENS")],
    [reply("", finish="SAFETY")],
    [{"promptFeedback": {"blockReason": "SAFETY"}}],   # no candidates at all
    [reply("   ")],
    [RuntimeError("anything unexpected")],
])
def test_gemini_failures_return_none_so_callers_fall_back(gemini, monkeypatch, replies):
    FakeHTTP(monkeypatch, replies)
    assert llm.complete_text("s", "u") is None
    FakeHTTP(monkeypatch, replies)
    assert llm.complete_json("s", "u", LLM_SCHEMA) is None


def test_gemini_invalid_json_is_rejected(gemini, monkeypatch):
    FakeHTTP(monkeypatch, [reply("not json at all")])
    assert llm.complete_json("s", "u", LLM_SCHEMA) is None
    FakeHTTP(monkeypatch, [reply('["a list, not an object"]')])
    assert llm.complete_json("s", "u", LLM_SCHEMA) is None


# --------------------------------------------------------------------- end to end with the provider failing

def test_assistant_and_documents_fall_back_when_gemini_fails(api, gemini, monkeypatch):
    """Key present but every call fails: answers and extraction must be the deterministic ones."""
    http = FakeHTTP(monkeypatch, [503] * 40)
    out = api.post("stu1", "/api/ai/chat", json={"message": "What is my CGPA?"}).json()
    assert (out["response"], out["source"]) == ("Your current CGPA is 8.5.", "database")
    unknown = api.post("stu1", "/api/ai/chat", json={"message": "Who is the principal?"}).json()
    assert unknown["source"] == "help" and unknown["response"].startswith("I can help with")

    from tests.conftest import next_weekday
    day = next_weekday(0)
    text = f"Event: Tech Symposium\nDate: {day}\nVenue: Main Auditorium\n".encode()
    req = api.apply(files={"file": ("invite.txt", text, "text/plain")})
    assert req.status_code == 201
    doc = api.get("stu1", f"/api/student/od/requests/{req.json()['id']}").json()["documents"][0]
    assert doc["extraction_status"] == "done" and doc["extracted_fields"]["engine"] == "heuristic"
    assert len(http.requests) >= 3                     # the provider really was attempted each time


def test_removing_the_key_restores_the_deterministic_path(api, monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    http = FakeHTTP(monkeypatch, [])
    out = api.post("stu1", "/api/ai/chat", json={"message": "How many OD hours do I have left?"}).json()
    assert out["source"] == "database" and "40 hours remaining" in out["response"]
    assert http.requests == []                         # no key -> no network call is even attempted
