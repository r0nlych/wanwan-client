"""
验证 run-stt-audio 的 Provider 选择逻辑：

- CLI 未传 --provider-id/--model-id 时，参数为 None，
  由 RuntimeConfig 按 default_provider_id / default_model_id 解析；
- 显式传参时，SttService 必须解析到指定的 provider / model。

全程使用假 Provider，不访问真实 STT API。
"""

from __future__ import annotations

import unittest

from src.wanwan_client.core.config.runtime_config import RuntimeConfig
from src.wanwan_client.main import build_parser
from src.wanwan_client.services.stt.providers.base import SttProviderResult
from src.wanwan_client.services.stt.service import SttService
from src.wanwan_client.shared.schemas import (
    ProviderConfig,
    ProviderModelConfig,
    RuntimeProfile,
    ServiceSettingsGroup,
)


class FakeSttProvider:
    """最小 STT Provider：只回固定文本，并记录收到的请求。"""

    ADAPTER_VERSION = "test.stt.v1"

    def __init__(self) -> None:
        self.received_requests: list[object] = []

    def transcribe(self, request: object) -> SttProviderResult:
        self.received_requests.append(request)
        return SttProviderResult(text="你好")


class RecordingSttRegistry:
    """记录 resolve 被调用时传入的 provider 配置，便于断言选择结果。"""

    def __init__(self, provider: FakeSttProvider) -> None:
        self.provider = provider
        self.resolved_provider_ids: list[str] = []

    def resolve(self, provider_config: ProviderConfig) -> FakeSttProvider:
        self.resolved_provider_ids.append(provider_config.provider_id)
        return self.provider


def build_runtime_config() -> RuntimeConfig:
    """构造含两个 STT provider 的真实 RuntimeConfig，不经过配置文件。"""
    default_provider = ProviderConfig(
        service_name="stt",
        adapter_kind="fake_stt",
        provider_id="stt_default",
        default_model_id="model_a",
        models=[
            ProviderModelConfig(model_id="model_a"),
            ProviderModelConfig(model_id="model_b"),
        ],
    )
    other_provider = ProviderConfig(
        service_name="stt",
        adapter_kind="fake_stt",
        provider_id="stt_other",
        default_model_id="model_c",
        models=[ProviderModelConfig(model_id="model_c")],
    )
    group = ServiceSettingsGroup(
        enabled=True,
        default_provider_id="stt_default",
        providers=[default_provider, other_provider],
    )
    profile = RuntimeProfile(profile_id="default", display_name="默认配置", stt=group)
    return RuntimeConfig(active_profile=profile, available_profiles=(profile,))


class SttCliArgumentTests(unittest.TestCase):
    def test_parser_uses_none_when_provider_not_specified(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["run-stt-audio", "sample.wav"])

        self.assertIsNone(args.provider_id)
        self.assertIsNone(args.model_id)

    def test_parser_accepts_explicit_provider_and_model(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "run-stt-audio",
                "sample.wav",
                "--provider-id",
                "stt_other",
                "--model-id",
                "model_c",
            ]
        )

        self.assertEqual("stt_other", args.provider_id)
        self.assertEqual("model_c", args.model_id)


class SttProviderSelectionTests(unittest.TestCase):
    def test_transcribe_uses_runtime_default_provider_without_override(self) -> None:
        registry = RecordingSttRegistry(FakeSttProvider())
        service = SttService(
            runtime_config=build_runtime_config(),
            provider_registry=registry,  # type: ignore[arg-type]
        )

        result = service.transcribe(
            audio_ref={"type": "local_path", "value": "sample.wav", "mime_type": "audio/wav"},
        )

        self.assertEqual("success", result["status"])
        self.assertEqual(["stt_default"], registry.resolved_provider_ids)
        self.assertEqual("stt_default", result["meta"]["provider"])
        # 未指定 model 时使用该 provider 的 default_model_id
        self.assertEqual("model_a", result["meta"]["model"])

    def test_transcribe_passes_explicit_provider_and_model_through(self) -> None:
        registry = RecordingSttRegistry(FakeSttProvider())
        service = SttService(
            runtime_config=build_runtime_config(),
            provider_registry=registry,  # type: ignore[arg-type]
        )

        result = service.transcribe(
            audio_ref={"type": "local_path", "value": "sample.wav", "mime_type": "audio/wav"},
            provider_id="stt_other",
            model_id="model_c",
        )

        self.assertEqual("success", result["status"])
        self.assertEqual(["stt_other"], registry.resolved_provider_ids)
        self.assertEqual("stt_other", result["meta"]["provider"])
        self.assertEqual("model_c", result["meta"]["model"])


if __name__ == "__main__":
    unittest.main()
