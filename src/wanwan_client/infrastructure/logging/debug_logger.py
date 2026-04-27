"""
结构化调试日志模块。

以 JSON Lines 格式写入 logs/wanwan_debug.log。
线程安全，自动创建目录，UTF-8 编码，追加写入。
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "wanwan_debug.log"

# 调试日志事件常量
EVENT_RECORD_START_CLICKED = "pet.record.start_clicked"
EVENT_RECORD_STARTED = "pet.record.started"
EVENT_RECORD_STOP_CLICKED = "pet.record.stop_clicked"
EVENT_RECORD_SAVED = "pet.record.saved"
EVENT_RECORD_CANCEL_CLICKED = "pet.record.cancel_clicked"
EVENT_VOICE_CHAIN_START = "pet.voice_chain.start"
EVENT_VOICE_CHAIN_RESULT = "pet.voice_chain.result"
EVENT_VOICE_CHAIN_FAILED = "pet.voice_chain.failed"
EVENT_VOICE_CHAIN_EXCEPTION = "pet.voice_chain.exception"
EVENT_PLAYBACK_RESULT = "pet.playback.result"
EVENT_CONVERSATION_SAVE_RESULT = "pet.conversation_save.result"
EVENT_VOICE_CHAIN_RESULT_DETAIL = "pet.voice_chain.result_detail"
EVENT_PLAYBACK_EXPLICIT_START = "pet.playback.explicit_start"
EVENT_PLAYBACK_EXPLICIT_RESULT = "pet.playback.explicit_result"

EVENT_VOICE_CHAIN_CLI_START = "voice_chain.cli.start"
EVENT_VOICE_CHAIN_CTRL_START = "voice_chain.controller.start"
EVENT_VOICE_CHAIN_CTRL_RESULT = "voice_chain.controller.result"
EVENT_VOICE_CHAIN_CTRL_FAILED = "voice_chain.controller.failed"
EVENT_CONVERSATION_SAVE_RESULT_V2 = "conversation_save.result"


class DebugLogger:
    """线程安全的 JSON Lines 调试日志写入器。"""

    def __init__(self, log_path: str | Path = LOG_FILE) -> None:
        self._log_path = Path(log_path)
        self._lock = threading.Lock()

    def _ensure_dir(self) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, level: str, event: str, message: str, **kwargs: Any) -> None:
        """写入一条结构化日志。"""
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event,
            "message": message,
        }
        extra_keys = [
            "trace_id", "session_id", "audio_path", "file_size",
            "status", "step", "error_code", "error_message",
            "json_only", "no_play",
            "stt_text_non_empty", "reply_text_non_empty",
            "tts_audio_path", "saved", "path",
        ]
        for key in extra_keys:
            if key in kwargs and kwargs[key] is not None:
                entry[key] = kwargs[key]
        with self._lock:
            self._ensure_dir()
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def info(self, event: str, message: str, **kwargs: Any) -> None:
        self.log("INFO", event, message, **kwargs)

    def warning(self, event: str, message: str, **kwargs: Any) -> None:
        self.log("WARNING", event, message, **kwargs)

    def error(self, event: str, message: str, **kwargs: Any) -> None:
        self.log("ERROR", event, message, **kwargs)

    def clear(self) -> None:
        """清空所有日志。"""
        with self._lock:
            self._ensure_dir()
            with open(self._log_path, "w", encoding="utf-8") as f:
                f.write("")

    def read_all(self) -> str:
        """读取日志文件全部内容。"""
        with self._lock:
            if not self._log_path.exists():
                return ""
            return self._log_path.read_text(encoding="utf-8")

    def read_tail(self, n: int = 300) -> str:
        """读取日志文件最后 n 行，避免大文件卡 UI。"""
        with self._lock:
            if not self._log_path.exists():
                return ""
            all_lines = self._log_path.read_text(encoding="utf-8").splitlines()
            tail = all_lines[-n:] if len(all_lines) > n else all_lines
            return "\n".join(tail)


_default_logger: DebugLogger | None = None


def get_debug_logger() -> DebugLogger:
    """获取模块级单例 DebugLogger。"""
    global _default_logger
    if _default_logger is None:
        _default_logger = DebugLogger()
    return _default_logger
