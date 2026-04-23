"""
Shared TTS provider contracts and result builders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from src.wanwan_client.shared.schemas import ProviderConfig, ProviderModelConfig


@dataclass(slots=True)
class TtsProviderRequest:
    trace_id: str
    session_id: str
    text: str
    provider_config: ProviderConfig
    model_config: ProviderModelConfig
    output_path: Path
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TtsProviderResult:
    audio_ref: dict[str, Any]
    voice: str | None = None
    voice_type: str | None = None
    response_format: str | None = None
    request_id: str | None = None
    logid: str | None = None
    byte_size: int | None = None
    duration_ms: int | None = None
    raw_details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TtsProviderError(Exception):
    code: str
    message: str
    error_type: str = "provider_error"
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


class BaseTtsProvider(Protocol):
    ADAPTER_VERSION: str

    def synthesize_to_file(self, request: TtsProviderRequest) -> TtsProviderResult:
        ...


def build_tts_stage_result(
    *,
    trace_id: str,
    session_id: str,
    status: str,
    provider_config: ProviderConfig,
    model_config: ProviderModelConfig,
    text: str,
    result: TtsProviderResult | None,
    duration_ms: int,
    adapter_version: str,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    audio_ref = result.audio_ref if result else {}
    return {
        "trace_id": trace_id,
        "session_id": session_id,
        "step": "tts",
        "status": status,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "payload": {
            "input": {
                "text": text,
            },
            "output": {
                "audio_ref": audio_ref,
            },
            "refs": {},
            "options": {
                "voice": result.voice if result else None,
                "voice_type": result.voice_type if result else None,
                "response_format": result.response_format if result else None,
                "sample_rate": _first_value(
                    model_config.extra.get("sample_rate"),
                    provider_config.extra.get("sample_rate"),
                ),
                "speed": _first_value(
                    model_config.extra.get("speed"),
                    provider_config.extra.get("speed"),
                ),
                "volume": _first_value(
                    model_config.extra.get("volume"),
                    provider_config.extra.get("volume"),
                ),
                "language": _first_value(
                    model_config.extra.get("language"),
                    provider_config.extra.get("language"),
                ),
            },
        },
        "error": error,
        "meta": {
            "provider": provider_config.provider_id,
            "model": model_config.model_id,
            "capabilities": list(model_config.capabilities or provider_config.capabilities),
            "content_type": audio_ref.get("mime_type", "application/octet-stream"),
            "protocol_version": "v0.3",
            "adapter_version": adapter_version,
            "duration_ms": duration_ms,
            "request_id": result.request_id if result else None,
            "logid": result.logid if result else None,
            "byte_size": result.byte_size if result else None,
            "audio_duration_ms": result.duration_ms if result else None,
        },
    }


def _first_value(*candidates: Any) -> Any:
    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate).strip()
        if not text or text.startswith("("):
            continue
        return candidate
    return None
