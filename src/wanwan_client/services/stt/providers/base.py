"""
Shared STT provider contracts and normalization helpers.
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.wanwan_client.shared.schemas import ProviderConfig, ProviderModelConfig

STT_MODE_SYNC_URL = "sync_url"
STT_MODE_SYNC_BASE64 = "sync_base64"
STT_MODE_ASYNC_URL = "async_url"
STT_MODE_ASYNC_BASE64 = "async_base64"

ALL_STT_REQUEST_MODES = (
    STT_MODE_SYNC_URL,
    STT_MODE_SYNC_BASE64,
    STT_MODE_ASYNC_URL,
    STT_MODE_ASYNC_BASE64,
)


@dataclass(slots=True)
class SttSegment:
    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    speaker: str | None = None
    confidence: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": self.text,
            "raw": self.raw,
        }
        if self.start_ms is not None:
            payload["start_ms"] = self.start_ms
        if self.end_ms is not None:
            payload["end_ms"] = self.end_ms
        if self.speaker is not None:
            payload["speaker"] = self.speaker
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        return payload


@dataclass(slots=True)
class SttUtterance:
    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    speaker: str | None = None
    confidence: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": self.text,
            "raw": self.raw,
        }
        if self.start_ms is not None:
            payload["start_ms"] = self.start_ms
        if self.end_ms is not None:
            payload["end_ms"] = self.end_ms
        if self.speaker is not None:
            payload["speaker"] = self.speaker
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        return payload


@dataclass(slots=True)
class SttProviderRequest:
    trace_id: str
    session_id: str
    provider_config: ProviderConfig
    model_config: ProviderModelConfig
    audio_ref: dict[str, Any]
    language_hint: str | None = None
    prompt: str | None = None
    response_format: str | None = None
    audio_format: str | None = None
    request_mode: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SttProviderResult:
    text: str
    is_final: bool = True
    utterances: list[SttUtterance] = field(default_factory=list)
    segments: list[SttSegment] = field(default_factory=list)
    request_id: str | None = None
    provider_job_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class SttProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        error_type: str,
        retryable: bool,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.error_type = error_type
        self.retryable = retryable
        self.details = details or {}


class SttProvider(ABC):
    ADAPTER_VERSION = "stt.provider.base.v1"

    @abstractmethod
    def transcribe(self, request: SttProviderRequest) -> SttProviderResult:
        raise NotImplementedError


def build_stt_stage_result(
    *,
    trace_id: str,
    session_id: str,
    status: str,
    provider_config: ProviderConfig,
    model_config: ProviderModelConfig,
    request: SttProviderRequest,
    result: SttProviderResult | None,
    duration_ms: int,
    adapter_version: str,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    utterances = [item.to_dict() for item in (result.utterances if result else [])]
    segments = [item.to_dict() for item in (result.segments if result else [])]

    payload = {
        "input": {
            "language_hint": request.language_hint,
            "prompt": request.prompt,
        },
        "output": {
            "text": result.text if result else "",
            "utterances": utterances,
            "segments": segments,
            "is_final": result.is_final if result else False,
        },
        "refs": {
            "audio_ref": request.audio_ref,
        },
        "options": {
            "response_format": request.response_format,
            "audio_format": request.audio_format,
            "request_mode": request.request_mode,
        },
    }

    return {
        "trace_id": trace_id,
        "session_id": session_id,
        "step": "stt",
        "status": status,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "payload": payload,
        "error": error,
        "meta": {
            "provider": provider_config.provider_id,
            "model": model_config.model_id,
            "capabilities": list(model_config.capabilities or provider_config.capabilities),
            "content_type": "text/plain",
            "protocol_version": "v0.3",
            "adapter_version": adapter_version,
            "duration_ms": duration_ms,
            "request_id": result.request_id if result else None,
            "provider_job_id": result.provider_job_id if result else None,
            "request_mode": request.request_mode,
            **(result.meta if result else {}),
        },
    }


def resolve_audio_ref_type(audio_ref: dict[str, Any]) -> str:
    ref_type = str(audio_ref.get("type", "")).strip()
    if not ref_type:
        raise SttProviderError(
            "audio_ref.type is required",
            code="STT_REF_INVALID",
            error_type="validation_error",
            retryable=False,
        )
    return ref_type


def get_remote_audio_url(audio_ref: dict[str, Any]) -> str:
    ref_type = resolve_audio_ref_type(audio_ref)
    if ref_type != "remote_url":
        raise SttProviderError(
            "Current provider requires a remote_url audio_ref, but the project has no local audio -> public URL bridge yet.",
            code="STT_REMOTE_URL_REQUIRED",
            error_type="validation_error",
            retryable=False,
            details={
                "audio_ref_type": ref_type,
                "next_action": "Add a resource publishing step before STT, then pass remote_url to the provider.",
            },
        )

    remote_url = str(audio_ref.get("value", "")).strip()
    if not remote_url:
        raise SttProviderError(
            "audio_ref.value is empty for remote_url input",
            code="STT_REF_INVALID",
            error_type="validation_error",
            retryable=False,
        )
    return remote_url


def get_base64_audio_data(audio_ref: dict[str, Any]) -> str:
    ref_type = resolve_audio_ref_type(audio_ref)
    if ref_type == "base64_inline":
        raw_data = str(audio_ref.get("value", "")).strip()
        if not raw_data:
            raise SttProviderError(
                "audio_ref.value is empty for base64_inline input",
                code="STT_REF_INVALID",
                error_type="validation_error",
                retryable=False,
            )
        return raw_data

    if ref_type == "local_path":
        file_path = get_local_audio_path(audio_ref)
        if not file_path.exists():
            raise SttProviderError(
                f"Local audio file not found: {file_path}",
                code="STT_FILE_ERROR",
                error_type="file_error",
                retryable=False,
            )
        return base64.b64encode(file_path.read_bytes()).decode("utf-8")

    raise SttProviderError(
        "Current provider requires base64 audio input. Supported audio_ref types are base64_inline and local_path.",
        code="STT_BASE64_REQUIRED",
        error_type="validation_error",
        retryable=False,
        details={
            "audio_ref_type": ref_type,
        },
    )


def resolve_request_mode(
    *,
    audio_ref: dict[str, Any],
    preferred_mode: str | None,
    supported_modes: tuple[str, ...],
) -> str:
    cleaned_supported = tuple(mode for mode in supported_modes if mode in ALL_STT_REQUEST_MODES)
    if not cleaned_supported:
        raise SttProviderError(
            "Provider declares no supported STT request modes.",
            code="STT_VALIDATION_ERROR",
            error_type="validation_error",
            retryable=False,
        )

    if preferred_mode:
        preferred_mode = preferred_mode.strip()
        if preferred_mode not in ALL_STT_REQUEST_MODES:
            raise SttProviderError(
                f"Unsupported STT request_mode: {preferred_mode}",
                code="STT_VALIDATION_ERROR",
                error_type="validation_error",
                retryable=False,
            )
        if preferred_mode not in cleaned_supported:
            raise SttProviderError(
                f"Provider does not support request_mode: {preferred_mode}",
                code="STT_MODE_UNSUPPORTED",
                error_type="validation_error",
                retryable=False,
                details={"supported_modes": list(cleaned_supported)},
            )
        validate_audio_ref_for_mode(audio_ref=audio_ref, request_mode=preferred_mode)
        return preferred_mode

    ref_type = resolve_audio_ref_type(audio_ref)
    mode_preference_order = {
        "remote_url": (
            STT_MODE_SYNC_URL,
            STT_MODE_ASYNC_URL,
        ),
        "base64_inline": (
            STT_MODE_SYNC_BASE64,
            STT_MODE_ASYNC_BASE64,
        ),
        "local_path": (
            STT_MODE_SYNC_BASE64,
            STT_MODE_ASYNC_BASE64,
        ),
    }
    for candidate in mode_preference_order.get(ref_type, ()):
        if candidate in cleaned_supported:
            validate_audio_ref_for_mode(audio_ref=audio_ref, request_mode=candidate)
            return candidate

    raise SttProviderError(
        f"Unable to infer STT request_mode for audio_ref.type={ref_type}.",
        code="STT_MODE_UNSUPPORTED",
        error_type="validation_error",
        retryable=False,
        details={"supported_modes": list(cleaned_supported)},
    )


def validate_audio_ref_for_mode(*, audio_ref: dict[str, Any], request_mode: str) -> None:
    if request_mode.endswith("_url"):
        get_remote_audio_url(audio_ref)
        return
    if request_mode.endswith("_base64"):
        get_base64_audio_data(audio_ref)
        return
    raise SttProviderError(
        f"Unsupported STT request_mode: {request_mode}",
        code="STT_VALIDATION_ERROR",
        error_type="validation_error",
        retryable=False,
    )


def get_local_audio_path(audio_ref: dict[str, Any]) -> Path:
    ref_type = resolve_audio_ref_type(audio_ref)
    if ref_type != "local_path":
        raise SttProviderError(
            "Current provider requires a local_path audio_ref.",
            code="STT_LOCAL_PATH_REQUIRED",
            error_type="validation_error",
            retryable=False,
            details={"audio_ref_type": ref_type},
        )

    raw_path = str(audio_ref.get("value", "")).strip()
    if not raw_path:
        raise SttProviderError(
            "audio_ref.value is empty for local_path input",
            code="STT_REF_INVALID",
            error_type="validation_error",
            retryable=False,
        )
    return Path(raw_path)
