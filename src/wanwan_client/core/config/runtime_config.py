"""
运行时生效配置骨架。
说明：
- 这是 `core.config` 面向主链路暴露的对象
- 它来自持久化设置，但不等于原始设置文件
- 当前阶段只做选择和装配，不做真实 provider 校验
"""

from dataclasses import dataclass

from src.wanwan_client.shared.schemas import (
    AppSettings,
    ProviderConfig,
    ProviderModelConfig,
    RuntimeProfile,
    ServiceSettingsGroup,
)


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

    def get_service_group(self, service_name: str) -> ServiceSettingsGroup:
        """
        返回当前 active_profile 下的服务配置组。
        """
        mapping = {
            "llm": self.active_profile.llm,
            "tts": self.active_profile.tts,
            "stt": self.active_profile.stt,
            "rvc": self.active_profile.rvc,
        }
        try:
            return mapping[service_name]
        except KeyError as error:
            raise ValueError(f"Unsupported service_name: {service_name}") from error

    def resolve_provider(self, service_name: str, provider_id: str | None = None) -> ProviderConfig:
        """
        解析当前服务实际生效的 provider 配置。
        """
        group = self.get_service_group(service_name)
        if not group.enabled:
            raise ValueError(f"Service group is disabled: {service_name}")

        enabled_providers = [
            provider
            for provider in group.providers
            if provider.enabled and provider.provider_id
        ]
        if not enabled_providers:
            raise ValueError(f"No enabled providers configured for service: {service_name}")

        target_provider_id = provider_id or group.default_provider_id or enabled_providers[0].provider_id
        for provider in enabled_providers:
            if provider.provider_id == target_provider_id:
                return provider

        raise ValueError(
            f"Configured provider not found for service {service_name}: {target_provider_id}"
        )

    def resolve_provider_and_model(
        self,
        service_name: str,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> tuple[ProviderConfig, ProviderModelConfig]:
        """
        解析当前服务实际生效的 provider 与 model 配置。
        """
        provider = self.resolve_provider(service_name=service_name, provider_id=provider_id)
        enabled_models = [
            model
            for model in provider.models
            if model.enabled and model.model_id
        ]
        if not enabled_models:
            raise ValueError(f"No enabled models configured for provider: {provider.provider_id}")

        target_model_id = model_id or provider.default_model_id or enabled_models[0].model_id
        for model in enabled_models:
            if model.model_id == target_model_id:
                return provider, model

        raise ValueError(
            f"Configured model not found for provider {provider.provider_id}: {target_model_id}"
        )

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
