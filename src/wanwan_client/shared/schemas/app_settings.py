"""
应用设置模型。

当前阶段先覆盖：
1. 设置保存对象
2. 运行时档案对象
3. 桌宠最小交互设置对象
"""

from dataclasses import dataclass, field
from typing import Any

from src.wanwan_client.shared.schemas.provider_config import ProviderConfig


@dataclass(slots=True)
class ServiceSettingsGroup:
    """
    单类服务配置集合。
    """

    enabled: bool = True
    default_provider_id: str = ""
    providers: list[ProviderConfig] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """
        转为可序列化字典。
        """
        return {
            "enabled": self.enabled,
            "default_provider_id": self.default_provider_id,
            "providers": [provider.to_dict() for provider in self.providers],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ServiceSettingsGroup":
        """
        从字典恢复对象。
        """
        source = data or {}
        return cls(
            enabled=bool(source.get("enabled", True)),
            default_provider_id=str(source.get("default_provider_id", "")),
            providers=[
                ProviderConfig.from_dict(item)
                for item in source.get("providers", [])
                if isinstance(item, dict)
            ],
        )


@dataclass(slots=True)
class DesktopInteractionSettings:
    """
    桌宠交互相关设置。

    当前只保留最小字段，不扩成复杂状态机。
    """

    auto_play_response: bool = True
    enable_text_input: bool = True
    enable_push_to_talk: bool = False
    volume: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """
        转为可序列化字典。
        """
        return {
            "auto_play_response": self.auto_play_response,
            "enable_text_input": self.enable_text_input,
            "enable_push_to_talk": self.enable_push_to_talk,
            "volume": self.volume,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DesktopInteractionSettings":
        """
        从字典恢复对象。
        """
        source = data or {}
        return cls(
            auto_play_response=bool(source.get("auto_play_response", True)),
            enable_text_input=bool(source.get("enable_text_input", True)),
            enable_push_to_talk=bool(source.get("enable_push_to_talk", False)),
            volume=float(source.get("volume", 1.0)),
        )


@dataclass(slots=True)
class RuntimeProfile:
    """
    单个运行时配置档。

    用于承接“设置保存 -> 设置应用”的最小骨架。
    """

    profile_id: str = "default"
    display_name: str = "默认配置"
    llm: ServiceSettingsGroup = field(default_factory=ServiceSettingsGroup)
    tts: ServiceSettingsGroup = field(default_factory=ServiceSettingsGroup)
    stt: ServiceSettingsGroup = field(default_factory=ServiceSettingsGroup)
    rvc: ServiceSettingsGroup = field(default_factory=ServiceSettingsGroup)
    desktop: DesktopInteractionSettings = field(default_factory=DesktopInteractionSettings)

    def to_dict(self) -> dict[str, Any]:
        """
        转为可序列化字典。
        """
        return {
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "llm": self.llm.to_dict(),
            "tts": self.tts.to_dict(),
            "stt": self.stt.to_dict(),
            "rvc": self.rvc.to_dict(),
            "desktop": self.desktop.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RuntimeProfile":
        """
        从字典恢复对象。
        """
        source = data or {}
        return cls(
            profile_id=str(source.get("profile_id", "default")),
            display_name=str(source.get("display_name", "默认配置")),
            llm=ServiceSettingsGroup.from_dict(source.get("llm")),
            tts=ServiceSettingsGroup.from_dict(source.get("tts")),
            stt=ServiceSettingsGroup.from_dict(source.get("stt")),
            rvc=ServiceSettingsGroup.from_dict(source.get("rvc")),
            desktop=DesktopInteractionSettings.from_dict(source.get("desktop")),
        )


@dataclass(slots=True)
class AppSettings:
    """
    应用设置根对象。
    """

    schema_version: str = "settings.v0.1"
    active_profile_id: str = "default"
    profiles: list[RuntimeProfile] = field(default_factory=lambda: [RuntimeProfile()])

    def ensure_minimum(self) -> "AppSettings":
        """
        保证最小可用设置结构。

        当前阶段只做最小回退：
        - profiles 为空时补一个默认 profile
        - active_profile_id 为空时回退到默认 profile
        """
        if not self.profiles:
            self.profiles = [RuntimeProfile()]

        if not self.active_profile_id:
            self.active_profile_id = self.profiles[0].profile_id

        return self

    def to_dict(self) -> dict[str, Any]:
        """
        转为可序列化字典。
        """
        normalized = self.ensure_minimum()
        return {
            "schema_version": normalized.schema_version,
            "active_profile_id": normalized.active_profile_id,
            "profiles": [profile.to_dict() for profile in normalized.profiles],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AppSettings":
        """
        从字典恢复对象。
        """
        source = data or {}
        settings = cls(
            schema_version=str(source.get("schema_version", "settings.v0.1")),
            active_profile_id=str(source.get("active_profile_id", "default")),
            profiles=[
                RuntimeProfile.from_dict(item)
                for item in source.get("profiles", [])
                if isinstance(item, dict)
            ],
        )
        return settings.ensure_minimum()
