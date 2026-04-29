"""Structured output + refusal handling against Gloo AI V2 (GAI-5626 Phase 1).

Demonstrates the full contract a Python consumer should implement once the
platform fix lands:

  * Happy path — call ``/ai/v2/chat/completions`` with
    ``response_format={"type": "json_schema", ...}`` against
    ``gloo-anthropic-claude-haiku-4.5`` and parse the response into a
    pydantic model.
  * Refusal path — when Anthropic safety post-training fires, the platform
    returns ``finish_reason="content_filter"`` and ``message.refusal`` populated.
    Branch on that typed signal instead of string-matching ``error.text``.

Why this lives next to ``main.py`` instead of replacing it:
  ``main.py`` shows the v1 quickstart that the official docs link to.
  ``structured_output.py`` shows the v2 + refusal contract — a strict
  superset that quickstart users graduate to once they need typed objects.

Run it once the ai-api Phase 1 (REFUSAL_CONTRACT_ENABLED) and Phase 2
(STRUCTURED_OUTPUTS_ANTHROPIC_ENABLED) flags are flipped on the env you
point ``GLOO_AI_BASE_URL`` at:

    pipenv run python structured_output.py "Plan a 3-day trip to Tokyo"

Until both flags are flipped, the call still works but the model may fall
back to prompt-engineered JSON, and refusals come back as plain text in
``message.content`` instead of the typed contract this example expects.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

# Endpoints. Override GLOO_AI_BASE_URL to point at a Porter preview env.
GLOO_AI_BASE_URL = os.environ.get("GLOO_AI_BASE_URL", "https://platform.ai.gloo.com")
TOKEN_URL = f"{GLOO_AI_BASE_URL.rstrip('/')}/oauth2/token"
COMPLETIONS_V2_URL = f"{GLOO_AI_BASE_URL.rstrip('/')}/ai/v2/chat/completions"

# Pinned to the ticket's canonical canary model. Swap to any other Anthropic
# alias once Phase 2 expands beyond Haiku 4.5.
MODEL = "gloo-anthropic-claude-haiku-4.5"


class TripPlan(BaseModel):
    """Strict trip-plan schema. Every field is required and bounded.

    Pydantic generates a JSON schema from this model that is forwarded
    verbatim to the platform via ``response_format.json_schema.schema``.
    """

    destination: str = Field(min_length=1)
    days: int = Field(ge=1, le=30)
    activities: list[str] = Field(min_length=2, max_length=10)


@dataclass(frozen=True)
class HappyPath:
    """A schema-validated structured response."""

    plan: TripPlan
    finish_reason: str


@dataclass(frozen=True)
class RefusalPath:
    """A typed safety refusal from the model.

    ``refusal`` carries the original prose the model emitted; consumers can
    surface it to the user without re-inspecting message.content.
    """

    refusal: str
    finish_reason: str


CompletionOutcome = HappyPath | RefusalPath


def load_credentials() -> tuple[str, str]:
    load_dotenv()
    client_id = os.getenv("GLOO_AI_CLIENT_ID")
    client_secret = os.getenv("GLOO_AI_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing GLOO_AI_CLIENT_ID or GLOO_AI_CLIENT_SECRET environment variables."
        )
    return client_id, client_secret


def get_access_token(client_id: str, client_secret: str) -> str:
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    response = requests.post(
        TOKEN_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth}",
        },
        data={"grant_type": "client_credentials", "scope": "api/access"},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(
            "Token endpoint returned no access_token; check client credentials."
        )
    return token


def request_trip_plan(access_token: str, prompt: str) -> dict[str, Any]:
    """POST a structured-output request and return the raw JSON body.

    The request body wires ``response_format.type="json_schema"`` so the
    platform translates pydantic's schema into an Anthropic tool-call
    behind the scenes (Phase 2). The model's tool result comes back as
    JSON in ``choices[0].message.content``, ready for pydantic parsing.
    """
    response = requests.post(
        COMPLETIONS_V2_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "trip_plan",
                    "strict": True,
                    "schema": TripPlan.model_json_schema(),
                },
            },
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def parse_completion(body: dict[str, Any]) -> CompletionOutcome:
    """Translate the V2 response body into a typed outcome.

    The interesting branching lives here. With the GAI-5626 fix:

      * ``finish_reason="content_filter"`` plus ``message.refusal`` populated
        is the typed safety-refusal signal — pre-fix, refusals came back as
        ``finish_reason="stop"`` with prose in ``message.content``, which
        callers had to string-match.
      * ``finish_reason="stop"`` with valid JSON in ``message.content`` is
        the structured happy path. Pydantic does the schema validation.

    Anything else raises — a 200 response with neither shape is a contract
    violation worth crashing on so it surfaces in monitoring.
    """
    if not body.get("choices"):
        raise RuntimeError(
            f"V2 completion returned no choices; full body: {json.dumps(body)[:200]}"
        )

    choice = body["choices"][0]
    finish_reason = choice.get("finish_reason", "")
    message = choice.get("message", {})
    refusal = message.get("refusal")

    # Refusal path — typed signal, no string-matching required.
    if finish_reason == "content_filter" or refusal:
        return RefusalPath(
            refusal=refusal or message.get("content") or "(model declined)",
            finish_reason=finish_reason or "content_filter",
        )

    # Happy path — content is JSON-stringified, validate against the schema.
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(
            "Expected JSON-stringified content for structured output; "
            f"got finish_reason={finish_reason!r} content={content!r}"
        )
    try:
        plan = TripPlan.model_validate_json(content)
    except ValidationError as exc:
        raise RuntimeError(
            f"Schema validation failed for structured output: {exc}"
        ) from exc

    return HappyPath(plan=plan, finish_reason=finish_reason or "stop")


def run(prompt: str) -> CompletionOutcome:
    client_id, client_secret = load_credentials()
    token = get_access_token(client_id, client_secret)
    body = request_trip_plan(token, prompt)
    return parse_completion(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GAI-5626 — structured output + refusal contract example."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Plan a 3-day trip to Tokyo with two daily activities each day.",
        help="Prompt to send to the model.",
    )
    args = parser.parse_args(argv)

    outcome = run(args.prompt)

    if isinstance(outcome, HappyPath):
        print("Structured outcome (happy path):")
        print(json.dumps(outcome.plan.model_dump(), indent=2))
        print(f"finish_reason={outcome.finish_reason}")
        return 0

    print("Structured outcome (refusal path):")
    print(f"finish_reason={outcome.finish_reason}")
    print(f"refusal={outcome.refusal}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
