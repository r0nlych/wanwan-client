"""
配置应用最小入口。

当前阶段职责：
1. 读取当前设置
2. 生成当前运行时配置
3. 暴露 active_profile 与可用 profiles
4. 支持切换 profile 后保存并重新生成运行时配置

不负责：
- 桌宠 UI
- 设置页
- provider 调用
- 文本链路业务
"""

from dataclasses import dataclass

from src.wanwan_client.core.config.config_manager import ConfigManager
from src.wanwan_client.core.config.runtime_config import RuntimeConfig
from src.wanwan_client.shared.schemas import AppSettings


@dataclass(slots=True)
class RuntimeAppState:
    """
    配置应用入口当前状态。
    """

    settings: AppSettings
    runtime_config: RuntimeConfig

    @property
    def active_profile_id(self) -> str:
        """
        返回当前生效 profile 标识。
        """
        return self.runtime_config.get_active_profile_id()

    @property
    def available_profile_ids(self) -> tuple[str, ...]:
        """
        返回当前可用 profile 标识列表。
        """
        return self.runtime_config.list_profile_ids()


class RuntimeApp:
    """
    配置应用最小入口。

    当前阶段作为应用层收口点，向更上层提供最小配置应用能力。
    """

    def __init__(self, config_manager: ConfigManager | None = None):
        self.config_manager = config_manager or ConfigManager()

    def load_state(self) -> RuntimeAppState:
        """
        读取当前设置并生成运行时配置。
        """
        settings = self.config_manager.load_persisted_settings()
        runtime_config = self.config_manager.build_runtime_config(settings)
        return RuntimeAppState(settings=settings, runtime_config=runtime_config)

    def get_active_profile(self) -> str:
        """
        获取当前生效 profile。
        """
        return self.load_state().active_profile_id

    def get_available_profiles(self) -> tuple[str, ...]:
        """
        获取当前可用 profiles。
        """
        return self.load_state().available_profile_ids

    def switch_active_profile(self, profile_id: str) -> RuntimeAppState:
        """
        切换 active_profile，保存并重新生成 runtime_config。
        """
        current_settings = self.config_manager.load_persisted_settings()
        updated_settings, runtime_config = self.config_manager.switch_profile_and_build_runtime(
            profile_id=profile_id,
            settings=current_settings,
        )
        return RuntimeAppState(settings=updated_settings, runtime_config=runtime_config)

    def reload_runtime_config(self) -> RuntimeAppState:
        """
        从当前已保存设置重新生成状态。
        """
        return self.load_state()

