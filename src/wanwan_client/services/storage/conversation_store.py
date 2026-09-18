"""
会话本地 JSONL 持久化存储。

每次文本或语音链路运行结束后，将结果追加写入 data/conversations/{YYYY-MM-DD}.jsonl。
一行一条记录，拍平结构，成功和失败链路均保存。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONVERSATIONS_DIR = Path("data") / "conversations"


class ConversationStore:
    """将文本或语音链路运行结果保存为统一 JSONL 文件。"""

    DEFAULT_CONTEXT_TURNS = 6
    DEFAULT_CONTEXT_CHARACTERS = 12_000

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

        # 新版文本链路直接在 final 中提供 user_text；旧结果则从 LLM 输入或 STT 文本兼容推导。
        user_text = final.get("user_text")
        if not user_text:
            user_text = ConversationStore._find_user_text_from_stages(stages)
        if not user_text:
            user_text = stt_text

        input_type = "voice" if stt_text else ("text" if user_text else "unknown")

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
            "input_type": input_type,
            "user_text": user_text,
            "stt_text": stt_text,
            "reply_text": reply_text,
            "tts_audio_path": tts_audio_path,
            "playback_played": playback_played,
            "stages_summary": stages_summary,
            "failed_stage": failed_stage,
            "error_summary": error_summary,
        }

    @staticmethod
    def _find_user_text_from_stages(stages: list[Any]) -> str | None:
        """兼容旧结构：从 LLM 阶段的第一条 user 消息中提取输入文本。"""
        for stage in stages:
            if not isinstance(stage, dict) or stage.get("step") != "llm":
                continue
            payload = stage.get("payload") or {}
            stage_input = payload.get("input") or {}
            messages = stage_input.get("messages") or []
            for message in messages:
                if isinstance(message, dict) and message.get("role") == "user":
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content
        return None

    @staticmethod
    def load_session_messages(
        session_id: str,
        *,
        max_turns: int = DEFAULT_CONTEXT_TURNS,
        max_characters: int = DEFAULT_CONTEXT_CHARACTERS,
    ) -> list[dict[str, str]]:
        """读取同一会话最近的成功轮次，并转换成受限的 LLM messages。"""
        normalized_session_id = str(session_id).strip()
        if (
            not normalized_session_id
            or max_turns <= 0
            or max_characters <= 0
            or not CONVERSATIONS_DIR.exists()
        ):
            return []

        turns: list[tuple[str, str]] = []
        for file_path in sorted(CONVERSATIONS_DIR.glob("*.jsonl")):
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except OSError:
                # 单个文件不可读时跳过，不能让旧历史阻断当前聊天。
                continue

            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue

                if not isinstance(record, dict):
                    continue
                if record.get("session_id") != normalized_session_id:
                    continue
                if record.get("status") != "success":
                    continue

                user_text = record.get("user_text") or record.get("stt_text")
                reply_text = record.get("reply_text")
                if not isinstance(user_text, str) or not user_text.strip():
                    continue
                if not isinstance(reply_text, str) or not reply_text.strip():
                    continue
                turns.append((user_text.strip(), reply_text.strip()))

        # 从最近一轮向前选择完整轮次；达到字符上限就停止，不截断半轮对话。
        selected_reversed: list[tuple[str, str]] = []
        used_characters = 0
        for user_text, reply_text in reversed(turns[-max_turns:]):
            turn_characters = len(user_text) + len(reply_text)
            if used_characters + turn_characters > max_characters:
                break
            selected_reversed.append((user_text, reply_text))
            used_characters += turn_characters

        messages: list[dict[str, str]] = []
        for user_text, reply_text in reversed(selected_reversed):
            messages.append({"role": "user", "content": user_text})
            messages.append({"role": "assistant", "content": reply_text})
        return messages
