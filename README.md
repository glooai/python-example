# Gloo AI Python Quickstart (pipenv)

This minimal example was built in response to the Slack thread in `#support-gloo-ai` (https://servant-io.slack.com/archives/C08QPAK2QAX/p1764093157738929) asking for a working Python snippet after a developer hit `403 forbidden` when calling the quickstart API.

## What this does

- Loads `GLOO_AI_CLIENT_ID` and `GLOO_AI_CLIENT_SECRET` from a local `.env`.
- Requests an OAuth token with the `api/access` scope.
- Calls the chat completions endpoint using `meta.llama3-70b-instruct-v1:0`.
- Prints the token expiration and the JSON completion response.

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

## Format

```bash
pipenv run format
```

Uses `black` via the Pipfile script to format the repository.

## Notes / troubleshooting

- A 403 usually means the token lacks the right scope or the Authorization header is malformed. This example uses `grant_type=client_credentials` with `scope=api/access` and sets `Authorization: Bearer <token>`, matching the published quickstart.
- If you rotate credentials, update `.env` and rerun.
