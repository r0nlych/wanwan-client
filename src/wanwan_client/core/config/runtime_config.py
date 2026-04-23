"""
运行时生效配置骨架。

说明：
- 这是 `core.config` 面向主链路暴露的对象
- 它来自持久化设置，但不等于原始设置文件
- 当前阶段只做选择和装配，不做真实 provider 校验
"""

from dataclasses import dataclass

from src.wanwan_client.shared.schemas import AppSettings, RuntimeProfile


@dataclass(slots=True)
class RuntimeConfig:
    """
    当前会被主链路消费的生效配置对象。
    """

    active_profile: RuntimeProfile
    available_profiles: tuple[RuntimeProfile, ...]

    def get_active_profile_id(self) -> str:
        """
        返回当前生效 profile 标识。
        """
        return self.active_profile.profile_id

    def list_profile_ids(self) -> tuple[str, ...]:
        """
        返回当前可用 profile 标识列表。
        """
        return tuple(profile.profile_id for profile in self.available_profiles)

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "RuntimeConfig":
        """
        从设置对象中选出当前激活 profile。

        当前阶段：
        - 找到匹配 profile 就使用
        - 找不到时退回首个 profile
        - 不在这里做复杂校验和容错
        """
        normalized_settings = settings.ensure_minimum()

        for profile in normalized_settings.profiles:
            if profile.profile_id == settings.active_profile_id:
                return cls(
                    active_profile=profile,
                    available_profiles=tuple(normalized_settings.profiles),
                )

        return cls(
            active_profile=normalized_settings.profiles[0],
            available_profiles=tuple(normalized_settings.profiles),
        )
