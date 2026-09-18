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
from src.wanwan_client.services.llm.providers import BaseLlmProvider, LlmProviderRegistry
from src.wanwan_client.services.tts.providers import TtsProviderRegistry
from src.wanwan_client.services.tts.providers.base import TtsProviderRequest


class TextAudioPipeline:
    """
    最小真实可跑文本音频闭环。
    """

    PROTOCOL_VERSION = "v0.3"
    MAX_CONTEXT_TURNS = 6
    MAX_CONTEXT_CHARACTERS = 12_000

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        llm_provider: BaseLlmProvider | None = None,
        tts_provider_registry: TtsProviderRegistry | None = None,
        audio_player: LocalAudioPlayer | None = None,
        llm_provider_registry: LlmProviderRegistry | None = None,
    ):
        self.runtime_config = runtime_config
        # 显式注入优先；未注入时不在构造期绑定具体厂商，
        # 而是在 run() 中按当前配置的 adapter_kind 经 registry 解析
        self.llm_provider = llm_provider
        self.llm_provider_registry = llm_provider_registry or LlmProviderRegistry()
        self.tts_provider_registry = tts_provider_registry or TtsProviderRegistry()
        self.audio_player = audio_player or LocalAudioPlayer()

    def run(
        self,
        user_text: str,
        session_id: str | None = None,
        skip_playback: bool = False,
        history_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        trace_id = self._build_trace_id()
        resolved_session_id = session_id or self._build_session_id()
        stages: list[dict[str, Any]] = []

        # 历史由调用方在获得明确授权后提供；Pipeline 再做角色和大小防御。
        # 当前用户消息始终最后追加，避免历史数据覆盖本轮输入。
        messages = self._build_messages(
            user_text=user_text,
            history_messages=history_messages,
        )

        llm_started = perf_counter()
        try:
            llm_provider_config, llm_model = self.runtime_config.resolve_provider_and_model("llm")
            # 与 VoiceAudioPipeline 一致：显式注入优先，否则按 adapter_kind 解析
            resolved_llm_provider = (
                self.llm_provider
                or self.llm_provider_registry.resolve(llm_provider_config)
            )
            llm_result = resolved_llm_provider.generate_reply(
                messages=messages,
                provider_config=llm_provider_config,
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
                    "provider": llm_provider_config.provider_id,
                    "model": llm_model.model_id,
                    "capabilities": list(llm_model.capabilities),
                    "content_type": "text/plain",
                    "protocol_version": self.PROTOCOL_VERSION,
                    "adapter_version": resolved_llm_provider.ADAPTER_VERSION,
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
            return self._build_pipeline_result(trace_id, resolved_session_id, stages, user_text)

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
            return self._build_pipeline_result(trace_id, resolved_session_id, stages, user_text)

        # WPF 主界面需要自己控制播放、停止按钮和音量，因此允许 Python 只生成音频。
        # 默认仍由 Python 播放，保证现有 CLI 调用和测试保持兼容。
        if skip_playback:
            stages.append(
                self._build_stage_result(
                    trace_id=trace_id,
                    session_id=resolved_session_id,
                    step="playback",
                    status="skipped",
                    payload={
                        "input": {},
                        "output": {
                            "skipped": True,
                            "reason": "client_playback",
                        },
                        "refs": {
                            "audio_ref": tts_result.audio_ref,
                        },
                        "options": {
                            "autoplay": False,
                            "volume": self.runtime_config.active_profile.desktop.volume,
                        },
                    },
                    meta={
                        "provider": "client_playback",
                        "model": None,
                        "capabilities": ["audio_out"],
                        "content_type": tts_result.audio_ref["mime_type"],
                        "protocol_version": self.PROTOCOL_VERSION,
                        "adapter_version": "phase6.playback.skipped.v1",
                        "duration_ms": 0,
                    },
                )
            )
            return self._build_pipeline_result(trace_id, resolved_session_id, stages, user_text)

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

        return self._build_pipeline_result(trace_id, resolved_session_id, stages, user_text)

    def _build_pipeline_result(
        self,
        trace_id: str,
        session_id: str,
        stages: list[dict[str, Any]],
        user_text: str,
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
                # 历史记录需要保留用户原文；这也让失败链路不依赖阶段 payload 才能还原输入。
                "user_text": user_text,
                "reply_text": last_successful_reply,
                "audio_ref": last_audio_ref,
            },
        }

    def _build_messages(
        self,
        *,
        user_text: str,
        history_messages: list[dict[str, Any]] | None,
    ) -> list[dict[str, str]]:
        """清洗历史消息、限制大小，并最终追加本轮用户输入。"""
        sanitized_turns: list[tuple[str, str]] = []
        pending_user: str | None = None
        for message in history_messages or []:
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            content = message.get("content")
            if role not in {"user", "assistant"}:
                continue
            if not isinstance(content, str) or not content.strip():
                continue
            normalized_content = content.strip()
            if role == "user":
                pending_user = normalized_content
                continue
            if role == "assistant" and pending_user is not None:
                sanitized_turns.append((pending_user, normalized_content))
                pending_user = None

        # 只接受完整的 user/assistant 轮次；即使调用方传入异常列表也限制为6轮和12000字符。
        selected_reversed: list[tuple[str, str]] = []
        used_characters = 0
        for history_user, history_assistant in reversed(
            sanitized_turns[-self.MAX_CONTEXT_TURNS :]
        ):
            turn_characters = len(history_user) + len(history_assistant)
            if used_characters + turn_characters > self.MAX_CONTEXT_CHARACTERS:
                break
            selected_reversed.append((history_user, history_assistant))
            used_characters += turn_characters

        messages: list[dict[str, str]] = []
        for history_user, history_assistant in reversed(selected_reversed):
            messages.append({"role": "user", "content": history_user})
            messages.append({"role": "assistant", "content": history_assistant})
        messages.append({"role": "user", "content": user_text})
        return messages

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
