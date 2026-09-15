"""LLM Provider 的厂商无关契约与同步流式降级。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator

from src.wanwan_client.shared.schemas import ProviderConfig, ProviderModelConfig


class BaseLlmProvider(ABC):
    """保留同步接口，并为不支持 Streaming 的 Provider 提供安全 fallback。"""

    ADAPTER_VERSION = "llm.provider.base.v1"
    SUPPORTS_STREAMING = False

    @abstractmethod
    def generate_reply(
        self,
        *,
        messages: list[dict[str, Any]],
        provider_config: ProviderConfig,
        model_config: ProviderModelConfig,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def stream_reply(
        self,
        *,
        messages: list[dict[str, Any]],
        provider_config: ProviderConfig,
        model_config: ProviderModelConfig,
    ) -> Iterator[str]:
        """默认把同步完整回复作为单个 chunk 输出。"""
        result = self.generate_reply(
            messages=messages,
            provider_config=provider_config,
            model_config=model_config,
        )
        reply_text = str(result.get("reply_text", ""))
        if reply_text:
            yield reply_text
