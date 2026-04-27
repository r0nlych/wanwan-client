"""
音频输入 -> STT -> LLM -> TTS -> 本地播放 的最小后端编排。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import requests

from src.wanwan_client.core.config.runtime_config import RuntimeConfig
from src.wanwan_client.desktop.playback import LocalAudioPlayer
from src.wanwan_client.services.llm.providers import OpenAICompatibleLlmProvider
from src.wanwan_client.services.stt.providers.base import (
    SttProviderRequest,
    build_stt_stage_result,
)
from src.wanwan_client.services.stt.providers.registry import SttProviderRegistry
from src.wanwan_client.services.tts.providers import TtsProviderRegistry
from src.wanwan_client.services.tts.providers.base import (
    TtsProviderRequest,
    build_tts_stage_result,
)


class VoiceAudioPipeline:
    """
    最小真实可跑后端语音链路。
    """

    PROTOCOL_VERSION = "v0.3"

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        stt_provider_registry: SttProviderRegistry | None = None,
        llm_provider: OpenAICompatibleLlmProvider | None = None,
        tts_provider_registry: TtsProviderRegistry | None = None,
        audio_player: LocalAudioPlayer | None = None,
    ) -> None:
        self.runtime_config = runtime_config
        self.stt_provider_registry = stt_provider_registry or SttProviderRegistry()
        self.llm_provider = llm_provider or OpenAICompatibleLlmProvider()
        self.tts_provider_registry = tts_provider_registry or TtsProviderRegistry()
        self.audio_player = audio_player or LocalAudioPlayer()

    def run(self, audio_path: str | Path, session_id: str | None = None) -> dict[str, Any]:
        trace_id = self._build_trace_id()
        resolved_session_id = session_id or self._build_session_id()
        stages: list[dict[str, Any]] = []
        normalized_audio_path = Path(audio_path)
        audio_ref = {
            "type": "local_path",
            "value": str(normalized_audio_path).replace("\\", "/"),
            "mime_type": self._guess_mime_type(normalized_audio_path),
        }
        stt_request = None
        llm_messages: list[dict[str, Any]] = []
        tts_input_text = ""

        stt_started = perf_counter()
        try:
            stt_provider_config, stt_model = self.runtime_config.resolve_provider_and_model("stt")
            stt_provider = self.stt_provider_registry.resolve(stt_provider_config)
            stt_request = SttProviderRequest(
                trace_id=trace_id,
                session_id=resolved_session_id,
                provider_config=stt_provider_config,
                model_config=stt_model,
                audio_ref=audio_ref,
                language_hint=self._first_value(
                    stt_model.extra.get("language_hint"),
                    stt_provider_config.extra.get("language_hint"),
                ),
                prompt=self._first_value(
                    stt_model.extra.get("prompt"),
                    stt_provider_config.extra.get("prompt"),
                ),
                response_format=self._first_value(
                    stt_model.extra.get("response_format"),
                    stt_provider_config.extra.get("response_format"),
                ),
                audio_format=self._resolve_audio_format(normalized_audio_path, stt_model, stt_provider_config),
                request_mode=self._first_value(
                    stt_model.extra.get("request_mode"),
                    stt_provider_config.extra.get("request_mode"),
                ),
                options={},
            )
            stt_result = stt_provider.transcribe(stt_request)
            stages.append(
                build_stt_stage_result(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    status="success",
                    provider_config=stt_provider_config,
                    model_config=stt_model,
                    request=stt_request,
                    result=stt_result,
                    duration_ms=self._duration_ms(stt_started),
                    adapter_version=stt_provider.ADAPTER_VERSION,
                )
            )
        except Exception as error:
            stages.append(
                self._build_failure_stage(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    step="stt",
                    started_at=stt_started,
                    error=error,
                    payload={
                        "input": {
                            "language_hint": stt_request.language_hint if stt_request else None,
                            "prompt": stt_request.prompt if stt_request else None,
                        },
                        "output": {},
                        "refs": {
                            "audio_ref": audio_ref,
                        },
                        "options": {
                            "response_format": stt_request.response_format if stt_request else None,
                            "audio_format": stt_request.audio_format if stt_request else None,
                            "request_mode": stt_request.request_mode if stt_request else None,
                        },
                    },
                )
            )
            return self._build_pipeline_result(trace_id, resolved_session_id, stages)

        llm_started = perf_counter()
        try:
            llm_provider_config, llm_model = self.runtime_config.resolve_provider_and_model("llm")
            llm_messages = self._build_messages(
                user_text=stt_result.text,
                system_prompt=self._first_value(
                    llm_model.extra.get("system_prompt"),
                    llm_provider_config.extra.get("system_prompt"),
                ),
            )
            llm_result = self.llm_provider.generate_reply(
                messages=llm_messages,
                provider_config=llm_provider_config,
                model_config=llm_model,
            )
            stages.append(
                self._build_stage_result(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    step="llm",
                    status="success",
                    payload={
                        "input": {
                            "messages": llm_messages,
                            "attachments": [],
                            "tools": [],
                        },
                        "output": {
                            "reply_text": llm_result["reply_text"],
                            "reply_message": {
                                "role": "assistant",
                                "content": llm_result["reply_text"],
                            },
                            "tool_calls": [],
                            "finish_reason": llm_result.get("finish_reason"),
                        },
                        "refs": {},
                        "options": {
                            "temperature": self._optional_number(
                                llm_model.extra.get("temperature", llm_provider_config.extra.get("temperature"))
                            ),
                            "max_output_tokens": self._optional_int(
                                llm_model.extra.get("max_output_tokens", llm_model.max_output_tokens)
                            ),
                            "reasoning_enabled": self._optional_bool(
                                llm_model.extra.get(
                                    "reasoning_enabled",
                                    llm_provider_config.extra.get("reasoning_enabled"),
                                )
                            ),
                        },
                    },
                    meta={
                        "provider": llm_provider_config.provider_id,
                        "model": llm_model.model_id,
                        "capabilities": list(llm_model.capabilities or llm_provider_config.capabilities),
                        "content_type": "text/plain",
                        "protocol_version": self.PROTOCOL_VERSION,
                        "adapter_version": self.llm_provider.ADAPTER_VERSION,
                        "duration_ms": self._duration_ms(llm_started),
                        "request_id": llm_result.get("request_id"),
                        "usage": llm_result.get("raw_usage"),
                    },
                )
            )
        except Exception as error:
            stages.append(
                self._build_failure_stage(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    step="llm",
                    started_at=llm_started,
                    error=error,
                    payload={
                        "input": {
                            "messages": [],
                            "attachments": [],
                            "tools": [],
                        },
                        "output": {},
                        "refs": {},
                        "options": {},
                    },
                )
            )
            return self._build_pipeline_result(trace_id, resolved_session_id, stages)

        tts_started = perf_counter()
        try:
            tts_provider_config, tts_model = self.runtime_config.resolve_provider_and_model("tts")
            tts_provider = self.tts_provider_registry.resolve(tts_provider_config)
            output_path = Path("data") / "tts" / f"{trace_id}_tts.wav"
            tts_input_text = llm_result["reply_text"]
            tts_result = tts_provider.synthesize_to_file(
                TtsProviderRequest(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    text=tts_input_text,
                    provider_config=tts_provider_config,
                    model_config=tts_model,
                    output_path=output_path,
                )
            )
            stages.append(
                build_tts_stage_result(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    status="success",
                    provider_config=tts_provider_config,
                    model_config=tts_model,
                    text=llm_result["reply_text"],
                    result=tts_result,
                    duration_ms=self._duration_ms(tts_started),
                    adapter_version=tts_provider.ADAPTER_VERSION,
                )
            )
        except Exception as error:
            stages.append(
                self._build_failure_stage(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    step="tts",
                    started_at=tts_started,
                    error=error,
                    payload={
                        "input": {
                            "text": tts_input_text,
                        },
                        "output": {},
                        "refs": {},
                        "options": {},
                    },
                )
            )
            return self._build_pipeline_result(trace_id, resolved_session_id, stages)

        playback_started = perf_counter()
        try:
            playback_result = self.audio_player.play(tts_result.audio_ref["value"])
            stages.append(
                self._build_stage_result(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    step="playback",
                    status="success",
                    payload={
                        "input": {},
                        "output": playback_result,
                        "refs": {
                            "audio_ref": tts_result.audio_ref,
                        },
                        "options": {
                            "autoplay": True,
                            "volume": self.runtime_config.active_profile.desktop.volume,
                        },
                    },
                    meta={
                        "provider": "local_windows_playback",
                        "model": None,
                        "capabilities": ["audio_out"],
                        "content_type": "audio/wav",
                        "protocol_version": self.PROTOCOL_VERSION,
                        "adapter_version": "phase6.playback.windows.v1",
                        "duration_ms": self._duration_ms(playback_started),
                    },
                )
            )
        except Exception as error:
            stages.append(
                self._build_failure_stage(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    step="playback",
                    started_at=playback_started,
                    error=error,
                    payload={
                        "input": {},
                        "output": {},
                        "refs": {
                            "audio_ref": tts_result.audio_ref,
                        },
                        "options": {
                            "autoplay": True,
                            "volume": self.runtime_config.active_profile.desktop.volume,
                        },
                    },
                )
            )

        return self._build_pipeline_result(trace_id, resolved_session_id, stages)

    def _build_pipeline_result(self, trace_id: str, session_id: str, stages: list[dict[str, Any]]) -> dict[str, Any]:
        final_status = "success" if stages and stages[-1]["status"] == "success" else "failed"
        stt_text = None
        reply_text = None
        audio_ref = None
        playback_result = None
        failed_stage = None
        for stage in stages:
            if stage["step"] == "stt" and stage["status"] == "success":
                stt_text = stage["payload"]["output"]["text"]
            if stage["step"] == "llm" and stage["status"] == "success":
                reply_text = stage["payload"]["output"]["reply_text"]
            if stage["step"] == "tts" and stage["status"] == "success":
                audio_ref = stage["payload"]["output"]["audio_ref"]
            if stage["step"] == "playback" and stage["status"] == "success":
                playback_result = stage["payload"]["output"]
            if stage["status"] == "failed" and failed_stage is None:
                failed_stage = {
                    "step": stage["step"],
                    "error": stage["error"],
                    "meta": stage["meta"],
                }

        return {
            "trace_id": trace_id,
            "session_id": session_id,
            "status": final_status,
            "stages": stages,
            "final": {
                "stt_text": stt_text,
                "reply_text": reply_text,
                "audio_ref": audio_ref,
                "playback": playback_result,
                "failed_stage": failed_stage,
            },
        }

    def _build_stage_result(
        self,
        *,
        trace_id: str,
        session_id: str,
        step: str,
        status: str,
        payload: dict[str, Any],
        meta: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "trace_id": trace_id,
            "session_id": session_id,
            "step": step,
            "status": status,
            "timestamp": self._now_iso(),
            "payload": payload,
            "error": error,
            "meta": meta or {},
        }

    def _build_failure_stage(
        self,
        *,
        trace_id: str,
        session_id: str,
        step: str,
        started_at: float,
        error: Exception,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self._build_stage_result(
            trace_id=trace_id,
            session_id=session_id,
            step=step,
            status="failed",
            payload=payload,
            error=self._normalize_error(step=step, error=error),
            meta={
                "protocol_version": self.PROTOCOL_VERSION,
                "duration_ms": self._duration_ms(started_at),
            },
        )

    def _normalize_error(self, *, step: str, error: Exception) -> dict[str, Any]:
        if isinstance(error, ValueError):
            return {
                "code": f"{step.upper()}_VALIDATION_ERROR",
                "message": str(error),
                "type": "validation_error",
                "retryable": False,
                "details": {},
                "raw_ref": None,
            }

        if isinstance(error, FileNotFoundError):
            return {
                "code": f"{step.upper()}_FILE_ERROR",
                "message": str(error),
                "type": "file_error",
                "retryable": False,
                "details": {},
                "raw_ref": None,
            }

        if isinstance(error, requests.Timeout):
            return {
                "code": f"{step.upper()}_TIMEOUT",
                "message": str(error),
                "type": "provider_timeout",
                "retryable": True,
                "details": {},
                "raw_ref": None,
            }

        if isinstance(error, requests.HTTPError):
            status_code = error.response.status_code if error.response is not None else None
            return {
                "code": f"{step.upper()}_PROVIDER_ERROR",
                "message": str(error),
                "type": "provider_error",
                "retryable": False,
                "details": {
                    "status_code": status_code,
                },
                "raw_ref": None,
            }

        if isinstance(error, requests.RequestException):
            return {
                "code": f"{step.upper()}_NETWORK_ERROR",
                "message": str(error),
                "type": "network_error",
                "retryable": True,
                "details": {},
                "raw_ref": None,
            }

        provider_code = getattr(error, "code", None)
        error_type = getattr(error, "error_type", None)
        retryable = getattr(error, "retryable", None)
        details = getattr(error, "details", None)
        if provider_code and error_type is not None and retryable is not None:
            return {
                "code": provider_code,
                "message": str(error),
                "type": error_type,
                "retryable": bool(retryable),
                "details": details or {},
                "raw_ref": None,
            }

        return {
            "code": f"{step.upper()}_UNKNOWN_ERROR",
            "message": str(error),
            "type": "unknown_error",
            "retryable": False,
            "details": {},
            "raw_ref": None,
        }

    def _build_messages(self, *, user_text: str, system_prompt: str | None) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )
        messages.append(
            {
                "role": "user",
                "content": user_text,
            }
        )
        return messages

    def _resolve_audio_format(self, audio_path: Path, model_config: Any, provider_config: Any) -> str | None:
        inferred = audio_path.suffix.lstrip(".").lower()
        return self._first_value(
            inferred,
            model_config.extra.get("audio_format"),
            provider_config.extra.get("audio_format"),
        )

    def _guess_mime_type(self, audio_path: Path) -> str:
        mapping = {
            ".wav": "audio/wav",
            ".webm": "audio/webm",
            ".mp3": "audio/mpeg",
            ".ogg": "audio/ogg",
            ".opus": "audio/ogg",
            ".pcm": "audio/pcm",
        }
        return mapping.get(audio_path.suffix.lower(), "application/octet-stream")

    def _first_value(self, *candidates: Any) -> str | None:
        for candidate in candidates:
            if candidate is None:
                continue
            text = str(candidate).strip()
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
        if not text or text.startswith("("):
            return None
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
        return None

    def _duration_ms(self, started_at: float) -> int:
        return int((perf_counter() - started_at) * 1000)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    def _build_trace_id(self) -> str:
        return f"trace_{uuid.uuid4().hex[:12]}"

    def _build_session_id(self) -> str:
        return f"session_{uuid.uuid4().hex[:12]}"
