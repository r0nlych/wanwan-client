"""按 adapter_kind 解析 LLM Provider。"""

from src.wanwan_client.services.llm.providers.base import BaseLlmProvider
from src.wanwan_client.services.llm.providers.openai_compatible_llm import (
    OpenAICompatibleLlmProvider,
)
from src.wanwan_client.shared.schemas import ProviderConfig


class LlmProviderRegistry:
    """让 Pipeline 只依赖 LLM 能力，不感知具体厂商。"""

    def __init__(self) -> None:
        self._providers: dict[str, BaseLlmProvider] = {
            "openai_compatible": OpenAICompatibleLlmProvider(),
        }

    def resolve(self, provider_config: ProviderConfig) -> BaseLlmProvider:
        adapter_kind = str(provider_config.adapter_kind).strip()
        provider = self._providers.get(adapter_kind)
        if provider is None:
            raise ValueError(
                f"Unsupported LLM adapter_kind for provider {provider_config.provider_id}: {adapter_kind}"
            )
        return provider
