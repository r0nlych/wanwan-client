"""
设置持久化仓库骨架。

当前阶段：
- 落本地 JSON 文件读写最小闭环
- 保持缺失或读取失败时的默认回退
- 不做复杂迁移和复杂兼容逻辑
"""

from pathlib import Path

from src.wanwan_client.infrastructure.settings.settings_loader import SettingsLoader
from src.wanwan_client.shared.schemas import AppSettings


class SettingsRepository:
    """
    设置仓库骨架。
    """

    def __init__(self, settings_path: Path | None = None):
        self.settings_path = settings_path or SettingsLoader.get_settings_path()

    def load(self) -> AppSettings:
        """
        读取设置对象。

        当前阶段读取本地文件，失败时回退到默认设置。
        """
        return SettingsLoader.read_settings_file(self.settings_path)

    def save(self, settings: AppSettings) -> None:
        """
        保存设置对象。

        当前阶段写入本地 JSON 文件。
        """
        SettingsLoader.write_settings_file(self.settings_path, settings)
