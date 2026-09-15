"""
OpenAI-compatible LLM provider 适配器。
"""

from __future__ import annotations

from typing import Any

from src.wanwan_client.infrastructure.http.openai_compatible_client import (
    OpenAICompatibleHttpClient,
)
from src.wanwan_client.services.llm.providers.base import BaseLlmProvider
from src.wanwan_client.shared.schemas import ProviderConfig, ProviderModelConfig


class OpenAICompatibleLlmProvider(BaseLlmProvider):
    """
    最小真实可跑 LLM 适配器。
    """

    ADAPTER_VERSION = "phase6.llm.openai_compatible.v1"

    def generate_reply(
        self,
        *,
        messages: list[dict[str, Any]],
        provider_config: ProviderConfig,
        model_config: ProviderModelConfig,
    ) -> dict[str, Any]:
        client = OpenAICompatibleHttpClient(provider_config)
        payload: dict[str, Any] = {
            "model": model_config.model_id,
            "messages": messages,
            "stream": False,
        }

        temperature = self._optional_number(
            model_config.extra.get("temperature", provider_config.extra.get("temperature"))
        )
        if temperature is not None:
            payload["temperature"] = temperature

        max_tokens = self._optional_int(
            model_config.extra.get("max_output_tokens", model_config.max_output_tokens)
        )
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        response = client.post_json(payload)
        data = response.json()
        reply_text = self._extract_reply_text(data)

        return {
            "reply_text": reply_text,
            "finish_reason": self._extract_finish_reason(data),
            "request_id": response.headers.get("x-request-id"),
            "raw_usage": data.get("usage"),
        }

    def _extract_reply_text(self, response_json: dict[str, Any]) -> str:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("LLM response missing choices")

        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text_value = item.get("text")
                    if isinstance(text_value, str):
                        text_parts.append(text_value)
            merged = "".join(text_parts).strip()
            if merged:
                return merged

        raise ValueError("LLM response missing message content")

    def _extract_finish_reason(self, response_json: dict[str, Any]) -> str | None:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        finish_reason = choices[0].get("finish_reason")
        return str(finish_reason) if finish_reason is not None else None

    def _optional_number(self, value: Any) -> float | int | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip()
        if not text or text.startswith("("):
            return None
        try:
            return float(text) if "." in text else int(text)
        except ValueError:
            return None

    def _optional_int(self, value: Any) -> int | None:
        number = self._optional_number(value)
        if number is None:
            return None
        return int(number)
