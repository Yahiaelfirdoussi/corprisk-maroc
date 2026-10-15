"""Extraction model routing: a cheap model first, a stronger one when it fails or looks incomplete.

Both providers (Anthropic, OpenAI) are replaced by mock HTTP transports; no key, no cost.
FICTITIOUS data.
"""
import json

import anthropic
import httpx2
import openai
import pytest

from corprisk import extraction as ex

FILES = [ex.UploadedFile("statuts.pdf", b"%PDF-1.4 fictional"), ex.UploadedFile("cnie.jpg", b"\xff\xd8fictional")]


def _result(classified=(0, 1), name="FICTIONAL Test SARL") -> ex.Extraction:
    return ex.Extraction(
        company_name=name, legal_form="SARL", ice="", rc="", city="", incorporation_date="", activity="",
        sector="other", directors=[], shareholders=[], financials=[], warnings=[],
        documents=[ex.DocumentInfo(file_index=i, doc_type="other", year=None, holder="", summary="")
                   for i in classified])


def _message(model, extraction=None, stop_reason="end_turn"):
    text = extraction.model_dump_json() if extraction else ""
    return httpx2.Response(200, json={
        "id": "msg_test", "type": "message", "role": "assistant", "model": model,
        "content": [{"type": "text", "text": text}] if text else [],
        "stop_reason": stop_reason, "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}})


@pytest.fixture
def api(monkeypatch):
    """Route each model to a scripted response; record the requests."""
    script, calls = {}, []

    def handler(request):
        body = json.loads(request.content)
        calls.append({"model": body["model"], "fallbacks": body.get("fallbacks")})
        return script[body["model"]](body["model"])

    real = anthropic.Anthropic
    monkeypatch.setattr(anthropic, "Anthropic", lambda: real(
        api_key="test", max_retries=0, http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler))))
    monkeypatch.setenv("EXTRACTION_PROVIDER", "anthropic")
    monkeypatch.delenv("EXTRACTION_MODEL", raising=False)
    monkeypatch.delenv("EXTRACTION_FALLBACK_MODEL", raising=False)
    return script, calls


def test_haiku_success_does_not_call_sonnet(api):
    script, calls = api
    script["claude-haiku-5-5"] = lambda m: _message(m, _result())
    result, note = ex.extract(FILES)
    assert result.company_name == "FICTIONAL Test SARL"
    assert calls == [{"model": "claude-haiku-5-5", "fallbacks": None}]
    assert note == "Read by claude-haiku-5-5."


@pytest.mark.parametrize("haiku_response", [
    lambda m: _message(m, stop_reason="refusal"),
    lambda m: httpx2.Response(529, json={"type": "error", "error": {"type": "overloaded_error", "message": "x"}}),
    lambda m: _message(m, _result(classified=(0,))),   # one file not classified
    lambda m: _message(m, _result(name="")),           # no company name
])
def test_sonnet_rereads_when_haiku_fails(api, haiku_response):
    script, calls = api
    script["claude-haiku-5-5"] = haiku_response
    script["claude-sonnet-5-5"] = lambda m: _message(m, _result())
    result, note = ex.extract(FILES)
    assert [c["model"] for c in calls] == ["claude-haiku-5-5", "claude-sonnet-5-5"]
    assert calls[1]["fallbacks"] == "default"   # Sonnet keeps the server-side refusal fallback
    assert "re-read by claude-sonnet-5-5" in note and result.warnings == []


def test_incomplete_sonnet_result_is_kept_with_warning(api):
    script, _ = api
    script["claude-haiku-5-5"] = lambda m: _message(m, _result(classified=(0,)))
    script["claude-sonnet-5-5"] = lambda m: _message(m, _result(classified=(0,)))
    result, _ = ex.extract(FILES)
    assert result.warnings == ["Check the extraction: not every file was classified."]


def test_both_models_fail(api):
    script, _ = api
    script["claude-haiku-5-5"] = script["claude-sonnet-5-5"] = lambda m: _message(m, stop_reason="refusal")
    with pytest.raises(ex.ExtractionError, match="claude-haiku-5-5.*claude-sonnet-5-5"):
        ex.extract(FILES)


