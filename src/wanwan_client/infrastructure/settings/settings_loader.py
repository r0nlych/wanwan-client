"""
旧 settings_loader 升级为设置入口骨架。

当前定位：
1. 统一暴露配置目录和默认设置入口。
2. 不承载运行时配置装配逻辑。
3. 不在此处写 provider 真实接入代码。
"""

import json
from pathlib import Path

from src.wanwan_client.shared.schemas import AppSettings


class SettingsLoader:
    """
    设置加载入口骨架。

    当前阶段只负责：
    - 提供默认设置对象
    - 提供设置文件路径约定
    """

    DEFAULT_SETTINGS_FILENAME = "app_settings.json"

    @staticmethod
    def get_settings_dir() -> Path:
        """
        返回设置目录。
        """
        return Path("data") / "config"

    @classmethod
    def get_settings_path(cls) -> Path:
        """
        返回默认设置文件路径。
        """
        return cls.get_settings_dir() / cls.DEFAULT_SETTINGS_FILENAME

    @staticmethod
    def build_default_settings() -> AppSettings:
        """
        返回默认设置对象。

        当前阶段默认返回空骨架，后续再逐步补默认 profile。
        """
        return AppSettings().ensure_minimum()

    @classmethod
    def ensure_settings_dir(cls) -> Path:
        """
        确保设置目录存在。
        """
        settings_dir = cls.get_settings_dir()
        settings_dir.mkdir(parents=True, exist_ok=True)
        return settings_dir

    @staticmethod
    def read_settings_file(settings_path: Path) -> AppSettings:
        """
        从本地文件读取设置。

        当前阶段：
        - 文件不存在时回退到默认设置
        - 文件损坏或解析失败时回退到默认设置
        """
        if not settings_path.exists():
            return SettingsLoader.build_default_settings()

        try:
            with settings_path.open("r", encoding="utf-8") as file:
                raw_data = json.load(file)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return SettingsLoader.build_default_settings()

        if not isinstance(raw_data, dict):
            return SettingsLoader.build_default_settings()

        return AppSettings.from_dict(raw_data)

    @staticmethod
    def write_settings_file(settings_path: Path, settings: AppSettings) -> None:
        """
        将设置对象写入本地文件。
        """
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = settings.ensure_minimum().to_dict()
        with settings_path.open("w", encoding="utf-8") as file:
            json.dump(serialized, file, ensure_ascii=False, indent=2)
