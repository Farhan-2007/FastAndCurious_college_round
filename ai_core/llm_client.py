
import json
import os
import re
import time

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(self, api_key=None, model=None, timeout=None, max_tokens=3000):
        self._api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model or os.environ.get("SO_LLM_MODEL", DEFAULT_MODEL)
        self.timeout = timeout or int(os.environ.get("SO_LLM_TIMEOUT", "60"))
        self.max_tokens = max_tokens

        if not self._api_key:
            raise LLMError("GROQ_API_KEY is missing from the environment.")

    def complete(self, system, user):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": self.max_tokens,
        }

        for attempt in range(3):
            try:
                response = requests.post(
                    API_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.timeout,
                )

                if response.status_code == 429:
                    try:
                        error_data = response.json()
                        error = error_data.get("error", {})
                        message = error.get("message", "")
                    except (ValueError, TypeError):
                        message = response.text[:500]

                    lower_message = message.lower()

                    # Daily quota errors should not be retried.
                    if (
                        "tokens per day" in lower_message
                        or "requests per day" in lower_message
                        or re.search(r"\btpd\b", lower_message)
                        or re.search(r"\brpd\b", lower_message)
                    ):
                        raise LLMError(
                            "Groq daily quota exceeded. Wait for the quota "
                            "to reset or choose a model with available quota. "
                            f"Details: {message[:300]}"
    )
                        raise LLMError(
                            "Groq daily quota exceeded. Wait for the quota "
                            "to reset or choose a model with available quota. "
                            f"Details: {message[:300]}"
                        )

                    # Retry temporary rate limits a limited number of times.
                    if attempt < 2:
                        retry_after = response.headers.get("Retry-After")
                        wait_seconds = None

                        try:
                            if retry_after is not None:
                                wait_seconds = float(retry_after)
                        except (TypeError, ValueError):
                            pass

                        if wait_seconds is None:
                            match = re.search(
                                r"try again in ([\d.]+)\s*s",
                                message,
                                re.IGNORECASE,
                            )
                            if match:
                                wait_seconds = float(match.group(1))

                        if wait_seconds is None:
                            wait_seconds = 15 * (attempt + 1)

                        time.sleep(min(max(wait_seconds, 1), 60))
                        continue

                    raise LLMError(
                        "Groq rate limit exceeded after retries. "
                        f"Details: {message[:300]}"
                    )

                if response.status_code in (500, 502, 503, 504):
                    if attempt < 2:
                        time.sleep(2 * (attempt + 1))
                        continue

                if not response.ok:
                    raise LLMError(
                        f"Groq API error ({response.status_code}): "
                        f"{response.text[:500]}"
                    )

                data = response.json()
                choice = data["choices"][0]
                message = choice.get("message", {})
                content = message.get("content")

                if choice.get("finish_reason") == "length":
                    raise LLMError(
                        "Groq response was truncated because the token limit "
                        "was reached. Increase max_tokens or reduce the prompt length."
                    )

                if not isinstance(content, str) or not content.strip():
                    raise LLMError(
                        "Groq returned an empty response. "
                        "Check the selected model and token limit."
                    )

                return content

            except requests.RequestException as exc:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue

                raise LLMError(f"Groq request failed: {exc}") from exc

            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise LLMError(
                    f"Unexpected Groq API response: {exc}"
                ) from exc

        raise LLMError("Groq request failed after retrying.")

    def complete_json(self, system, user):
        text = self.complete(system, user).strip()

        if text.startswith("```"):
            text = text.split("\n", 1)[-1]

            if text.endswith("```"):
                text = text[:-3].strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(
                f"Model returned invalid JSON: {exc}"
            ) from exc

        if not isinstance(result, dict):
            raise LLMError("Model response must be a JSON object.")

        return result

    @staticmethod
    def parse_json_object(text):
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Invalid JSON: {exc}") from exc

        if not isinstance(result, dict):
            raise LLMError("Expected a JSON object.")

        return result
