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
2. Copy `.env.example` to `.env` (already gitignored) and populate it with:
   ```
   GLOO_AI_CLIENT_ID=...
   GLOO_AI_CLIENT_SECRET=...
   ```
   The example file contains placeholders only; replace them with your credentials (or use org-provided demo values).
3. Install deps and lock via pipenv:
   ```bash
   pipenv install --python 3.11
   ```

## Run

```bash
pipenv run gloo-chat
```

## Format

```bash
pipenv run format
```

Uses `black` via the Pipfile script to format the repository.

## Notes / troubleshooting

- A 403 usually means the token lacks the right scope or the Authorization header is malformed. This example uses `grant_type=client_credentials` with `scope=api/access` and sets `Authorization: Bearer <token>`, matching the published quickstart.
- If you rotate credentials, update `.env` and rerun.
- GitHub Actions picks up `GLOO_AI_CLIENT_ID` and `GLOO_AI_CLIENT_SECRET` from repository secrets (with non-sensitive fallback demo strings for forked PRs); add your own secrets to avoid noisy failures.
