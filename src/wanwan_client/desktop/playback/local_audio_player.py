"""
Windows 本地音频播放。
"""

from __future__ import annotations

import os
import winsound
from pathlib import Path


SND_SYNC = winsound.SND_FILENAME | winsound.SND_NODEFAULT
SND_ASYNC_FLAG = winsound.SND_FILENAME | winsound.SND_NODEFAULT | winsound.SND_ASYNC


def _describe_flags(flags: int) -> str:
    parts = []
    if flags & winsound.SND_FILENAME:
        parts.append("SND_FILENAME")
    if flags & winsound.SND_NODEFAULT:
        parts.append("SND_NODEFAULT")
    if flags & winsound.SND_ASYNC:
        parts.append("SND_ASYNC")
    return " | ".join(parts)


class LocalAudioPlayer:
    """
    Windows first 的最小本地播放实现。
    当前阶段只支持 wav 文件同步/异步播放。
    始终使用 SND_NODEFAULT，避免文件无法播放时触发系统默认提示音。
    """

    def play(self, audio_path: str, async_mode: bool = False) -> dict[str, object]:
        original_path = audio_path
        resolved_path = str(Path(audio_path).resolve())
        flags = SND_ASYNC_FLAG if async_mode else SND_SYNC

        path = Path(resolved_path)
        exists = path.exists()
        suffix = path.suffix.lower()
        file_size = path.stat().st_size if exists else 0

        error_code = None
        error_message = None
        played = False

        if not exists:
            error_code = "PET_PLAYBACK_AUDIO_FILE_NOT_FOUND"
            error_message = f"Audio file not found: {resolved_path}"
        elif suffix != ".wav":
            error_code = "PET_PLAYBACK_INVALID_FORMAT"
            error_message = f"LocalAudioPlayer currently supports only .wav playback, got: {suffix}"
        elif file_size == 0:
            error_code = "PET_PLAYBACK_EMPTY_FILE"
            error_message = f"Audio file is empty (0 bytes): {resolved_path}"

        if error_code:
            return {
                "played": False,
                "original_audio_path": original_path,
                "resolved_audio_path": resolved_path,
                "exists": exists,
                "file_size": file_size,
                "flags": _describe_flags(flags),
                "error_code": error_code,
                "error_message": error_message,
            }

        try:
            winsound.PlaySound(os.fspath(path), flags)
            played = True
        except RuntimeError as e:
            error_code = "PET_PLAYBACK_FAILED"
            error_message = f"winsound.PlaySound failed: {e}"

        return {
            "played": played,
            "playable_ref": {
                "type": "local_path",
                "value": resolved_path.replace("\\", "/"),
                "mime_type": "audio/wav",
            },
            "original_audio_path": original_path,
            "resolved_audio_path": resolved_path,
            "exists": exists,
            "file_size": file_size,
            "flags": _describe_flags(flags),
            "error_code": error_code,
            "error_message": error_message,
        }
