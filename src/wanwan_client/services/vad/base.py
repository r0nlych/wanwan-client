"""VAD Provider 抽象；本阶段不绑定具体算法或厂商。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class VadEventType(str, Enum):
    """Runtime 当前需要识别的最小语音活动事件。"""

    SPEECH_STARTED = "speech_started"
    SPEECH_ENDED = "speech_ended"


@dataclass(frozen=True, slots=True)
class VadEvent:
    """一次 VAD 状态变化；时间信息留给具体实现提供。"""

    event_type: VadEventType
    timestamp_ms: int | None = None


class VadProvider(ABC):
    """接收音频块并返回零个或多个语音活动事件。"""

    @abstractmethod
    def process(self, audio_chunk: bytes) -> tuple[VadEvent, ...]:
        raise NotImplementedError

    def reset(self) -> None:
        """新一轮监听前重置 Provider 内部状态。"""
