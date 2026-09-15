"""Voice Runtime 的稳定状态定义。"""

from enum import Enum


class VoiceRuntimeState(str, Enum):
    """一轮语音对话在本地运行时中的生命周期状态。"""

    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTING = "interrupting"
    ERROR = "error"
