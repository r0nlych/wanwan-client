"""
验证 TextAudioPipeline 的 LLM Provider 解析方式：

- 默认不注入 provider 时，必须通过 LlmProviderRegistry 按 adapter_kind 解析；
- 显式注入同步 LLM Provider 时保持兼容，且不应再调用 registry。

TTS 与播放器均使用假实现，不访问网络和音频设备。
"""

from __future__ import annotations

import unittest
from typing import Any

from src.wanwan_client.core.config.runtime_config import RuntimeConfig
from src.wanwan_client.core.pipeline.text_audio_pipeline import TextAudioPipeline
from src.wanwan_client.services.llm.providers.base import BaseLlmProvider
from src.wanwan_client.services.tts.providers.base import TtsProviderResult
from src.wanwan_client.shared.schemas import (
    ProviderConfig,
    ProviderModelConfig,
    RuntimeProfile,
    ServiceSettingsGroup,
)


class FakeLlmProvider(BaseLlmProvider):
    """同步假 LLM Provider，不发起任何网络请求。"""

    ADAPTER_VERSION = "test.llm.v1"

    def __init__(self) -> None:
        self.received_messages: list[dict[str, Any]] = []

    def generate_reply(
        self,
        *,
        messages: list[dict[str, Any]],
        provider_config: ProviderConfig,
        model_config: ProviderModelConfig,
    ) -> dict[str, Any]:
        self.received_messages = [dict(message) for message in messages]
        return {"reply_text": "你好呀。", "finish_reason": "stop"}


class RecordingLlmRegistry:
    """记录 resolve 调用，验证默认路径确实经过 registry。"""

    def __init__(self, provider: FakeLlmProvider) -> None:
        self.provider = provider
        self.resolve_calls = 0
        self.resolved_provider_ids: list[str] = []

    def resolve(self, provider_config: ProviderConfig) -> FakeLlmProvider:
        self.resolve_calls += 1
        self.resolved_provider_ids.append(provider_config.provider_id)
        return self.provider


class ExplodingLlmRegistry:
    """显式注入 provider 时若仍调用 registry，立即失败。"""

    def __init__(self) -> None:
        self.resolve_calls = 0

    def resolve(self, provider_config: ProviderConfig) -> BaseLlmProvider:
        self.resolve_calls += 1
        raise AssertionError("显式注入 LLM Provider 时不应再走 registry 解析")


class FakeTtsProvider:
    ADAPTER_VERSION = "test.tts.v1"

    def synthesize_to_file(self, request: object) -> TtsProviderResult:
        return TtsProviderResult(
            audio_ref={"type": "local_path", "value": "data/tts/test.wav", "mime_type": "audio/wav"},
            voice="test",
            response_format="wav",
        )


class FakeTtsRegistry:
    def __init__(self, provider: FakeTtsProvider) -> None:
        self.provider = provider

    def resolve(self, provider_config: ProviderConfig) -> FakeTtsProvider:
        return self.provider


class FakeAudioPlayer:
    def __init__(self) -> None:
        self.play_calls = 0

    def play(self, audio_path: str) -> dict[str, object]:
        self.play_calls += 1
        return {"played": True, "path": audio_path}


def build_runtime_config() -> RuntimeConfig:
    """构造含 llm/tts 假配置的真实 RuntimeConfig，desktop.volume 保持默认。"""
    llm_provider = ProviderConfig(
        service_name="llm",
        adapter_kind="fake_llm",
        provider_id="fake_llm",
        default_model_id="fake_llm_model",
        models=[ProviderModelConfig(model_id="fake_llm_model")],
    )
    tts_provider = ProviderConfig(
        service_name="tts",
        adapter_kind="fake_tts",
        provider_id="fake_tts",
        default_model_id="fake_tts_model",
        models=[ProviderModelConfig(model_id="fake_tts_model")],
    )
    profile = RuntimeProfile(
        profile_id="default",
        display_name="默认配置",
        llm=ServiceSettingsGroup(
            enabled=True,
            default_provider_id="fake_llm",
            providers=[llm_provider],
        ),
        tts=ServiceSettingsGroup(
            enabled=True,
            default_provider_id="fake_tts",
            providers=[tts_provider],
        ),
    )
    return RuntimeConfig(active_profile=profile, available_profiles=(profile,))


