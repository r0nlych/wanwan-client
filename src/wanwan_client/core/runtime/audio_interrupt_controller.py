"""当前语音轮次的协作式取消与播放中断控制。"""

from __future__ import annotations

from threading import Event, Lock
from typing import Protocol


class StoppableAudioPlayer(Protocol):
    """Interrupt Controller 只依赖播放器的停止能力。"""

    def stop(self) -> dict[str, object]: ...


class CancellationToken:
    """在线程之间安全传递取消信号，不通过杀进程终止任务。"""

    def __init__(self) -> None:
        self._event = Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def wait(self, timeout: float | None = None) -> bool:
        """
        阻塞等待取消信号的最小公开接口。

        - timeout 为 None 时一直等待，直到收到取消信号；
        - timeout 为正数时最多等待指定秒数：
          等待期间被取消返回 True，超时仍未取消返回 False。
        不暴露底层 threading.Event，调用方只能读取取消状态。
        """
        return self._event.wait(timeout)


class AudioInterruptController:
    """统一取消剩余阶段，并立即要求本地播放器停止。"""

    def __init__(self, audio_player: StoppableAudioPlayer) -> None:
        self._audio_player = audio_player
        self._lock = Lock()
        self._current_token: CancellationToken | None = None

    def begin_turn(self) -> CancellationToken:
        """为新轮次创建独立 token，避免旧取消信号污染下一轮。"""
        token = CancellationToken()
        with self._lock:
            self._current_token = token
        return token

    def finish_turn(self, token: CancellationToken) -> None:
        """只清理当前 token，避免并发旧轮次误清理新轮次。"""
        with self._lock:
            if self._current_token is token:
                self._current_token = None

    def cancel_current_turn(self) -> bool:
        """发出协作式取消信号，并尝试停止当前本地播放。"""
        with self._lock:
            token = self._current_token
        if token is None:
            return False

        token.cancel()
        self._audio_player.stop()
        return True
