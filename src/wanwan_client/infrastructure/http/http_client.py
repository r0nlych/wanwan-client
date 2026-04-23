"""
Generic HTTP transport helpers for provider adapters.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from src.wanwan_client.shared.schemas import ProviderConfig


class ProviderHttpClient:
    def __init__(self, provider_config: ProviderConfig):
        self.provider_config = provider_config

    def build_url(self, api_path: str | None = None) -> str:
        api_host = str(self.provider_config.api_host).strip()
        path = str(api_path or self.provider_config.api_path).strip()
        if not api_host or api_host.startswith("("):
            raise ValueError(f"Provider api_host is empty: {self.provider_config.provider_id}")
        if not path or path.startswith("("):
            raise ValueError(f"Provider api_path is empty: {self.provider_config.provider_id}")
        return f"{api_host.rstrip('/')}/{path.lstrip('/')}"

    def resolve_api_key(self) -> str:
        explicit_api_key = str(self.provider_config.api_key).strip()
        if explicit_api_key and not explicit_api_key.startswith("("):
            return explicit_api_key

        api_key_env = str(self.provider_config.api_key_env).strip()
        if not api_key_env or api_key_env.startswith("("):
            return ""

        return os.getenv(api_key_env, "").strip()

    def request(
        self,
        *,
        method: str,
        api_path: str | None = None,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        data: bytes | str | None = None,
        timeout_seconds: float | int | None = None,
    ) -> requests.Response:
        resolved_timeout = timeout_seconds
        if resolved_timeout is None:
            raw_timeout = self.provider_config.timeout_seconds
            try:
                resolved_timeout = float(raw_timeout)
            except (TypeError, ValueError):
                raise ValueError(
                    f"Invalid timeout_seconds for provider: {self.provider_config.provider_id}"
                ) from None

        response = requests.request(
            method=method.upper(),
            url=self.build_url(api_path=api_path),
            headers=headers or {},
            json=json_body,
            data=data,
            timeout=resolved_timeout,
        )
        if response.status_code >= 400:
            raise requests.HTTPError(
                f"{response.status_code} Client Error: {response.reason} for url: {response.url}",
                response=response,
            )
        return response
