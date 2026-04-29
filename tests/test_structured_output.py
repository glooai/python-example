"""Unit tests for the GAI-5626 structured output + refusal contract example."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import structured_output


def _fake_response(payload: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = payload
    response.status_code = status_code
    return response


def _completion_body(
    *, content: str | None, refusal: str | None, finish_reason: str
) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                    "refusal": refusal,
                },
                "finish_reason": finish_reason,
            }
        ]
    }


class TestParseCompletion:
    """The branching logic in parse_completion is the public contract; cover it directly."""

    def test_happy_path_returns_validated_plan(self):
        plan = {
            "destination": "Tokyo",
            "days": 3,
            "activities": ["sushi class", "sumo match", "shrine visit"],
        }
        body = _completion_body(
            content=json.dumps(plan), refusal=None, finish_reason="stop"
        )

        outcome = structured_output.parse_completion(body)

        assert isinstance(outcome, structured_output.HappyPath)
        assert outcome.plan.destination == "Tokyo"
        assert outcome.plan.days == 3
        assert outcome.plan.activities == plan["activities"]
        assert outcome.finish_reason == "stop"

    def test_refusal_path_via_finish_reason(self):
        body = _completion_body(
            content=None,
            refusal="I can't help with that request.",
            finish_reason="content_filter",
        )

        outcome = structured_output.parse_completion(body)

        assert isinstance(outcome, structured_output.RefusalPath)
        assert outcome.refusal == "I can't help with that request."
        assert outcome.finish_reason == "content_filter"

    def test_refusal_path_when_only_refusal_field_populated(self):
        # Defensive: even if finish_reason isn't normalized yet, a populated
        # message.refusal is reason enough to take the refusal branch.
        body = _completion_body(
            content="",
            refusal="I can't help with that.",
            finish_reason="stop",
        )

        outcome = structured_output.parse_completion(body)

        assert isinstance(outcome, structured_output.RefusalPath)
        assert outcome.refusal == "I can't help with that."

    def test_invalid_schema_raises(self):
        bad_plan = {
            "destination": "Tokyo",
            "days": 3,
            "activities": ["only-one"],
        }  # min 2
        body = _completion_body(
            content=json.dumps(bad_plan), refusal=None, finish_reason="stop"
        )

        with pytest.raises(RuntimeError, match="Schema validation failed"):
            structured_output.parse_completion(body)

    def test_missing_choices_raises(self):
        with pytest.raises(RuntimeError, match="no choices"):
            structured_output.parse_completion({})

    def test_missing_content_on_happy_finish_raises(self):
        body = _completion_body(content=None, refusal=None, finish_reason="stop")

        with pytest.raises(RuntimeError, match="JSON-stringified content"):
            structured_output.parse_completion(body)


class TestRequestTripPlan:
    """Verify the request body shape — this is the wire-level contract with ai-api."""

    def test_request_includes_response_format_json_schema(self, monkeypatch):
        captured: dict = {}

        def fake_post(
            url, headers, json, timeout
        ):  # noqa: A002 — match requests' signature
            captured["url"] = url
            captured["body"] = json
            return _fake_response(
                _completion_body(content="{}", refusal=None, finish_reason="stop")
            )

        monkeypatch.setattr(structured_output.requests, "post", fake_post)

        structured_output.request_trip_plan("test-token", "Plan a trip")

        assert captured["url"].endswith("/ai/v2/chat/completions")
        body = captured["body"]
        assert body["model"] == structured_output.MODEL
        rf = body["response_format"]
        assert rf["type"] == "json_schema"
        assert rf["json_schema"]["name"] == "trip_plan"
        assert rf["json_schema"]["strict"] is True
        assert "destination" in rf["json_schema"]["schema"]["properties"]


class TestLoadCredentials:
    def test_reads_env(self, monkeypatch):
        monkeypatch.setenv("GLOO_AI_CLIENT_ID", "abc")
        monkeypatch.setenv("GLOO_AI_CLIENT_SECRET", "xyz")
        assert structured_output.load_credentials() == ("abc", "xyz")

    def test_missing_raises(self, monkeypatch):
        monkeypatch.setattr(structured_output, "load_dotenv", lambda: None)
        monkeypatch.delenv("GLOO_AI_CLIENT_ID", raising=False)
        monkeypatch.delenv("GLOO_AI_CLIENT_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="Missing GLOO_AI_CLIENT_ID"):
            structured_output.load_credentials()
