
import json
import os
import time

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

        for attempt in range(2):
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

                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt == 0:
                        time.sleep(2)
                        continue

                if not response.ok:
                    raise LLMError(
                        f"Groq API error ({response.status_code}): "
                        f"{response.text[:500]}"
                    )

                data = response.json()
                return data["choices"][0]["message"]["content"]

            except requests.RequestException as exc:
                if attempt == 0:
                    time.sleep(2)
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
            raise LLMError(f"Model returned invalid JSON: {exc}") from exc

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
