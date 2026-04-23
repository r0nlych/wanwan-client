"""
Registry for STT provider adapters.
"""

from __future__ import annotations

from src.wanwan_client.services.stt.providers.base import SttProvider
from src.wanwan_client.services.stt.providers.doubao_stt import (
    DoubaoAsyncSttProvider,
    DoubaoFlashSttProvider,
)
from src.wanwan_client.shared.schemas import ProviderConfig


class SttProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, SttProvider] = {
            "doubao_async": DoubaoAsyncSttProvider(),
            "doubao_stt_async": DoubaoAsyncSttProvider(),
            "doubao_flash": DoubaoFlashSttProvider(),
            "doubao_stt_flash": DoubaoFlashSttProvider(),
        }

    def resolve(self, provider_config: ProviderConfig) -> SttProvider:
        adapter_kind = str(provider_config.adapter_kind).strip()
        if not adapter_kind or adapter_kind.startswith("("):
            raise ValueError(
                f"Missing adapter_kind for STT provider: {provider_config.provider_id}"
            )

        try:
            return self._providers[adapter_kind]
        except KeyError as error:
            raise ValueError(
                f"Unsupported STT adapter_kind: {adapter_kind}"
            ) from error
