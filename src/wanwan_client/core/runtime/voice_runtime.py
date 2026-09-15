"""VoiceAudioPipeline 上方的语音生命周期控制层。"""

from __future__ import annotations

from threading import RLock
from typing import Any, Callable

from src.wanwan_client.core.pipeline.voice_audio_pipeline import VoiceAudioPipeline
from src.wanwan_client.core.runtime.audio_interrupt_controller import AudioInterruptController
from src.wanwan_client.core.runtime.voice_state import VoiceRuntimeState

StateChangedCallback = Callable[[VoiceRuntimeState, VoiceRuntimeState], None]


class VoiceRuntime:
    """集中管理状态、当前轮次与取消，不接触具体厂商 Provider。"""

    _STAGE_STATES = {
        "stt": VoiceRuntimeState.TRANSCRIBING,
        "llm": VoiceRuntimeState.THINKING,
        "tts": VoiceRuntimeState.SPEAKING,
        "playback": VoiceRuntimeState.SPEAKING,
    }

    def __init__(
        self,
        pipeline: VoiceAudioPipeline,
        *,
        interrupt_controller: AudioInterruptController | None = None,
        on_state_changed: StateChangedCallback | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.interrupt_controller = interrupt_controller or AudioInterruptController(pipeline.audio_player)
        self._on_state_changed = on_state_changed
        self._state = VoiceRuntimeState.IDLE
        self._lock = RLock()
        self._turn_active = False

    @property
    def state(self) -> VoiceRuntimeState:
        with self._lock:
            return self._state

    def set_state_changed_callback(self, callback: StateChangedCallback | None) -> None:
        """更新 UI 可订阅的状态回调，不把动画逻辑写进 Runtime。"""
        with self._lock:
            self._on_state_changed = callback

    def start_listening(self) -> None:
        """声明本地录音/监听已经开始。"""
        self._transition_to(VoiceRuntimeState.LISTENING)

    def run_turn(
        self,
        audio_path: str,
        session_id: str | None = None,
        skip_playback: bool = False,
    ) -> dict[str, Any]:
        """运行一次稳定 Pipeline，并将阶段映射为 Voice Runtime 状态。"""
        with self._lock:
            if self._turn_active:
                raise RuntimeError("A voice turn is already running")
            self._turn_active = True

        token = self.interrupt_controller.begin_turn()
        if self.state is VoiceRuntimeState.IDLE:
            self._transition_to(VoiceRuntimeState.LISTENING)

        try:
            result = self.pipeline.run(
                audio_path=audio_path,
                session_id=session_id,
                skip_playback=skip_playback,
                cancellation_token=token,
                on_stage_started=self._handle_stage_started,
            )
            if token.is_cancelled or result.get("status") == "cancelled":
                self._transition_to(VoiceRuntimeState.LISTENING)
            elif result.get("status") == "success":
                self._transition_to(VoiceRuntimeState.IDLE)
            else:
                self._transition_to(VoiceRuntimeState.ERROR)
            return result
        except Exception:
            self._transition_to(VoiceRuntimeState.ERROR)
            raise
        finally:
            self.interrupt_controller.finish_turn(token)
            with self._lock:
                self._turn_active = False

    def cancel_current_turn(self) -> bool:
        """中断当前轮次；已取消后回到监听态，等待下一段用户语音。"""
        if not self.interrupt_controller.cancel_current_turn():
            return False
        self._transition_to(VoiceRuntimeState.INTERRUPTING)
        self._transition_to(VoiceRuntimeState.LISTENING)
        return True

    def reset_error(self) -> None:
        """显式清除错误态，避免错误被静默覆盖。"""
        if self.state is VoiceRuntimeState.ERROR:
            self._transition_to(VoiceRuntimeState.IDLE)

    def _handle_stage_started(self, step: str) -> None:
        state = self._STAGE_STATES.get(step)
        if state is not None:
            self._transition_to(state)

    def _transition_to(self, new_state: VoiceRuntimeState) -> None:
        with self._lock:
            old_state = self._state
            if old_state is new_state:
                return
            self._state = new_state
            callback = self._on_state_changed
        if callback is not None:
            callback(old_state, new_state)
