import base64
import json
import os
from typing import Any, Dict, Tuple

import requests
from dotenv import load_dotenv
from jwt import decode as jwt_decode

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


def describe_expiration(access_token: str) -> int:
    decoded = jwt_decode(access_token, options={"verify_signature": False})
    return int(decoded.get("exp", 0))


def main() -> None:
    prompt = "How do I discover my purpose?"
    try:
        client_id, client_secret = load_credentials()
        token_data = get_access_token(client_id, client_secret)
        access_token = token_data["access_token"]
        expiration = describe_expiration(access_token)
        print(f"Token expires at (unix seconds): {expiration}")

        completion = get_chat_completion(access_token, prompt)
        print(json.dumps(completion, indent=2))
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
