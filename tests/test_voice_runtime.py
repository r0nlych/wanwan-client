"""Voice Runtime 第一阶段控制骨架的验收测试。"""

from __future__ import annotations

import threading
import unittest
from typing import Any

from src.wanwan_client.core.pipeline.voice_audio_pipeline import VoiceAudioPipeline
from src.wanwan_client.core.runtime import (
    CancellationToken,
    TextSegmenter,
    VoiceRuntime,
    VoiceRuntimeState,
)
from src.wanwan_client.services.llm.providers.base import BaseLlmProvider
from src.wanwan_client.services.stt.providers.base import SttProviderResult
from src.wanwan_client.services.tts.providers.base import TtsProviderResult
from src.wanwan_client.shared.schemas import ProviderConfig, ProviderModelConfig


class FakeRuntimeConfig:
    """只提供 Pipeline 真实消费的 provider/model 解析入口。"""

    def __init__(self) -> None:
        self._configs = {
            service: (
                ProviderConfig(
                    service_name=service,
                    adapter_kind=f"fake_{service}",
                    provider_id=f"fake_{service}",
                    default_model_id=f"fake_{service}_model",
                    models=[ProviderModelConfig(model_id=f"fake_{service}_model")],
                ),
                ProviderModelConfig(model_id=f"fake_{service}_model"),
            )
            for service in ("stt", "llm", "tts")
        }

    def resolve_provider_and_model(self, service_name: str) -> tuple[ProviderConfig, ProviderModelConfig]:
        return self._configs[service_name]


class FakeRegistry:
    def __init__(self, provider: object) -> None:
        self.provider = provider

    def resolve(self, provider_config: ProviderConfig) -> object:
        return self.provider


class FakeSttProvider:
    ADAPTER_VERSION = "test.stt.v1"

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def transcribe(self, request: object) -> SttProviderResult:
        if self.should_fail:
            raise RuntimeError("stt failed")
        return SttProviderResult(text="你好")


class FakeLlmProvider(BaseLlmProvider):
    ADAPTER_VERSION = "test.llm.v1"

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.sync_calls = 0

    def generate_reply(
        self,
        *,
        messages: list[dict[str, Any]],
        provider_config: ProviderConfig,
        model_config: ProviderModelConfig,
    ) -> dict[str, Any]:
        self.sync_calls += 1
        if self.should_fail:
            raise RuntimeError("llm failed")
        return {"reply_text": "你好呀。", "finish_reason": "stop"}


class FakeTtsProvider:
    ADAPTER_VERSION = "test.tts.v1"

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def synthesize_to_file(self, request: object) -> TtsProviderResult:
        if self.should_fail:
            raise RuntimeError("tts failed")
        return TtsProviderResult(
            audio_ref={"type": "local_path", "value": "data/tts/test.wav", "mime_type": "audio/wav"},
            voice="test",
            response_format="wav",
        )


class FakeAudioPlayer:
    def __init__(self) -> None:
        self.stop_calls = 0

    def play(self, audio_path: str, async_mode: bool = False) -> dict[str, object]:
        return {"played": True}

    def stop(self) -> dict[str, object]:
        self.stop_calls += 1
        return {"stopped": True}


def build_runtime(*, failed_stage: str | None = None) -> VoiceRuntime:
    """装配真实 Pipeline 与假的外部边界，避免测试访问网络和音频设备。"""
    pipeline = VoiceAudioPipeline(
        runtime_config=FakeRuntimeConfig(),  # type: ignore[arg-type]
        stt_provider_registry=FakeRegistry(FakeSttProvider(failed_stage == "stt")),  # type: ignore[arg-type]
        llm_provider=FakeLlmProvider(failed_stage == "llm"),
        tts_provider_registry=FakeRegistry(FakeTtsProvider(failed_stage == "tts")),  # type: ignore[arg-type]
        audio_player=FakeAudioPlayer(),  # type: ignore[arg-type]
    )
    return VoiceRuntime(pipeline)


class VoiceRuntimeTests(unittest.TestCase):
    def test_successful_turn_transitions_through_runtime_states(self) -> None:
        transitions: list[VoiceRuntimeState] = []
        runtime = build_runtime()
        runtime.set_state_changed_callback(lambda _old, new: transitions.append(new))

        result = runtime.run_turn("input.wav", skip_playback=True)

        self.assertEqual("success", result["status"])
        self.assertEqual(
            [
                VoiceRuntimeState.LISTENING,
                VoiceRuntimeState.TRANSCRIBING,
                VoiceRuntimeState.THINKING,
                VoiceRuntimeState.SPEAKING,
                VoiceRuntimeState.IDLE,
            ],
            transitions,
        )

    def test_successful_pipeline_returns_runtime_to_idle(self) -> None:
        runtime = build_runtime()

        runtime.run_turn("input.wav", skip_playback=True)

        self.assertEqual(VoiceRuntimeState.IDLE, runtime.state)

    def test_stt_failure_enters_error(self) -> None:
        self._assert_stage_failure("stt")

    def test_llm_failure_enters_error(self) -> None:
        self._assert_stage_failure("llm")

    def test_tts_failure_enters_error(self) -> None:
        self._assert_stage_failure("tts")

    def test_cancel_current_turn_stops_playback_and_cancels_task(self) -> None:
        player = FakeAudioPlayer()
        started = threading.Event()
        result_holder: list[dict[str, Any]] = []

        class BlockingPipeline:
            audio_player = player

            def run(self, **kwargs: Any) -> dict[str, Any]:
                kwargs["on_stage_started"]("llm")
                started.set()
                token = kwargs["cancellation_token"]
                # 只使用公开等待接口：阻塞到外部取消后再结束本轮
                token.wait()
                return {"status": "cancelled", "stages": [], "final": {}}

        runtime = VoiceRuntime(BlockingPipeline())  # type: ignore[arg-type]
        worker = threading.Thread(
            target=lambda: result_holder.append(runtime.run_turn("input.wav")),
            daemon=True,
        )
        worker.start()
        self.assertTrue(started.wait(1.0))

        self.assertTrue(runtime.cancel_current_turn())
        worker.join(1.0)

        self.assertFalse(worker.is_alive())
        self.assertEqual(1, player.stop_calls)
        self.assertEqual("cancelled", result_holder[0]["status"])
        self.assertEqual(VoiceRuntimeState.LISTENING, runtime.state)

    def _assert_stage_failure(self, failed_stage: str) -> None:
        runtime = build_runtime(failed_stage=failed_stage)

        result = runtime.run_turn("input.wav", skip_playback=True)

        self.assertEqual("failed", result["status"])
        self.assertEqual(failed_stage, result["final"]["failed_stage"]["step"])
        self.assertEqual(VoiceRuntimeState.ERROR, runtime.state)


