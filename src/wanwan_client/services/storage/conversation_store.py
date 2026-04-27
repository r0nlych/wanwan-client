"""
会话本地 JSONL 持久化存储。

每次语音链路运行结束后，将结果追加写入 data/conversations/{YYYY-MM-DD}.jsonl。
一行一条记录，拍平结构，成功和失败链路均保存。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONVERSATIONS_DIR = Path("data") / "conversations"


class ConversationStore:
    """将语音链路运行结果保存为 JSONL 文件。"""

    @staticmethod
    def save(result: dict[str, Any]) -> dict[str, Any]:
        try:
            CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)

            today = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
            file_path = CONVERSATIONS_DIR / f"{today}.jsonl"

            record = ConversationStore._build_record(result)

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            return {
                "saved": True,
                "path": str(file_path.as_posix()),
            }
        except Exception as e:
            return {
                "saved": False,
                "error": str(e),
            }

    @staticmethod
    def _build_record(result: dict[str, Any]) -> dict[str, Any]:
        final = result.get("final") or {}
        stages = result.get("stages") or []

        stt_text = final.get("stt_text")
        reply_text = final.get("reply_text")

        audio_ref = final.get("audio_ref")
        tts_audio_path = None
        if isinstance(audio_ref, dict):
            tts_audio_path = audio_ref.get("value")

        playback = final.get("playback")
        playback_played = None
        if isinstance(playback, dict):
            playback_played = playback.get("played")

        stages_summary = {}
        for known_step in ("stt", "llm", "tts", "playback"):
            status = "missing"
            for s in stages:
                if isinstance(s, dict) and s.get("step") == known_step:
                    status = s.get("status", "missing")
                    break
            stages_summary[known_step] = status

        failed_stage_raw = final.get("failed_stage")
        if isinstance(failed_stage_raw, dict) and failed_stage_raw.get("step"):
            err = failed_stage_raw.get("error") or {}
            failed_stage = {
                "step": failed_stage_raw["step"],
                "error_code": err.get("code", ""),
                "error_message": err.get("message", ""),
            }
            error_summary = {
                "step": failed_stage_raw["step"],
                "code": err.get("code", ""),
                "message": err.get("message", ""),
            }
        else:
            failed_stage = None
            error_summary = None

        timestamp = result.get("timestamp")
        if not timestamp:
            timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

        return {
            "trace_id": result.get("trace_id", ""),
            "session_id": result.get("session_id", ""),
            "timestamp": timestamp,
            "status": result.get("status", "unknown"),
            "stt_text": stt_text,
            "reply_text": reply_text,
            "tts_audio_path": tts_audio_path,
            "playback_played": playback_played,
            "stages_summary": stages_summary,
            "failed_stage": failed_stage,
            "error_summary": error_summary,
        }
