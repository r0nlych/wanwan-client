"""
TTS provider registry keyed by adapter_kind.
"""

from __future__ import annotations

from src.wanwan_client.services.tts.providers.base import BaseTtsProvider
from src.wanwan_client.services.tts.providers.doubao_tts import DoubaoTtsProvider
from src.wanwan_client.services.tts.providers.openai_compatible_tts import (
    OpenAICompatibleTtsProvider,
)
from src.wanwan_client.shared.schemas import ProviderConfig


class TtsProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseTtsProvider] = {
            "openai_compatible": OpenAICompatibleTtsProvider(),
            "doubao_tts_sse": DoubaoTtsProvider(),
        }

    def resolve(self, provider_config: ProviderConfig) -> BaseTtsProvider:
        adapter_kind = str(provider_config.adapter_kind).strip()
        provider = self._providers.get(adapter_kind)
        if provider is None:
            raise ValueError(
                f"Unsupported TTS adapter_kind for provider {provider_config.provider_id}: {adapter_kind}"
            )
        return provider