def test_bad_key_does_not_trigger_fallback(api):
    script, calls = api
    script["claude-haiku-5-5"] = lambda m: httpx2.Response(
        401, json={"type": "error", "error": {"type": "authentication_error", "message": "bad key"}})
    with pytest.raises(ex.ExtractionError, match="ANTHROPIC_API_KEY"):
        ex.extract(FILES)
    assert len(calls) == 1


def test_fallback_can_be_disabled(api, monkeypatch):
    script, calls = api
    monkeypatch.setenv("EXTRACTION_FALLBACK_MODEL", "")
    script["claude-haiku-5-5"] = lambda m: _message(m, stop_reason="refusal")
    with pytest.raises(ex.ExtractionError, match="declined"):
        ex.extract(FILES)
    assert len(calls) == 1


# --- OpenAI -----------------------------------------------------------------------

def _oa_response(model, extraction=None, refusal=False, status="completed"):
    if refusal:
        content = [{"type": "refusal", "refusal": "I can't help with that."}]
    else:
        content = [{"type": "output_text", "text": extraction.model_dump_json() if extraction else "",
                    "annotations": []}]
    return httpx2.Response(200, json={
        "id": "resp_test", "object": "response", "created_at": 0, "model": model, "status": status,
        "output": [{"type": "message", "id": "msg_test", "status": "completed", "role": "assistant",
                    "content": content}],
        "parallel_tool_calls": True, "tool_choice": "auto", "tools": [], "error": None,
        "incomplete_details": None, "instructions": None, "metadata": {}, "temperature": None, "top_p": None})


@pytest.fixture
def oa(monkeypatch):
    script, calls = {}, []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        return script[body["model"]](body["model"])

    real = openai.OpenAI
    monkeypatch.setattr(openai, "OpenAI", lambda: real(
        api_key="test", max_retries=0, http_client=openai.DefaultHttpxClient(transport=httpx2.MockTransport(handler))))
    monkeypatch.setenv("EXTRACTION_PROVIDER", "openai")
    monkeypatch.delenv("EXTRACTION_MODEL", raising=False)
    monkeypatch.delenv("EXTRACTION_FALLBACK_MODEL", raising=False)
    return script, calls


def test_openai_luna_success_and_request_shape(oa):
    script, calls = oa
    script["gpt-6-luna"] = lambda m: _oa_response(m, _result())
    result, note = ex.extract(FILES)
    assert result.company_name == "FICTIONAL Test SARL" and note == "Read by gpt-6-luna."
    body = calls[0]
    assert [c["type"] for c in body["input"][0]["content"]] == ["input_file", "input_image", "input_text"]
    assert body["input"][0]["content"][0]["file_data"].startswith("data:application/pdf;base64,")
    assert body["text"]["format"]["type"] == "json_schema" and body["text"]["format"]["strict"] is True
    assert body["store"] is False and body["reasoning"] == {"effort": "medium"}


@pytest.mark.parametrize("luna_response", [
    lambda m: _oa_response(m, refusal=True),
    lambda m: _oa_response(m, _result(), status="incomplete"),
    lambda m: httpx2.Response(503, json={"error": {"message": "overloaded", "type": "server_error"}}),
    lambda m: _oa_response(m, _result(classified=(1,))),
])
def test_openai_sol_rereads_when_luna_fails(oa, luna_response):
    script, calls = oa
    script["gpt-6-luna"] = luna_response
    script["gpt-6.1-sol"] = lambda m: _oa_response(m, _result())
    result, note = ex.extract(FILES)
    assert [c["model"] for c in calls] == ["gpt-6-luna", "gpt-6.1-sol"]
    assert "re-read by gpt-6.1-sol" in note


def test_openai_bad_key(oa):
    script, calls = oa
    script["gpt-6-luna"] = lambda m: httpx2.Response(401, json={"error": {"message": "bad", "type": "invalid_request_error"}})
    with pytest.raises(ex.ExtractionError, match="OPENAI_API_KEY"):
        ex.extract(FILES)
    assert len(calls) == 1


def test_provider_follows_available_key(monkeypatch):
    monkeypatch.delenv("EXTRACTION_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert ex.provider() == "openai" and ex.api_key_variable() == "OPENAI_API_KEY"
    monkeypatch.setenv("EXTRACTION_PROVIDER", "mistral")
    with pytest.raises(ex.ExtractionError, match="EXTRACTION_PROVIDER"):
        ex.provider()