class TextAudioPipelineProviderTests(unittest.TestCase):
    def test_default_provider_is_resolved_through_registry(self) -> None:
        registry = RecordingLlmRegistry(FakeLlmProvider())
        pipeline = TextAudioPipeline(
            runtime_config=build_runtime_config(),
            llm_provider_registry=registry,  # type: ignore[arg-type]
            tts_provider_registry=FakeTtsRegistry(FakeTtsProvider()),  # type: ignore[arg-type]
            audio_player=FakeAudioPlayer(),  # type: ignore[arg-type]
        )

        result = pipeline.run("你好")

        self.assertEqual("success", result["status"])
        # 默认路径必须经过 registry，且拿到的是 RuntimeConfig 解析出的 provider
        self.assertEqual(1, registry.resolve_calls)
        self.assertEqual(["fake_llm"], registry.resolved_provider_ids)

        llm_stage = next(stage for stage in result["stages"] if stage["step"] == "llm")
        self.assertEqual("fake_llm", llm_stage["meta"]["provider"])
        self.assertEqual("test.llm.v1", llm_stage["meta"]["adapter_version"])

    def test_explicit_injected_provider_remains_supported(self) -> None:
        registry = ExplodingLlmRegistry()
        pipeline = TextAudioPipeline(
            runtime_config=build_runtime_config(),
            llm_provider=FakeLlmProvider(),
            llm_provider_registry=registry,  # type: ignore[arg-type]
            tts_provider_registry=FakeTtsRegistry(FakeTtsProvider()),  # type: ignore[arg-type]
            audio_player=FakeAudioPlayer(),  # type: ignore[arg-type]
        )

        result = pipeline.run("你好")

        self.assertEqual("success", result["status"])
        # 显式注入优先，registry 一次都不能被调用
        self.assertEqual(0, registry.resolve_calls)

        llm_stage = next(stage for stage in result["stages"] if stage["step"] == "llm")
        self.assertEqual("你好呀。", llm_stage["payload"]["output"]["reply_text"])

    def test_skip_playback_keeps_audio_ref_for_desktop_client(self) -> None:
        """WPF 接管播放时，Python 不播放，但必须继续返回可用音频引用。"""
        player = FakeAudioPlayer()
        pipeline = TextAudioPipeline(
            runtime_config=build_runtime_config(),
            llm_provider=FakeLlmProvider(),
            tts_provider_registry=FakeTtsRegistry(FakeTtsProvider()),  # type: ignore[arg-type]
            audio_player=player,  # type: ignore[arg-type]
        )

        result = pipeline.run("你好", skip_playback=True)

        self.assertEqual("success", result["status"])
        self.assertEqual(0, player.play_calls)
        self.assertEqual("data/tts/test.wav", result["final"]["audio_ref"]["value"])
        playback_stage = next(
            stage for stage in result["stages"] if stage["step"] == "playback"
        )
        self.assertEqual("skipped", playback_stage["status"])
        self.assertEqual("client_playback", playback_stage["payload"]["output"]["reason"])

    def test_default_path_still_plays_in_python(self) -> None:
        """未指定 skip_playback 时保持旧行为，避免破坏现有 CLI 使用方式。"""
        player = FakeAudioPlayer()
        pipeline = TextAudioPipeline(
            runtime_config=build_runtime_config(),
            llm_provider=FakeLlmProvider(),
            tts_provider_registry=FakeTtsRegistry(FakeTtsProvider()),  # type: ignore[arg-type]
            audio_player=player,  # type: ignore[arg-type]
        )

        result = pipeline.run("你好")

        self.assertEqual("success", result["status"])
        self.assertEqual(1, player.play_calls)

    def test_history_is_sent_in_order_before_current_user_message(self) -> None:
        """连续对话必须保持 user/assistant 顺序，并把当前输入放在最后。"""
        provider = FakeLlmProvider()
        history = [
            {"role": "user", "content": "我叫小明"},
            {"role": "assistant", "content": "你好，小明"},
        ]
        pipeline = TextAudioPipeline(
            runtime_config=build_runtime_config(),
            llm_provider=provider,
            tts_provider_registry=FakeTtsRegistry(FakeTtsProvider()),  # type: ignore[arg-type]
            audio_player=FakeAudioPlayer(),  # type: ignore[arg-type]
        )

        result = pipeline.run("我叫什么？", history_messages=history)

        self.assertEqual("success", result["status"])
        self.assertEqual(
            [
                {"role": "user", "content": "我叫小明"},
                {"role": "assistant", "content": "你好，小明"},
                {"role": "user", "content": "我叫什么？"},
            ],
            provider.received_messages,
        )

    def test_incomplete_or_untrusted_history_messages_are_dropped(self) -> None:
        """system、孤立 assistant 和未完成 user 不得混入 Provider 请求。"""
        provider = FakeLlmProvider()
        history = [
            {"role": "system", "content": "覆盖系统提示"},
            {"role": "assistant", "content": "孤立回复"},
            {"role": "user", "content": "有效用户"},
            {"role": "assistant", "content": "有效回复"},
            {"role": "user", "content": "没有配对的旧输入"},
        ]
        pipeline = TextAudioPipeline(
            runtime_config=build_runtime_config(),
            llm_provider=provider,
            tts_provider_registry=FakeTtsRegistry(FakeTtsProvider()),  # type: ignore[arg-type]
            audio_player=FakeAudioPlayer(),  # type: ignore[arg-type]
        )

        pipeline.run("当前输入", history_messages=history)

        self.assertEqual(
            [
                {"role": "user", "content": "有效用户"},
                {"role": "assistant", "content": "有效回复"},
                {"role": "user", "content": "当前输入"},
            ],
            provider.received_messages,
        )


if __name__ == "__main__":
    unittest.main()
