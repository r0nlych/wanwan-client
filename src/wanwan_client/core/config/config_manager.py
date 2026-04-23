"""
配置管理骨架。

阶段 2 目标：
1. 承接持久化设置对象。
2. 负责构建运行时生效配置对象。
3. 不直接处理 provider 真实调用逻辑。
"""

from dataclasses import replace
from typing import Optional

from src.wanwan_client.core.config.runtime_config import RuntimeConfig
from src.wanwan_client.infrastructure.settings.settings_repository import SettingsRepository
from src.wanwan_client.shared.schemas import AppSettings


class ConfigManager:
    """
    配置管理器骨架。

    设计约束：
    - `infrastructure.settings` 负责设置读写入口
    - `core.config` 负责把设置装配成运行时可消费对象
    - `services` 只读取生效配置，不负责持久化配置
    """

    def __init__(self, repository: Optional[SettingsRepository] = None):
        self.repository = repository or SettingsRepository()

    def load_persisted_settings(self) -> AppSettings:
        """
        读取当前已保存设置。

        当前阶段只返回结构化对象，不接真实 provider。
        """
        return self.repository.load()

    def save_settings(self, settings: AppSettings) -> None:
        """
        保存设置对象。

        当前阶段只保留保存入口，不扩展校验和迁移逻辑。
        """
        self.repository.save(settings)

    def build_runtime_config(self, settings: Optional[AppSettings] = None) -> RuntimeConfig:
        """
        基于持久化设置构建运行时生效配置。
        """
        persisted_settings = settings or self.load_persisted_settings()
        return RuntimeConfig.from_settings(persisted_settings)

    def reload_runtime_config(self) -> RuntimeConfig:
        """
        从当前已保存设置重新生成运行时配置。
        """
        return self.build_runtime_config()

    def with_profile(self, profile_id: str, settings: Optional[AppSettings] = None) -> AppSettings:
        """
        返回切换激活配置档后的新设置对象。

        当前阶段先保留对象层入口，不直接做 UI 和业务联动。
        """
        persisted_settings = settings or self.load_persisted_settings()
        updated_settings = replace(persisted_settings, active_profile_id=profile_id)
        return updated_settings.ensure_minimum()

    def save_with_profile(self, profile_id: str, settings: Optional[AppSettings] = None) -> AppSettings:
        """
        更新激活 profile 并立即保存。
        """
        updated_settings = self.with_profile(profile_id=profile_id, settings=settings)
        self.save_settings(updated_settings)
        return updated_settings

    def switch_profile_and_build_runtime(
        self,
        profile_id: str,
        settings: Optional[AppSettings] = None,
    ) -> tuple[AppSettings, RuntimeConfig]:
        """
        切换激活 profile，保存后返回新的设置与运行时配置。
        """
        updated_settings = self.save_with_profile(profile_id=profile_id, settings=settings)
        runtime_config = self.build_runtime_config(updated_settings)
        return updated_settings, runtime_config
