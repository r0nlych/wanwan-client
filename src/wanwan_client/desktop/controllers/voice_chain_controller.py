"""
桌面端内部语音链路调用入口。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.wanwan_client.core.app import RuntimeApp
from src.wanwan_client.core.pipeline import VoiceAudioPipeline
from src.wanwan_client.services.storage import ConversationStore


class VoiceChainController:
    """
    为未来桌宠 UI / 托盘按钮 / 快捷键 / 录音回调提供统一语音链路调用入口。
    """

    def __init__(self, runtime_app: RuntimeApp | None = None) -> None:
        self.runtime_app = runtime_app or RuntimeApp()

    def run(self, audio_path: str, session_id: str | None = None, skip_playback: bool = False) -> dict[str, Any]:
        normalized_audio_path = str(audio_path).strip()
        resolved_session_id = session_id or self._build_session_id()

        if not normalized_audio_path:
            result = self._build_validation_failure(
                session_id=resolved_session_id,
                error_code="VOICE_CHAIN_AUDIO_PATH_REQUIRED",
                error_message="audio_path is required",
                details={},
            )
        elif not Path(normalized_audio_path).exists():
            result = self._build_validation_failure(
                session_id=resolved_session_id,
                error_code="VOICE_CHAIN_AUDIO_PATH_NOT_FOUND",
                error_message=f"Audio path not found: {normalized_audio_path}",
                details={
                    "audio_path": normalized_audio_path,
                },
            )
        else:
            state = self.runtime_app.load_state()
            pipeline = VoiceAudioPipeline(runtime_config=state.runtime_config)
            result = pipeline.run(audio_path=normalized_audio_path, session_id=resolved_session_id, skip_playback=skip_playback)
            self._attach_controller_meta(result)
            self._attach_final_audio_path(result)

        save_meta = ConversationStore.save(result)
        result["conversation_save"] = save_meta
        return result

    def _build_validation_failure(
        self,
        *,
        session_id: str,
        error_code: str,
        error_message: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        trace_id = self._build_trace_id()
        return {
            "trace_id": trace_id,
            "session_id": session_id,
            "status": "failed",
            "stages": [
                {
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "step": "voice_chain",
                    "status": "failed",
                    "timestamp": self._now_iso(),
                    "payload": {
                        "input": {
                            "audio_path": details.get("audio_path", ""),
                        },
                        "output": {},
                        "refs": {},
                        "options": {},
                    },
                    "error": {
                        "code": error_code,
                        "message": error_message,
                        "type": "validation_error",
                        "retryable": False,
                        "details": details,
                        "raw_ref": None,
                    },
                    "meta": {
                        "caller": "desktop_controller",
                        "controller": "VoiceChainController",
                        "protocol_version": "v0.3",
                    },
                }
            ],
            "final": {
                "stt_text": None,
                "reply_text": None,
                "llm_reply_text": None,
                "audio_ref": None,
                "tts_audio_path": None,
                "playback": None,
                "failed_stage": {
                    "step": "voice_chain",
                    "error": {
                        "code": error_code,
                        "message": error_message,
                        "type": "validation_error",
                        "retryable": False,
                        "details": details,
                        "raw_ref": None,
                    },
                    "meta": {
                        "caller": "desktop_controller",
                        "controller": "VoiceChainController",
                        "protocol_version": "v0.3",
                    },
                },
            },
        }

    def _attach_controller_meta(self, result: dict[str, Any]) -> None:
        for stage in result.get("stages", []):
            if not isinstance(stage, dict):
                continue
            meta = stage.setdefault("meta", {})
            if isinstance(meta, dict):
                meta["caller"] = "desktop_controller"
                meta["controller"] = "VoiceChainController"

    def _attach_final_audio_path(self, result: dict[str, Any]) -> None:
        final = result.get("final")
        if not isinstance(final, dict):
            return
        final["llm_reply_text"] = final.get("reply_text")
        audio_ref = final.get("audio_ref")
        if isinstance(audio_ref, dict):
            final["tts_audio_path"] = audio_ref.get("value")
            return
        final["tts_audio_path"] = None

    def _build_trace_id(self) -> str:
        return f"trace_{uuid.uuid4().hex[:12]}"

    def _build_session_id(self) -> str:
        return f"session_{uuid.uuid4().hex[:12]}"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
