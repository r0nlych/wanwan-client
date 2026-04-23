"""
Windows 本地音频播放。
"""

from __future__ import annotations

import os
import winsound
from pathlib import Path


class LocalAudioPlayer:
    """
    Windows first 的最小本地播放实现。
    当前阶段只支持 wav 文件同步播放。
    """

    def play(self, audio_path: str) -> dict[str, object]:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if path.suffix.lower() != ".wav":
            raise ValueError("LocalAudioPlayer currently supports only .wav playback")

        winsound.PlaySound(os.fspath(path), winsound.SND_FILENAME)
        return {
            "played": True,
            "playable_ref": {
                "type": "local_path",
                "value": str(path).replace("\\", "/"),
                "mime_type": "audio/wav",
            },
        }
