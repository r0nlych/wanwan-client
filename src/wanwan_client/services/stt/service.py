"""
Unified STT service entry for the internal `stt` stage.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

import requests

from src.wanwan_client.core.config.runtime_config import RuntimeConfig
from src.wanwan_client.services.stt.providers.base import (
    SttProviderError,
    SttProviderRequest,
    build_stt_stage_result,
)
from src.wanwan_client.services.stt.providers.registry import SttProviderRegistry


class SttService:
    def __init__(
        self,
        runtime_config: RuntimeConfig,
        provider_registry: SttProviderRegistry | None = None,
    ) -> None:
        self.runtime_config = runtime_config
        self.provider_registry = provider_registry or SttProviderRegistry()

    def transcribe(
        self,
        *,
        audio_ref: dict[str, Any],
        session_id: str | None = None,
        provider_id: str | None = None,
        model_id: str | None = None,
        language_hint: str | None = None,
        prompt: str | None = None,
        response_format: str | None = None,
        audio_format: str | None = None,
        request_mode: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        resolved_session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        started_at = perf_counter()
        provider_config = None
        model_config = None
        provider = None
        request = None
        try:
            provider_config, model_config = self.runtime_config.resolve_provider_and_model(
                "stt",
                provider_id=provider_id,
                model_id=model_id,
            )
            provider = self.provider_registry.resolve(provider_config)

            merged_language_hint = self._first_value(
                language_hint,
                model_config.extra.get("language_hint"),
                provider_config.extra.get("language_hint"),
            )
            merged_prompt = self._first_value(
                prompt,
                model_config.extra.get("prompt"),
                provider_config.extra.get("prompt"),
            )
            merged_response_format = self._first_value(
                response_format,
                model_config.extra.get("response_format"),
                provider_config.extra.get("response_format"),
            )
            merged_audio_format = self._first_value(
                audio_format,
                model_config.extra.get("audio_format"),
                provider_config.extra.get("audio_format"),
            )
            merged_request_mode = self._first_value(
                request_mode,
                (options or {}).get("request_mode") if options else None,
                model_config.extra.get("request_mode"),
                provider_config.extra.get("request_mode"),
            )

            request = SttProviderRequest(
                trace_id=trace_id,
                session_id=resolved_session_id,
                provider_config=provider_config,
                model_config=model_config,
                audio_ref=audio_ref,
                language_hint=merged_language_hint,
                prompt=merged_prompt,
                response_format=merged_response_format,
                audio_format=merged_audio_format,
                request_mode=merged_request_mode,
                options=options or {},
            )
            result = provider.transcribe(request)
            return build_stt_stage_result(
                trace_id=trace_id,
                session_id=resolved_session_id,
                status="success",
                provider_config=provider_config,
                model_config=model_config,
                request=request,
                result=result,
                duration_ms=self._duration_ms(started_at),
                adapter_version=provider.ADAPTER_VERSION,
            )
        except Exception as error:
            if provider_config is None or model_config is None or request is None:
                return self._build_unresolved_failure_stage(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    audio_ref=audio_ref,
                    duration_ms=self._duration_ms(started_at),
                    error=error,
                )
            return build_stt_stage_result(
                trace_id=trace_id,
                session_id=resolved_session_id,
                status="failed",
                provider_config=provider_config,
                model_config=model_config,
                request=request,
                result=None,
                duration_ms=self._duration_ms(started_at),
                adapter_version=provider.ADAPTER_VERSION,
                error=self._normalize_error(error),
            )

    def _build_unresolved_failure_stage(
        self,
        *,
        trace_id: str,
        session_id: str,
        audio_ref: dict[str, Any],
        duration_ms: int,
        error: Exception,
    ) -> dict[str, Any]:
        return {
            "trace_id": trace_id,
            "session_id": session_id,
            "step": "stt",
            "status": "failed",
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "payload": {
                "input": {
                    "language_hint": None,
                    "prompt": None,
                },
                "output": {
                    "text": "",
                    "utterances": [],
                    "segments": [],
                    "is_final": False,
                },
                "refs": {
                    "audio_ref": audio_ref,
                },
                "options": {
                    "response_format": None,
                    "audio_format": None,
                },
            },
            "error": self._normalize_error(error),
            "meta": {
                "provider": None,
                "model": None,
                "capabilities": [],
                "content_type": "text/plain",
                "protocol_version": "v0.3",
                "adapter_version": "phase6.stt.unresolved.v1",
                "duration_ms": duration_ms,
            },
        }

    def _normalize_error(self, error: Exception) -> dict[str, Any]:
        if isinstance(error, SttProviderError):
            return {
                "code": error.code,
                "message": str(error),
                "type": error.error_type,
                "retryable": error.retryable,
                "details": error.details,
                "raw_ref": None,
            }

        if isinstance(error, ValueError):
            return {
                "code": "STT_VALIDATION_ERROR",
                "message": str(error),
                "type": "validation_error",
                "retryable": False,
                "details": {},
                "raw_ref": None,
            }

        if isinstance(error, requests.Timeout):
            return {
                "code": "STT_TIMEOUT",
                "message": str(error),
                "type": "provider_timeout",
                "retryable": True,
                "details": {},
                "raw_ref": None,
            }

        if isinstance(error, requests.HTTPError):
            response = error.response
            return {
                "code": "STT_PROVIDER_ERROR",
                "message": str(error),
                "type": "provider_error",
                "retryable": False,
                "details": {
                    "status_code": response.status_code if response else None,
                    "provider_status_code": response.headers.get("X-Api-Status-Code") if response else None,
                    "provider_message": response.headers.get("X-Api-Message") if response else None,
                    "request_id": response.headers.get("X-Api-Request-Id") if response else None,
                },
                "raw_ref": None,
            }

        if isinstance(error, requests.RequestException):
            return {
                "code": "STT_NETWORK_ERROR",
                "message": str(error),
                "type": "network_error",
                "retryable": True,
                "details": {},
                "raw_ref": None,
            }

        return {
            "code": "STT_UNKNOWN_ERROR",
            "message": str(error),
            "type": "unknown_error",
            "retryable": False,
            "details": {},
            "raw_ref": None,
        }

    def _duration_ms(self, started_at: float) -> int:
        return int((perf_counter() - started_at) * 1000)

    def _first_value(self, *candidates: Any) -> str | None:
        for candidate in candidates:
            if candidate is None:
                continue
            text = str(candidate).strip()
            if not text or text.startswith("("):
                continue
            return text
        return None
