"""
Unit tests for src/utils/llm_client.py
All HTTP calls are mocked — no real Ollama server required.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.utils.llm_client import OllamaClient, validate_classification_response


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    return OllamaClient(
        endpoint="http://localhost:11434",
        model="qwen2.5:7b",
        temperature=0.1,
        max_tokens=256,
        max_retries=2,
        timeout=30,
    )


# ── OllamaClient.__init__ ─────────────────────────────────────────────────────


def test_init_defaults():
    c = OllamaClient()
    assert c.endpoint == "http://localhost:11434"
    assert c.model == "qwen2.5:7b"
    assert c.fallback_models == []
    assert c._available is None


def test_init_strips_trailing_slash():
    c = OllamaClient(endpoint="http://localhost:11434/")
    assert c.endpoint == "http://localhost:11434"


def test_init_custom_fallbacks():
    c = OllamaClient(fallback_models=["llama3:8b"])
    assert c.fallback_models == ["llama3:8b"]


# ── is_available ──────────────────────────────────────────────────────────────


def test_is_available_true(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "qwen2.5:7b"}, {"name": "llama3:8b"}]}
    with patch("src.utils.llm_client.requests.get", return_value=mock_resp):
        assert client.is_available() is True


def test_is_available_model_not_in_list(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "llama3:8b"}]}
    with patch("src.utils.llm_client.requests.get", return_value=mock_resp):
        assert client.is_available() is False


def test_is_available_bad_status(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    with patch("src.utils.llm_client.requests.get", return_value=mock_resp):
        assert client.is_available() is False


def test_is_available_connection_error(client):
    with patch("src.utils.llm_client.requests.get", side_effect=ConnectionError("refused")):
        assert client.is_available() is False


def test_is_available_no_substring_match(client):
    """qwen2.5:7b must NOT match when only qwen2.5:72b is present."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "qwen2.5:72b"}]}
    with patch("src.utils.llm_client.requests.get", return_value=mock_resp):
        assert client.is_available() is False


# ── get_active_model ──────────────────────────────────────────────────────────


def test_get_active_model_primary_available(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "qwen2.5:7b"}]}
    with patch("src.utils.llm_client.requests.get", return_value=mock_resp):
        assert client.get_active_model() == "qwen2.5:7b"


def test_get_active_model_fallback(client):
    client.fallback_models = ["llama3:8b"]

    def side_effect(url, timeout):
        resp = MagicMock()
        resp.status_code = 200
        if "tags" in url:
            resp.json.return_value = {"models": [{"name": "llama3:8b"}]}
        return resp

    with patch("src.utils.llm_client.requests.get", side_effect=side_effect):
        assert client.get_active_model() == "llama3:8b"


def test_get_active_model_none_available(client):
    with patch("src.utils.llm_client.requests.get", side_effect=ConnectionError):
        assert client.get_active_model() is None


# ── generate ─────────────────────────────────────────────────────────────────


def test_generate_success(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"message": {"content": "hello world"}}
    mock_resp.raise_for_status = MagicMock()
    with patch("src.utils.llm_client.requests.post", return_value=mock_resp):
        text, ok = client.generate("sys", "user")
    assert ok is True
    assert text == "hello world"


def test_generate_retries_then_fails(client):
    client.max_retries = 2
    with patch("src.utils.llm_client.requests.post", side_effect=ConnectionError("down")):
        with patch("src.utils.llm_client.time.sleep"):
            text, ok = client.generate("sys", "user")
    assert ok is False
    assert text == ""


def test_generate_uses_explicit_model(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "ok"}}
    mock_resp.raise_for_status = MagicMock()
    with patch("src.utils.llm_client.requests.post", return_value=mock_resp) as mock_post:
        client.generate("sys", "user", model="llama3:8b")
    payload = mock_post.call_args[1]["json"]
    assert payload["model"] == "llama3:8b"


# ── generate_json ─────────────────────────────────────────────────────────────


def test_generate_json_valid(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "message": {"content": '{"domain": "Economics", "confidence": 0.9}'}
    }
    mock_resp.raise_for_status = MagicMock()
    with patch("src.utils.llm_client.requests.post", return_value=mock_resp):
        result, ok = client.generate_json("sys", "user", required_keys=["domain"])
    assert ok is True
    assert result["domain"] == "Economics"


def test_generate_json_missing_required_key(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": '{"confidence": 0.9}'}}
    mock_resp.raise_for_status = MagicMock()
    with patch("src.utils.llm_client.requests.post", return_value=mock_resp):
        result, ok = client.generate_json("sys", "user", required_keys=["domain"])
    assert ok is False
    assert result is None


def test_generate_json_invalid_json(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "not json at all"}}
    mock_resp.raise_for_status = MagicMock()
    with patch("src.utils.llm_client.requests.post", return_value=mock_resp):
        result, ok = client.generate_json("sys", "user")
    assert ok is False


def test_generate_json_llm_failure(client):
    with patch("src.utils.llm_client.requests.post", side_effect=ConnectionError):
        with patch("src.utils.llm_client.time.sleep"):
            result, ok = client.generate_json("sys", "user")
    assert ok is False
    assert result is None


# ── _extract_json ─────────────────────────────────────────────────────────────


def test_extract_json_plain():
    assert OllamaClient._extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_markdown_fence():
    text = '```json\n{"a": 1}\n```'
    assert OllamaClient._extract_json(text) == {"a": 1}


def test_extract_json_embedded_in_text():
    text = 'Here is the result: {"domain": "Economics"} — done.'
    assert OllamaClient._extract_json(text) == {"domain": "Economics"}


def test_extract_json_returns_none_on_garbage():
    assert OllamaClient._extract_json("no json here at all!!!") is None


# ── validate_classification_response ─────────────────────────────────────────


def test_validate_classification_valid():
    resp = {"domain": "Economics", "subcategory": "political_economy", "confidence": 0.85}
    ok, msg = validate_classification_response(resp)
    assert ok is True
    assert msg == ""


def test_validate_classification_invalid_domain():
    resp = {"domain": "Astrology", "subcategory": "anything", "confidence": 0.8}
    ok, msg = validate_classification_response(resp)
    assert ok is False
    assert "domain" in msg.lower()


def test_validate_classification_invalid_subcategory():
    resp = {"domain": "Economics", "subcategory": "NonExistent", "confidence": 0.8}
    ok, msg = validate_classification_response(resp)
    assert ok is False
    assert "subcategory" in msg.lower()


def test_validate_classification_bad_confidence():
    resp = {"domain": "Economics", "subcategory": "political_economy", "confidence": 1.5}
    ok, msg = validate_classification_response(resp)
    assert ok is False
    assert "confidence" in msg.lower()


def test_validate_classification_confidence_zero():
    resp = {"domain": "Economics", "subcategory": "political_economy", "confidence": 0.0}
    ok, msg = validate_classification_response(resp)
    assert ok is True


def test_validate_classification_missing_confidence():
    resp = {"domain": "Economics", "subcategory": "political_economy"}
    ok, msg = validate_classification_response(resp)
    assert ok is False
