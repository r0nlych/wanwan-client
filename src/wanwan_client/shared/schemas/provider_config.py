"""
Provider 配置模型。
当前阶段只定义可直接填写的配置模板结构，不绑定任何真实 provider 实现。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProviderModelConfig:
    """
    单个模型配置模板。
    """

    model_id: str = "(填写模型 ID)"
    display_name: str = "(填写模型显示名)"
    enabled: bool = True
    capabilities: tuple[str, ...] = ()
    context_window: int | str | None = "(填写上下文窗口)"
    max_output_tokens: int | str | None = "(填写最大输出 Token)"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "enabled": self.enabled,
            "capabilities": list(self.capabilities),
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProviderModelConfig":
        source = data or {}
        legacy_display_name = source.get("label", "(填写模型显示名)")
        return cls(
            model_id=str(source.get("model_id", "(填写模型 ID)")),
            display_name=str(source.get("display_name", legacy_display_name)),
            enabled=bool(source.get("enabled", True)),
            capabilities=tuple(str(item) for item in source.get("capabilities", [])),
            context_window=source.get("context_window", "(填写上下文窗口)"),
            max_output_tokens=source.get("max_output_tokens", "(填写最大输出 Token)"),
            extra=dict(source.get("extra", {})),
        )


@dataclass(slots=True)
class ProviderConfig:
    """
    Provider 级配置模板。
    设计目标：
    - 通用字段固定
    - 服务专属字段通过 `extra`
    - 兼容旧版 `endpoint` 嵌套结构读取
    """

    service_name: str = "(填写服务类型)"
    adapter_kind: str = "(填写 Provider 适配器类型)"
    provider_id: str = "(填写 Provider ID)"
    display_name: str = "(填写 Provider 显示名)"
    enabled: bool = True
    api_host: str = "(填写 API Host)"
    api_path: str = "(填写 API Path)"
    api_key: str = "(填写 API Key)"
    api_key_env: str = "(填写 API Key 环境变量名)"
    timeout_seconds: int | str = "(填写超时时间秒数)"
    default_model_id: str = "(填写默认模型 ID)"
    models: list[ProviderModelConfig] = field(default_factory=list)
    capabilities: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_name": self.service_name,
            "adapter_kind": self.adapter_kind,
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "enabled": self.enabled,
            "api_host": self.api_host,
            "api_path": self.api_path,
            "api_key": self.api_key,
            "api_key_env": self.api_key_env,
            "timeout_seconds": self.timeout_seconds,
            "default_model_id": self.default_model_id,
            "models": [model.to_dict() for model in self.models],
            "capabilities": list(self.capabilities),
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProviderConfig":
        source = data or {}
        legacy_endpoint = source.get("endpoint", {})
        if not isinstance(legacy_endpoint, dict):
            legacy_endpoint = {}

        legacy_display_name = source.get("label", "(填写 Provider 显示名)")
        return cls(
            service_name=str(source.get("service_name", "(填写服务类型)")),
            adapter_kind=str(source.get("adapter_kind", "(填写 Provider 适配器类型)")),
            provider_id=str(source.get("provider_id", "(填写 Provider ID)")),
            display_name=str(source.get("display_name", legacy_display_name)),
            enabled=bool(source.get("enabled", True)),
            api_host=str(source.get("api_host", legacy_endpoint.get("api_host", "(填写 API Host)"))),
            api_path=str(source.get("api_path", legacy_endpoint.get("api_path", "(填写 API Path)"))),
            api_key=str(source.get("api_key", "(填写 API Key)")),
            api_key_env=str(
                source.get("api_key_env", legacy_endpoint.get("api_key_env", "(填写 API Key 环境变量名)"))
            ),
            timeout_seconds=source.get(
                "timeout_seconds",
                legacy_endpoint.get("timeout_seconds", "(填写超时时间秒数)"),
            ),
            default_model_id=str(source.get("default_model_id", "(填写默认模型 ID)")),
            models=[
                ProviderModelConfig.from_dict(item)
                for item in source.get("models", [])
                if isinstance(item, dict)
            ],
            capabilities=tuple(str(item) for item in source.get("capabilities", [])),
            extra=dict(source.get("extra", {})),
        )
