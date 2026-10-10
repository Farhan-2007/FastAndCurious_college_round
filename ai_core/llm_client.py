"""One reusable client for one hosted LLM (Anthropic Messages API).

Environment variables:
  ANTHROPIC_API_KEY   required - read at call time, never logged or returned
  SO_LLM_MODEL        optional - model name (default below)
  SO_LLM_TIMEOUT      optional - seconds per request (default 60)
  SO_LLM_MAX_TOKENS   optional - max output tokens (default 3000)
"""
import json
import os
import re
import time

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import requests

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"


class LLMError(Exception):
    """Any failure talking to the LLM or parsing its reply."""


class LLMClient:
    def __init__(self, api_key=None, model=None, timeout=None, max_tokens=None):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("SO_LLM_MODEL", DEFAULT_MODEL)
        self.timeout = float(timeout or os.environ.get("SO_LLM_TIMEOUT", 60))
        self.max_tokens = int(max_tokens or os.environ.get("SO_LLM_MAX_TOKENS", 3000))

    def complete(self, system: str, user: str) -> str:
        if not self._api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        payload = {"model": self.model, "max_tokens": self.max_tokens,
                   "system": system,
                   "messages": [{"role": "user", "content": user}]}
        headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}
        last = None
        for attempt in range(2):  # one retry for transient failures
            try:
                r = requests.post(API_URL, headers=headers, json=payload,
                                  timeout=self.timeout)
            except requests.RequestException as e:
                last = f"request failed: {type(e).__name__}"
            else:
                if r.status_code == 200:
                    try:
                        return "".join(b.get("text", "") for b in r.json()["content"])
                    except (KeyError, TypeError, ValueError):
                        raise LLMError("Unexpected response shape from LLM API")
                last = f"API error {r.status_code}: {r.text[:200]}"
                if r.status_code not in (429, 500, 502, 503, 529):
                    break  # not transient, don't retry
            if attempt == 0:
                time.sleep(2)
        raise LLMError(f"LLM call failed ({last})")

    def complete_json(self, system: str, user: str) -> dict:
        """Call the LLM and return a parsed JSON object; retries once if malformed."""
        err = None
        for attempt in range(2):
            prompt = user if attempt == 0 else (
                user + "\n\nYour previous reply was not valid JSON. "
                       "Reply with ONLY the JSON object, nothing else.")
            try:
                return parse_json_object(self.complete(system, prompt))
            except ValueError as e:
                err = e
        raise LLMError(f"LLM returned malformed JSON twice: {err}")


def parse_json_object(text: str) -> dict:
    """Parse a JSON object from LLM text, tolerating ``` fences and chatter."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    obj = json.loads(text[start:end + 1])  # json.JSONDecodeError is a ValueError
    if not isinstance(obj, dict):
        raise ValueError("JSON root is not an object")
    return obj