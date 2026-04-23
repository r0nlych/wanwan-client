"""
provider 配置模型。

当前阶段只定义结构，不绑定任何具体厂商。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProviderEndpointConfig:
    """
    provider 连接配置。

    说明：
    - `api_key_env` 只声明环境变量名，不在这里读取真实密钥
    - `api_host`、`api_path` 保持集中定义，避免散落硬编码
    """

    api_host: str = ""
    api_path: str = ""
    api_key_env: str = ""
    timeout_seconds: int = 30

    def to_dict(self) -> dict[str, Any]:
        """
        转为可序列化字典。
        """
        return {
            "api_host": self.api_host,
            "api_path": self.api_path,
            "api_key_env": self.api_key_env,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProviderEndpointConfig":
        """
        从字典恢复对象。
        """
        source = data or {}
        return cls(
            api_host=str(source.get("api_host", "")),
            api_path=str(source.get("api_path", "")),
            api_key_env=str(source.get("api_key_env", "")),
            timeout_seconds=int(source.get("timeout_seconds", 30)),
        )


@dataclass(slots=True)
class ProviderModelConfig:
    """
    单个模型配置。
    """

    model_id: str
    enabled: bool = True
    label: str = ""
    capabilities: tuple[str, ...] = ()
    context_window: int | None = None
    max_output_tokens: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """
        转为可序列化字典。
        """
        return {
            "model_id": self.model_id,
            "enabled": self.enabled,
            "label": self.label,
            "capabilities": list(self.capabilities),
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProviderModelConfig":
        """
        从字典恢复对象。
        """
        source = data or {}
        return cls(
            model_id=str(source.get("model_id", "")),
            enabled=bool(source.get("enabled", True)),
            label=str(source.get("label", "")),
            capabilities=tuple(str(item) for item in source.get("capabilities", [])),
            context_window=source.get("context_window"),
            max_output_tokens=source.get("max_output_tokens"),
            extra=dict(source.get("extra", {})),
        )


@dataclass(slots=True)
class ProviderConfig:
    """
    provider 级配置。

    说明：
    - `service_name` 用于区分 llm / tts / stt / rvc
    - `provider_id` 作为仓库内稳定标识
    - `default_model_id` 只表示默认选择，不表示真实可调用
    """

    service_name: str
    provider_id: str
    enabled: bool = True
    label: str = ""
    endpoint: ProviderEndpointConfig = field(default_factory=ProviderEndpointConfig)
    models: list[ProviderModelConfig] = field(default_factory=list)
    default_model_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """
        转为可序列化字典。
        """
        return {
            "service_name": self.service_name,
            "provider_id": self.provider_id,
            "enabled": self.enabled,
            "label": self.label,
            "endpoint": self.endpoint.to_dict(),
            "models": [model.to_dict() for model in self.models],
            "default_model_id": self.default_model_id,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProviderConfig":
        """
        从字典恢复对象。
        """
        source = data or {}
        return cls(
            service_name=str(source.get("service_name", "")),
            provider_id=str(source.get("provider_id", "")),
            enabled=bool(source.get("enabled", True)),
            label=str(source.get("label", "")),
            endpoint=ProviderEndpointConfig.from_dict(source.get("endpoint")),
            models=[
                ProviderModelConfig.from_dict(item)
                for item in source.get("models", [])
                if isinstance(item, dict)
            ],
            default_model_id=str(source.get("default_model_id", "")),
            extra=dict(source.get("extra", {})),
        )
