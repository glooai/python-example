import base64
import json
import logging
import os
import time
from typing import Any, Dict, Tuple

import requests
from dotenv import load_dotenv

TOKEN_URL = "https://platform.ai.gloo.com/oauth2/token"
CHAT_URL = "https://platform.ai.gloo.com/ai/v1/chat/completions"
MODEL = "meta.llama3-70b-instruct-v1:0"


def load_credentials() -> Tuple[str, str]:
    """Load client credentials from environment variables."""
    load_dotenv()
    client_id = os.getenv("GLOO_AI_CLIENT_ID")
    client_secret = os.getenv("GLOO_AI_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing GLOO_AI_CLIENT_ID or GLOO_AI_CLIENT_SECRET environment variables."
        )
    return client_id, client_secret


def get_access_token(client_id: str, client_secret: str) -> Dict[str, Any]:
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
    return response.json()


def get_chat_completion(access_token: str, prompt: str) -> Dict[str, Any]:
    response = requests.post(
        CHAT_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "You are a human-flourishing assistant."},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def describe_expiration(token_data: Dict[str, Any]) -> int:
    expires_in = token_data.get("expires_in")
    if expires_in is None:
        raise RuntimeError("Token response did not include expires_in")
    try:
        expires_in_seconds = int(expires_in)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("expires_in must be a number of seconds") from exc
    return int(time.time()) + expires_in_seconds


def main() -> None:
    prompt = "How do I discover my purpose?"
    client_id, client_secret = load_credentials()
    token_data = get_access_token(client_id, client_secret)

    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError("Token response did not include an access_token")

    try:
        expiration = describe_expiration(token_data)
        print(f"Token expires at (unix seconds): {expiration}")
    except RuntimeError as exc:
        logging.warning("Unable to determine token expiration: %s", exc)

    completion = get_chat_completion(access_token, prompt)
    print(json.dumps(completion, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        main()
    except Exception:
        logging.exception("Error running chat example")
        raise
