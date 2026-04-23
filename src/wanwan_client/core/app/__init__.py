"""
桌宠应用级核心导出。

当前阶段只导出配置应用最小入口，不接 UI，不接 provider。
"""

from src.wanwan_client.core.app.runtime_app import RuntimeApp, RuntimeAppState

__all__ = ["RuntimeApp", "RuntimeAppState"]

