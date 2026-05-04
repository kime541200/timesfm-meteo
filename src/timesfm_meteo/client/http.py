from __future__ import annotations

import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

_MISSING_URL = (
    "TIMESFM_API_URL is not set. Add it to .env or set the environment variable.\n"
    "Example: TIMESFM_API_URL=http://localhost:8000"
)
_MISSING_KEY = (
    "TIMESFM_API_KEY is not set. Add it to .env or set the environment variable."
)


def make_client(timeout: float = 30.0) -> httpx.Client:
    """Return a configured httpx.Client with auth header injected."""
    base_url = os.environ.get("TIMESFM_API_URL", "")
    api_key = os.environ.get("TIMESFM_API_KEY", "")

    if not base_url:
        print(_MISSING_URL, file=sys.stderr)
        sys.exit(1)
    if not api_key:
        print(_MISSING_KEY, file=sys.stderr)
        sys.exit(1)

    return httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )


def handle_response_error(resp: httpx.Response, resource: str = "") -> None:
    """Print a human-readable error and exit non-zero on HTTP errors."""
    if resp.status_code == 401:
        print("Error: API key is invalid or missing.", file=sys.stderr)
        sys.exit(1)
    if resp.status_code == 404:
        msg = f"Error: {resource} not found." if resource else "Error: resource not found."
        print(msg, file=sys.stderr)
        sys.exit(1)
    if resp.is_error:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        print(f"Error {resp.status_code}: {detail}", file=sys.stderr)
        sys.exit(1)
