# Gloo AI Python Quickstart (pipenv)

This minimal example was built in response to the Slack thread in `#support-gloo-ai` (https://servant-io.slack.com/archives/C08QPAK2QAX/p1764093157738929) asking for a working Python snippet after a developer hit `403 forbidden` when calling the quickstart API.

## What this does

- Loads `GLOO_AI_CLIENT_ID` and `GLOO_AI_CLIENT_SECRET` from a local `.env`.
- Requests an OAuth token with the `api/access` scope.
- Calls the chat completions endpoint using `meta.llama3-70b-instruct-v1:0`.
- Prints the token expiration and the JSON completion response.

For the full walkthrough, see the official quickstart docs: https://docs.gloo.com/getting-started/quickstart-developers.

## Setup

1. Ensure Python 3.11 is available.
2. Create `.env` (already gitignored) with:
   ```
   GLOO_AI_CLIENT_ID=...
   GLOO_AI_CLIENT_SECRET=...
   ```
   The provided demo values are already placed in `.env` for convenience; replace if you have org-specific credentials.
3. Install deps and lock via pipenv:
   ```bash
   pipenv install --python 3.11
   ```

## Run

```bash
pipenv run gloo-chat
```

## Structured output + typed refusal handling (GAI-5626)

`structured_output.py` is a strict superset of the quickstart that demonstrates the platform contract for structured outputs and typed safety refusals against `gloo-anthropic-claude-haiku-4.5` (V2 endpoint). It defines a pydantic model, sends a `response_format: json_schema` request, and branches on the response shape:

- **Happy path** — `finish_reason="stop"` with JSON-stringified content. Pydantic validates the schema and the example prints the parsed object.
- **Refusal path** — `finish_reason="content_filter"` with `message.refusal` populated. The example prints the typed refusal without string-matching `error.text` or message content.

Run the example:

```bash
pipenv run gloo-structured "Plan a 3-day trip to Tokyo with two daily activities each day."
```

Set `GLOO_AI_BASE_URL` to point at a Porter preview env if you're testing against an `ai-api` build with the Phase 1 / Phase 2 flags flipped:

```bash
GLOO_AI_BASE_URL=https://dev-ai-api-XXXX.onporter.run pipenv run gloo-structured "..."
```

The unit tests in `tests/test_structured_output.py` cover the parser branches without hitting the network — run them with `pipenv run test`.

This file lands as the Python companion to GAI-5626 and stays alongside `main.py` rather than replacing it; `main.py` remains the v1 quickstart that the official docs link to. See [the architecture decision on GAI-5626](https://linear.app/gloo/issue/GAI-5626/ai-sdk-structured-output-anthropic-refusals-advertise) for why this is one of five companion PRs across the platform.

## Format

```bash
pipenv run format
```

Uses `black` via the Pipfile script to format the repository.

## Notes / troubleshooting

- A 403 usually means the token lacks the right scope or the Authorization header is malformed. This example uses `grant_type=client_credentials` with `scope=api/access` and sets `Authorization: Bearer <token>`, matching the published quickstart.
- If you rotate credentials, update `.env` and rerun.
