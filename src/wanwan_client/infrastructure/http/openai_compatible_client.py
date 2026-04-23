"""
OpenAI-compatible HTTP client for LLM / TTS providers.
"""

from __future__ import annotations

import requests

from src.wanwan_client.infrastructure.http.http_client import ProviderHttpClient
from src.wanwan_client.shared.schemas import ProviderConfig


class OpenAICompatibleHttpClient:
    def __init__(self, provider_config: ProviderConfig):
        self.provider_config = provider_config
        self.transport = ProviderHttpClient(provider_config)
        self.url = self.transport.build_url()
        self.timeout_seconds = self._resolve_timeout_seconds()
        self.api_key = self._resolve_api_key()

    def _resolve_timeout_seconds(self) -> float:
        raw_timeout = self.provider_config.timeout_seconds
        try:
            return float(raw_timeout)
        except (TypeError, ValueError):
            raise ValueError(
                f"Invalid timeout_seconds for provider: {self.provider_config.provider_id}"
            ) from None

    def _resolve_api_key(self) -> str:
        api_key = self.transport.resolve_api_key()
        if not api_key:
            raise ValueError(
                f"Missing API key for provider: {self.provider_config.provider_id}"
            )
        return api_key

    def post_json(
        self,
        payload: dict,
        *,
        accept: str = "application/json",
    ) -> requests.Response:
        headers = {
            "Content-Type": "application/json",
            "Accept": accept,
            "Authorization": f"Bearer {self.api_key}",
        }
        response = requests.post(
            self.url,
            json=payload,
            headers=headers,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response
