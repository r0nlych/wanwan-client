"""
文本输入 -> 真实 LLM -> 真实 TTS -> 本地播放 的最小编排。
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
from src.wanwan_client.services.tts.providers import TtsProviderRegistry
from src.wanwan_client.services.tts.providers.base import TtsProviderRequest


class TextAudioPipeline:
    """
    最小真实可跑文本音频闭环。
    """

    PROTOCOL_VERSION = "v0.3"

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        llm_provider: OpenAICompatibleLlmProvider | None = None,
        tts_provider_registry: TtsProviderRegistry | None = None,
        audio_player: LocalAudioPlayer | None = None,
    ):
        self.runtime_config = runtime_config
        self.llm_provider = llm_provider or OpenAICompatibleLlmProvider()
        self.tts_provider_registry = tts_provider_registry or TtsProviderRegistry()
        self.audio_player = audio_player or LocalAudioPlayer()

    def run(self, user_text: str, session_id: str | None = None) -> dict[str, Any]:
        trace_id = self._build_trace_id()
        resolved_session_id = session_id or self._build_session_id()
        stages: list[dict[str, Any]] = []

        messages = [
            {
                "role": "user",
                "content": user_text,
            }
        ]

        llm_started = perf_counter()
        try:
            llm_provider, llm_model = self.runtime_config.resolve_provider_and_model("llm")
            llm_result = self.llm_provider.generate_reply(
                messages=messages,
                provider_config=llm_provider,
                model_config=llm_model,
            )
            llm_stage = self._build_stage_result(
                trace_id=trace_id,
                session_id=resolved_session_id,
                step="llm",
                status="success",
                payload={
                    "input": {
                        "messages": messages,
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
                        "finish_reason": llm_result["finish_reason"],
                    },
                    "refs": {},
                    "options": {
                        "temperature": llm_model.extra.get("temperature"),
                        "max_output_tokens": llm_model.max_output_tokens,
                        "reasoning_enabled": False,
                    },
                },
                meta={
                    "provider": llm_provider.provider_id,
                    "model": llm_model.model_id,
                    "capabilities": list(llm_model.capabilities),
                    "content_type": "text/plain",
                    "protocol_version": self.PROTOCOL_VERSION,
                    "adapter_version": self.llm_provider.ADAPTER_VERSION,
                    "duration_ms": self._duration_ms(llm_started),
                    "request_id": llm_result.get("request_id"),
                },
            )
            stages.append(llm_stage)
        except Exception as error:
            stages.append(
                self._build_failure_stage(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    step="llm",
                    started_at=llm_started,
                    error=error,
                )
            )
            return self._build_pipeline_result(trace_id, resolved_session_id, stages)

        tts_started = perf_counter()
        try:
            tts_provider_config, tts_model = self.runtime_config.resolve_provider_and_model("tts")
            tts_provider = self.tts_provider_registry.resolve(tts_provider_config)
            output_path = Path("data") / "tts" / f"{trace_id}_tts.wav"
            tts_result = tts_provider.synthesize_to_file(
                TtsProviderRequest(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    text=llm_result["reply_text"],
                    provider_config=tts_provider_config,
                    model_config=tts_model,
                    output_path=output_path,
                )
            )
            tts_stage = self._build_stage_result(
                trace_id=trace_id,
                session_id=resolved_session_id,
                step="tts",
                status="success",
                payload={
                    "input": {
                        "text": llm_result["reply_text"],
                    },
                    "output": {
                        "audio_ref": tts_result.audio_ref,
                    },
                    "refs": {},
                    "options": {
                        "voice": tts_result.voice,
                        "voice_type": tts_result.voice_type,
                        "speed": tts_model.extra.get("speed"),
                        "sample_rate": tts_model.extra.get("sample_rate"),
                    },
                },
                meta={
                    "provider": tts_provider_config.provider_id,
                    "model": tts_model.model_id,
                    "capabilities": list(tts_model.capabilities),
                    "content_type": tts_result.audio_ref["mime_type"],
                    "protocol_version": self.PROTOCOL_VERSION,
                    "adapter_version": tts_provider.ADAPTER_VERSION,
                    "duration_ms": self._duration_ms(tts_started),
                    "request_id": tts_result.request_id,
                    "byte_size": tts_result.byte_size,
                },
            )
            stages.append(tts_stage)
        except Exception as error:
            stages.append(
                self._build_failure_stage(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    step="tts",
                    started_at=tts_started,
                    error=error,
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
                )
            )

        return self._build_pipeline_result(trace_id, resolved_session_id, stages)

    def _build_pipeline_result(
        self,
        trace_id: str,
        session_id: str,
        stages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        final_status = "success"
        for s in stages:
            if s["status"] == "failed":
                final_status = "failed"
                break
        last_successful_reply = None
        last_audio_ref = None
        for stage in stages:
            if stage["step"] == "llm" and stage["status"] == "success":
                last_successful_reply = stage["payload"]["output"]["reply_text"]
            if stage["step"] == "tts" and stage["status"] == "success":
                last_audio_ref = stage["payload"]["output"]["audio_ref"]

        return {
            "trace_id": trace_id,
            "session_id": session_id,
            "status": final_status,
            "stages": stages,
            "final": {
                "reply_text": last_successful_reply,
                "audio_ref": last_audio_ref,
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
    ) -> dict[str, Any]:
        error_payload = self._normalize_error(step=step, error=error)
        return self._build_stage_result(
            trace_id=trace_id,
            session_id=session_id,
            step=step,
            status="failed",
            payload={
                "input": {},
                "output": {},
                "refs": {},
                "options": {},
            },
            error=error_payload,
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
            status_code = None
            if error.response is not None:
                status_code = error.response.status_code
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

        return {
            "code": f"{step.upper()}_UNKNOWN_ERROR",
            "message": str(error),
            "type": "unknown_error",
            "retryable": False,
            "details": {},
            "raw_ref": None,
        }

    def _duration_ms(self, started_at: float) -> int:
        return int((perf_counter() - started_at) * 1000)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    def _build_trace_id(self) -> str:
        return f"trace_{uuid.uuid4().hex[:12]}"

    def _build_session_id(self) -> str:
        return f"session_{uuid.uuid4().hex[:12]}"
