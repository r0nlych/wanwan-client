"""
Unified TTS service entry for the internal `tts` stage.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from time import perf_counter
from typing import Any

import requests

from src.wanwan_client.core.config.runtime_config import RuntimeConfig
from src.wanwan_client.services.tts.providers.base import (
    TtsProviderError,
    TtsProviderRequest,
    build_tts_stage_result,
)
from src.wanwan_client.services.tts.providers.registry import TtsProviderRegistry


class TtsService:
    def __init__(
        self,
        runtime_config: RuntimeConfig,
        provider_registry: TtsProviderRegistry | None = None,
    ) -> None:
        self.runtime_config = runtime_config
        self.provider_registry = provider_registry or TtsProviderRegistry()

    def synthesize(
        self,
        *,
        text: str,
        session_id: str | None = None,
        provider_id: str | None = None,
        model_id: str | None = None,
        output_path: str | Path | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        resolved_session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        started_at = perf_counter()
        provider_config = None
        model_config = None
        provider = None
        request = None
        normalized_output_path = self._resolve_output_path(output_path, trace_id)

        try:
            provider_config, model_config = self.runtime_config.resolve_provider_and_model(
                "tts",
                provider_id=provider_id,
                model_id=model_id,
            )
            provider = self.provider_registry.resolve(provider_config)
            request = TtsProviderRequest(
                trace_id=trace_id,
                session_id=resolved_session_id,
                text=text,
                provider_config=provider_config,
                model_config=model_config,
                output_path=normalized_output_path,
                options=options or {},
            )
            result = provider.synthesize_to_file(request)
            return build_tts_stage_result(
                trace_id=trace_id,
                session_id=resolved_session_id,
                status="success",
                provider_config=provider_config,
                model_config=model_config,
                text=text,
                result=result,
                duration_ms=self._duration_ms(started_at),
                adapter_version=provider.ADAPTER_VERSION,
            )
        except Exception as error:
            if provider_config is None or model_config is None:
                return self._build_unresolved_failure_stage(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    text=text,
                    duration_ms=self._duration_ms(started_at),
                    error=error,
                )
            return build_tts_stage_result(
                trace_id=trace_id,
                session_id=resolved_session_id,
                status="failed",
                provider_config=provider_config,
                model_config=model_config,
                text=text,
                result=None,
                duration_ms=self._duration_ms(started_at),
                adapter_version=provider.ADAPTER_VERSION if provider else "phase6.tts.unknown.v1",
                error=self._normalize_error(error),
            )

    def _build_unresolved_failure_stage(
        self,
        *,
        trace_id: str,
        session_id: str,
        text: str,
        duration_ms: int,
        error: Exception,
    ) -> dict[str, Any]:
        return {
            "trace_id": trace_id,
            "session_id": session_id,
            "step": "tts",
            "status": "failed",
            "timestamp": self._now_iso(),
            "payload": {
                "input": {
                    "text": text,
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
                "content_type": "application/octet-stream",
                "protocol_version": "v0.3",
                "adapter_version": "phase6.tts.unresolved.v1",
                "duration_ms": duration_ms,
            },
        }

    def _normalize_error(self, error: Exception) -> dict[str, Any]:
        if isinstance(error, TtsProviderError):
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
                "code": "TTS_VALIDATION_ERROR",
                "message": str(error),
                "type": "validation_error",
                "retryable": False,
                "details": {},
                "raw_ref": None,
            }

        if isinstance(error, requests.Timeout):
            return {
                "code": "TTS_TIMEOUT",
                "message": str(error),
                "type": "provider_timeout",
                "retryable": True,
                "details": {},
                "raw_ref": None,
            }

        if isinstance(error, requests.HTTPError):
            response = error.response
            return {
                "code": "TTS_PROVIDER_ERROR",
                "message": str(error),
                "type": "provider_error",
                "retryable": False,
                "details": {
                    "status_code": response.status_code if response else None,
                    "provider_status_code": response.headers.get("X-Api-Status-Code") if response else None,
                    "provider_message": response.headers.get("X-Api-Message") if response else None,
                    "request_id": response.headers.get("X-Api-Request-Id") if response else None,
                    "logid": response.headers.get("X-Tt-Logid") if response else None,
                },
                "raw_ref": None,
            }

        if isinstance(error, requests.RequestException):
            return {
                "code": "TTS_NETWORK_ERROR",
                "message": str(error),
                "type": "network_error",
                "retryable": True,
                "details": {},
                "raw_ref": None,
            }

        return {
            "code": "TTS_UNKNOWN_ERROR",
            "message": str(error),
            "type": "unknown_error",
            "retryable": False,
            "details": {},
            "raw_ref": None,
        }

    def _resolve_output_path(self, output_path: str | Path | None, trace_id: str) -> Path:
        if output_path is None:
            return Path("data") / "tts" / f"{trace_id}_tts.wav"
        return Path(output_path)

    def _duration_ms(self, started_at: float) -> int:
        return int((perf_counter() - started_at) * 1000)

    def _now_iso(self) -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
