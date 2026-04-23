"""
Unified LLM service entry for the internal `llm` stage.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

import requests

from src.wanwan_client.core.config.runtime_config import RuntimeConfig
from src.wanwan_client.services.llm.providers import OpenAICompatibleLlmProvider


class LlmService:
    def __init__(
        self,
        runtime_config: RuntimeConfig,
        llm_provider: OpenAICompatibleLlmProvider | None = None,
    ) -> None:
        self.runtime_config = runtime_config
        self.llm_provider = llm_provider or OpenAICompatibleLlmProvider()

    def generate_reply(
        self,
        *,
        user_text: str,
        session_id: str | None = None,
        provider_id: str | None = None,
        model_id: str | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        resolved_session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        started_at = perf_counter()

        try:
            provider_config, model_config = self.runtime_config.resolve_provider_and_model(
                "llm",
                provider_id=provider_id,
                model_id=model_id,
            )
            messages = self._build_messages(
                user_text=user_text,
                system_prompt=system_prompt,
                provider_config=provider_config,
                model_config=model_config,
            )
            result = self.llm_provider.generate_reply(
                messages=messages,
                provider_config=provider_config,
                model_config=model_config,
            )
            return {
                "trace_id": trace_id,
                "session_id": resolved_session_id,
                "step": "llm",
                "status": "success",
                "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "payload": {
                    "input": {
                        "messages": messages,
                        "attachments": [],
                        "tools": [],
                    },
                    "output": {
                        "reply_text": result["reply_text"],
                        "reply_message": {
                            "role": "assistant",
                            "content": result["reply_text"],
                        },
                        "tool_calls": [],
                        "finish_reason": result.get("finish_reason"),
                    },
                    "refs": {},
                    "options": {
                        "temperature": self._optional_number(
                            model_config.extra.get("temperature", provider_config.extra.get("temperature"))
                        ),
                        "max_output_tokens": self._optional_int(
                            model_config.extra.get("max_output_tokens", model_config.max_output_tokens)
                        ),
                        "reasoning_enabled": self._optional_bool(
                            model_config.extra.get("reasoning_enabled", provider_config.extra.get("reasoning_enabled"))
                        ),
                    },
                },
                "error": None,
                "meta": {
                    "provider": provider_config.provider_id,
                    "model": model_config.model_id,
                    "capabilities": list(model_config.capabilities or provider_config.capabilities),
                    "content_type": "text/plain",
                    "protocol_version": "v0.3",
                    "adapter_version": self.llm_provider.ADAPTER_VERSION,
                    "duration_ms": self._duration_ms(started_at),
                    "request_id": result.get("request_id"),
                    "usage": result.get("raw_usage"),
                },
            }
        except Exception as error:
            return {
                "trace_id": trace_id,
                "session_id": resolved_session_id,
                "step": "llm",
                "status": "failed",
                "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "payload": {
                    "input": {
                        "messages": [],
                        "attachments": [],
                        "tools": [],
                    },
                    "output": {},
                    "refs": {},
                    "options": {},
                },
                "error": self._normalize_error(error),
                "meta": {
                    "provider": None,
                    "model": None,
                    "capabilities": [],
                    "content_type": "text/plain",
                    "protocol_version": "v0.3",
                    "adapter_version": "phase6.llm.service.v1",
                    "duration_ms": self._duration_ms(started_at),
                },
            }

    def _build_messages(
        self,
        *,
        user_text: str,
        system_prompt: str | None,
        provider_config: Any,
        model_config: Any,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        resolved_system_prompt = self._first_non_placeholder(
            system_prompt,
            model_config.extra.get("system_prompt"),
            provider_config.extra.get("system_prompt"),
        )
        if resolved_system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": resolved_system_prompt,
                }
            )
        messages.append(
            {
                "role": "user",
                "content": user_text,
            }
        )
        return messages

    def _normalize_error(self, error: Exception) -> dict[str, Any]:
        if isinstance(error, ValueError):
            return {
                "code": "LLM_VALIDATION_ERROR",
                "message": str(error),
                "type": "validation_error",
                "retryable": False,
                "details": {},
                "raw_ref": None,
            }

        if isinstance(error, requests.Timeout):
            return {
                "code": "LLM_TIMEOUT",
                "message": str(error),
                "type": "provider_timeout",
                "retryable": True,
                "details": {},
                "raw_ref": None,
            }

        if isinstance(error, requests.HTTPError):
            return {
                "code": "LLM_PROVIDER_ERROR",
                "message": str(error),
                "type": "provider_error",
                "retryable": False,
                "details": {
                    "status_code": error.response.status_code if error.response else None,
                },
                "raw_ref": None,
            }

        if isinstance(error, requests.RequestException):
            return {
                "code": "LLM_NETWORK_ERROR",
                "message": str(error),
                "type": "network_error",
                "retryable": True,
                "details": {},
                "raw_ref": None,
            }

        return {
            "code": "LLM_UNKNOWN_ERROR",
            "message": str(error),
            "type": "unknown_error",
            "retryable": False,
            "details": {},
            "raw_ref": None,
        }

    def _duration_ms(self, started_at: float) -> int:
        return int((perf_counter() - started_at) * 1000)

    def _first_non_placeholder(self, *values: Any) -> str | None:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if not text or text.startswith("("):
                continue
            return text
        return None

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

    def _optional_bool(self, value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        text = str(value).strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
        return None
