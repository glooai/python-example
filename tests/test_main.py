import base64
import json
from unittest.mock import MagicMock

import pytest

import main


def _fake_response(payload):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = payload
    return response


def test_load_credentials_reads_env(monkeypatch):
    monkeypatch.setenv("GLOO_AI_CLIENT_ID", "abc")
    monkeypatch.setenv("GLOO_AI_CLIENT_SECRET", "xyz")

    client_id, client_secret = main.load_credentials()

    assert client_id == "abc"
    assert client_secret == "xyz"


def test_load_credentials_missing(monkeypatch):
    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.delenv("GLOO_AI_CLIENT_ID", raising=False)
    monkeypatch.delenv("GLOO_AI_CLIENT_SECRET", raising=False)

    with pytest.raises(RuntimeError):
        main.load_credentials()


def test_get_access_token_posts_expected_payload(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, data=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        captured["timeout"] = timeout
        return _fake_response({"access_token": "token123"})

    monkeypatch.setattr(main.requests, "post", fake_post)

    token_data = main.get_access_token("client-id", "client-secret")

    assert token_data == {"access_token": "token123"}
    assert captured["url"] == main.TOKEN_URL
    assert captured["data"] == {
        "grant_type": "client_credentials",
        "scope": "api/access",
    }
    assert captured["timeout"] == 10
    assert captured["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    expected_auth = base64.b64encode(b"client-id:client-secret").decode()
    assert captured["headers"]["Authorization"] == f"Basic {expected_auth}"


def test_get_chat_completion_posts_expected_payload(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _fake_response({"choices": [{"message": {"content": "hello"}}]})

    monkeypatch.setattr(main.requests, "post", fake_post)

    response = main.get_chat_completion("token123", "Hi there!")

    assert response["choices"][0]["message"]["content"] == "hello"
    assert captured["url"] == main.CHAT_URL
    assert captured["headers"]["Authorization"] == "Bearer token123"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["json"]["model"] == main.MODEL
    assert captured["json"]["messages"][1]["content"] == "Hi there!"
    assert captured["timeout"] == 30


def test_describe_expiration_uses_expires_in(monkeypatch):
    monkeypatch.setattr(main.time, "time", lambda: 1_700_000_000)

    expiration = main.describe_expiration({"expires_in": 120})

    assert expiration == 1700000120


def test_main_happy_path(monkeypatch, capsys):
    monkeypatch.setattr(main, "load_credentials", lambda: ("id", "secret"))
    monkeypatch.setattr(main, "get_access_token", lambda *_: {"access_token": "tok"})
    monkeypatch.setattr(main, "describe_expiration", lambda _: 42)
    monkeypatch.setattr(main, "get_chat_completion", lambda *_: {"message": "ok"})

    main.main()

    out = capsys.readouterr().out
    assert "Token expires at (unix seconds): 42" in out
    assert json.dumps({"message": "ok"}, indent=2) in out
