"""Small OpenAI-compatible LLM client used by the patch generator."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 60
    temperature: float = 0.0


class LLMClientError(RuntimeError):
    pass


def load_llm_config_from_env() -> LLMConfig | None:
    api_key = os.getenv("AI_CODING_LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    if os.getenv("AI_CODING_LLM_BASE_URL"):
        base_url = os.environ["AI_CODING_LLM_BASE_URL"]
    elif os.getenv("DEEPSEEK_API_KEY"):
        base_url = "https://api.deepseek.com"
    else:
        base_url = "https://api.openai.com/v1"

    if os.getenv("AI_CODING_LLM_MODEL"):
        model = os.environ["AI_CODING_LLM_MODEL"]
    elif os.getenv("DEEPSEEK_API_KEY"):
        model = "deepseek-chat"
    else:
        model = "gpt-4.1-mini"

    timeout = int(os.getenv("AI_CODING_LLM_TIMEOUT", "60"))
    temperature = float(os.getenv("AI_CODING_LLM_TEMPERATURE", "0"))
    return LLMConfig(api_key=api_key, base_url=base_url, model=model, timeout_seconds=timeout, temperature=temperature)


class OpenAICompatibleClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @property
    def chat_completions_url(self) -> str:
        return f"{self.config.base_url.rstrip('/')}/chat/completions"

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "stream": False,
        }
        request = urllib.request.Request(
            self.chat_completions_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LLMClientError(f"LLM HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise LLMClientError(f"LLM request failed: {exc}") from exc

        try:
            data = json.loads(raw)
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMClientError(f"unexpected LLM response shape: {raw[:500]}") from exc