class StreamingAndSegmentationTests(unittest.TestCase):
    def test_sync_llm_provider_remains_available(self) -> None:
        provider = FakeLlmProvider()
        provider_config = ProviderConfig(provider_id="fake", adapter_kind="fake")
        model_config = ProviderModelConfig(model_id="fake-model")
        messages = [{"role": "user", "content": "你好"}]

        sync_result = provider.generate_reply(
            messages=messages,
            provider_config=provider_config,
            model_config=model_config,
        )
        self.assertEqual("你好呀。", sync_result["reply_text"])
        self.assertEqual(1, provider.sync_calls)

    def test_streaming_uses_sync_fallback_when_provider_does_not_support_it(self) -> None:
        provider = FakeLlmProvider()
        provider_config = ProviderConfig(provider_id="fake", adapter_kind="fake")
        model_config = ProviderModelConfig(model_id="fake-model")

        stream_chunks = list(
            provider.stream_reply(
                messages=[{"role": "user", "content": "你好"}],
                provider_config=provider_config,
                model_config=model_config,
            )
        )

        self.assertEqual(["你好呀。"], stream_chunks)
        self.assertEqual(1, provider.sync_calls)
        self.assertFalse(provider.SUPPORTS_STREAMING)

    def test_text_segmenter_joins_chunks_and_splits_on_chinese_punctuation(self) -> None:
        segmenter = TextSegmenter(max_length=20)

        segments: list[str] = []
        for chunk in ("今天", "天气", "不错，", "我们可以", "出去走走。", "好呀！"):
            segments.extend(segmenter.feed(chunk))
        segments.extend(segmenter.flush())

        self.assertEqual(["今天天气不错，我们可以出去走走。", "好呀！"], segments)

    def test_text_segmenter_uses_length_threshold_without_punctuation(self) -> None:
        segmenter = TextSegmenter(max_length=4)

        self.assertEqual(["一二三四"], segmenter.feed("一二三四五"))
        self.assertEqual(["五"], segmenter.flush())

    def test_text_segmenter_enforces_max_length_when_boundary_beyond_threshold(self) -> None:
        # 第一个结束标点"。"出现在 max_length 之外（第 6 个字符）：
        # 旧实现会一直等到标点，产出 6 字符的超长段；
        # 新实现必须先严格按 max_length=4 切，保证上限有效。
        segmenter = TextSegmenter(max_length=4)

        segments = segmenter.feed("一二三四五。")
        segments.extend(segmenter.flush())

        self.assertEqual(["一二三四", "五。"], segments)
        self.assertTrue(all(len(segment) <= 4 for segment in segments))

    def test_text_segmenter_prefers_boundary_within_threshold(self) -> None:
        # 标点位于阈值以内且缓冲已达上限时，仍优先按标点成段
        segmenter = TextSegmenter(max_length=6)

        segments = segmenter.feed("一二。三四五六")

        self.assertEqual(["一二。"], segments)
        self.assertEqual(["三四五六"], segmenter.flush())


class CancellationTokenTests(unittest.TestCase):
    def test_wait_times_out_before_cancel(self) -> None:
        token = CancellationToken()

        self.assertFalse(token.wait(0.01))
        self.assertFalse(token.is_cancelled)

    def test_wait_returns_after_cancel(self) -> None:
        token = CancellationToken()
        token.cancel()

        self.assertTrue(token.wait(0.01))
        self.assertTrue(token.is_cancelled)

    def test_blocking_wait_is_released_by_cancel_from_another_thread(self) -> None:
        # 无超时 wait() 必须能被另一线程的 cancel() 唤醒，验证线程安全语义
        token = CancellationToken()

        worker = threading.Thread(target=lambda: token.wait(), daemon=True)
        worker.start()
        worker.join(0.05)
        self.assertTrue(worker.is_alive())  # 未取消时一直阻塞

        token.cancel()
        worker.join(1.0)

        self.assertFalse(worker.is_alive())
        self.assertTrue(token.is_cancelled)


if __name__ == "__main__":
    unittest.main()
