"""
Settings loading entry.

Current responsibilities:
- expose the settings file location
- build default editable templates
- read/write persisted settings
"""

from __future__ import annotations

import json
from pathlib import Path

from src.wanwan_client.shared.constants.capabilities import (
    CAPABILITY_AUDIO_IN,
    CAPABILITY_AUDIO_OUT,
    CAPABILITY_CHAT,
    CAPABILITY_REASONING,
    CAPABILITY_TOOLS,
    CAPABILITY_VISION,
    CAPABILITY_VOICE_CONVERT,
)
from src.wanwan_client.shared.schemas import (
    AppSettings,
    ProviderConfig,
    ProviderModelConfig,
    RuntimeProfile,
    ServiceSettingsGroup,
)


class SettingsLoader:
    DEFAULT_SETTINGS_FILENAME = "app_settings.json"

    @staticmethod
    def get_settings_dir() -> Path:
        return Path("data") / "config"

    @classmethod
    def get_settings_path(cls) -> Path:
        return cls.get_settings_dir() / cls.DEFAULT_SETTINGS_FILENAME

    @classmethod
    def _build_llm_group(cls) -> ServiceSettingsGroup:
        provider = ProviderConfig(
            service_name="llm",
            adapter_kind="openai_compatible",
            provider_id="llm_primary_template",
            display_name="(填写 LLM Provider 显示名)",
            enabled=True,
            api_host="(填写 LLM API Host)",
            api_path="(填写 LLM API Path)",
            api_key="(填写 LLM API Key)",
            api_key_env="(填写 LLM API Key 环境变量名)",
            timeout_seconds="(填写 LLM 超时时间秒数)",
            default_model_id="llm_primary_model",
            capabilities=(
                CAPABILITY_CHAT,
                CAPABILITY_REASONING,
                CAPABILITY_VISION,
                CAPABILITY_TOOLS,
            ),
            models=[
                ProviderModelConfig(
                    model_id="llm_primary_model",
                    display_name="(填写 LLM 模型显示名)",
                    enabled=True,
                    capabilities=(
                        CAPABILITY_CHAT,
                        CAPABILITY_REASONING,
                        CAPABILITY_VISION,
                        CAPABILITY_TOOLS,
                    ),
                    context_window="(填写 LLM 上下文窗口)",
                    max_output_tokens="(填写 LLM 最大输出 Token)",
                    extra={
                        "temperature": "(填写 temperature)",
                        "max_output_tokens": "(填写 max_output_tokens)",
                        "system_prompt": "(填写 system_prompt)",
                        "reasoning_enabled": "(填写 true/false)",
                        "vision_enabled": "(填写 true/false)",
                        "tools_enabled": "(填写 true/false)",
                        "custom": {
                            "notes": "(按需填写 LLM 模型扩展字段)",
                        },
                    },
                )
            ],
            extra={
                "temperature": "(填写 temperature)",
                "max_output_tokens": "(填写 max_output_tokens)",
                "system_prompt": "(填写 system_prompt)",
                "reasoning_enabled": "(填写 true/false)",
                "vision_enabled": "(填写 true/false)",
                "tools_enabled": "(填写 true/false)",
                "custom": {
                    "notes": "(按需填写 LLM Provider 扩展字段)",
                },
            },
        )
        return ServiceSettingsGroup(
            enabled=True,
            default_provider_id=provider.provider_id,
            providers=[provider],
        )

    @classmethod
    def _build_tts_group(cls) -> ServiceSettingsGroup:
        provider = ProviderConfig(
            service_name="tts",
            adapter_kind="doubao_tts_sse",
            provider_id="doubao_tts_primary",
            display_name="(填写豆包 TTS Provider 显示名)",
            enabled=True,
            api_host="https://openspeech.bytedance.com",
            api_path="/api/v3/tts/unidirectional/sse",
            api_key="(填写豆包 TTS API Key)",
            api_key_env="DOUBAO_TTS_API_KEY",
            timeout_seconds="60",
            default_model_id="doubao_tts_v3_model",
            capabilities=(CAPABILITY_AUDIO_OUT,),
            models=[
                ProviderModelConfig(
                    model_id="doubao_tts_v3_model",
                    display_name="(填写豆包 TTS 模型显示名)",
                    enabled=True,
                    capabilities=(CAPABILITY_AUDIO_OUT,),
                    context_window="0",
                    max_output_tokens="0",
                    extra={
                        "voice": "(填写 voice)",
                        "voice_type": "(填写 voice_type)",
                        "language": "(填写 language)",
                        "response_format": "wav",
                        "speed": "1.0",
                        "sample_rate": "24000",
                        "volume": "1.0",
                        "emotion": "",
                        "custom": {
                            "notes": "",
                        },
                    },
                )
            ],
            extra={
                "voice": "(填写 voice)",
                "voice_type": "(填写 voice_type)",
                "language": "(填写 language)",
                "response_format": "wav",
                "speed": "1.0",
                "sample_rate": "24000",
                "volume": "1.0",
                "resource_id": "volc.service_type.10029",
                "auth_mode": "x_api_key",
                "app_id": "(按需填写 App ID)",
                "emotion": "",
                "custom": {
                    "notes": "",
                },
            },
        )
        return ServiceSettingsGroup(
            enabled=True,
            default_provider_id=provider.provider_id,
            providers=[provider],
        )

    @classmethod
    def _build_stt_group(cls) -> ServiceSettingsGroup:
        flash_provider = ProviderConfig(
            service_name="stt",
            adapter_kind="doubao_flash",
            provider_id="doubao_flash_stt_primary",
            display_name="(填写豆包极速版 STT Provider 显示名)",
            enabled=True,
            api_host="(填写豆包极速版 STT API Host)",
            api_path="(填写豆包极速版 STT Path)",
            api_key="(填写豆包极速版 STT API Key 或 Access Token)",
            api_key_env="(填写豆包极速版 STT API Key 环境变量名)",
            timeout_seconds="(填写豆包极速版 STT 超时秒数)",
            default_model_id="doubao_flash_stt_model",
            capabilities=(CAPABILITY_AUDIO_IN,),
            models=[
                ProviderModelConfig(
                    model_id="doubao_flash_stt_model",
                    display_name="(填写豆包极速版 STT 模型显示名)",
                    enabled=True,
                    capabilities=(CAPABILITY_AUDIO_IN,),
                    context_window="(填写 STT 上下文窗口或不适用)",
                    max_output_tokens="(填写 STT 最大输出 Token 或不适用)",
                    extra={
                        "language_hint": "(填写 language_hint)",
                        "prompt": "(填写 prompt)",
                        "response_format": "(填写 response_format)",
                        "audio_format": "(填写 audio_format)",
                        "request_mode": "(填写 sync_url 或 sync_base64)",
                        "custom": {
                            "notes": "(按需填写豆包极速版 STT 模型扩展字段)",
                        },
                    },
                )
            ],
            extra={
                "language_hint": "(填写 language_hint)",
                "prompt": "(填写 prompt)",
                "response_format": "(填写 response_format)",
                "audio_format": "(填写 audio_format)",
                "request_mode": "(填写 sync_url 或 sync_base64)",
                "resource_id": "(填写豆包极速版 resource_id)",
                "auth_mode": "(填写 x_api_key 或 legacy_app_access)",
                "app_id": "(旧版控制台可填写 App ID，新版留空)",
                "custom": {
                    "notes": "(按需填写豆包极速版 STT Provider 扩展字段)",
                },
            },
        )
        async_provider = ProviderConfig(
            service_name="stt",
            adapter_kind="doubao_async",
            provider_id="doubao_async_stt_primary",
            display_name="(填写豆包标准版 STT Provider 显示名)",
            enabled=True,
            api_host="(填写豆包标准版 STT API Host)",
            api_path="(填写豆包标准版 STT Submit Path)",
            api_key="(填写豆包标准版 STT API Key 或 Access Token)",
            api_key_env="(填写豆包标准版 STT API Key 环境变量名)",
            timeout_seconds="(填写豆包标准版 STT 单次请求超时秒数)",
            default_model_id="doubao_async_stt_model",
            capabilities=(CAPABILITY_AUDIO_IN,),
            models=[
                ProviderModelConfig(
                    model_id="doubao_async_stt_model",
                    display_name="(填写豆包标准版 STT 模型显示名)",
                    enabled=True,
                    capabilities=(CAPABILITY_AUDIO_IN,),
                    context_window="(填写 STT 上下文窗口或不适用)",
                    max_output_tokens="(填写 STT 最大输出 Token 或不适用)",
                    extra={
                        "language_hint": "(填写 language_hint)",
                        "prompt": "(填写 prompt)",
                        "response_format": "(填写 response_format)",
                        "audio_format": "(填写 audio_format)",
                        "request_mode": "(填写 async_url 或 async_base64)",
                        "custom": {
                            "notes": "(按需填写豆包标准版 STT 模型扩展字段)",
                        },
                    },
                )
            ],
            extra={
                "language_hint": "(填写 language_hint)",
                "prompt": "(填写 prompt)",
                "response_format": "(填写 response_format)",
                "audio_format": "(填写 audio_format)",
                "request_mode": "(填写 async_url 或 async_base64)",
                "query_path": "(填写豆包标准版 STT Query Path)",
                "query_interval_ms": "(填写轮询间隔毫秒数)",
                "query_timeout_seconds": "(填写轮询超时秒数)",
                "resource_id": "(填写豆包标准版 resource_id)",
                "auth_mode": "(填写 x_api_key 或 legacy_app_access)",
                "app_id": "(旧版控制台可填写 App ID，新版留空)",
                "custom": {
                    "notes": "(按需填写豆包标准版 STT Provider 扩展字段)",
                },
            },
        )
        return ServiceSettingsGroup(
            enabled=True,
            default_provider_id=flash_provider.provider_id,
            providers=[flash_provider, async_provider],
        )

    @classmethod
    def _build_rvc_group(cls) -> ServiceSettingsGroup:
        provider = ProviderConfig(
            service_name="rvc",
            adapter_kind="(填写 RVC Provider 适配器类型)",
            provider_id="rvc_primary_template",
            display_name="(填写 RVC Provider 显示名)",
            enabled=True,
            api_host="(填写 RVC API Host)",
            api_path="(填写 RVC API Path)",
            api_key="(填写 RVC API Key)",
            api_key_env="(填写 RVC API Key 环境变量名)",
            timeout_seconds="(填写 RVC 超时时间秒数)",
            default_model_id="rvc_primary_model",
            capabilities=(CAPABILITY_VOICE_CONVERT,),
            models=[
                ProviderModelConfig(
                    model_id="rvc_primary_model",
                    display_name="(填写 RVC 模型显示名)",
                    enabled=True,
                    capabilities=(CAPABILITY_VOICE_CONVERT,),
                    context_window="(填写 RVC 上下文窗口或不适用)",
                    max_output_tokens="(填写 RVC 最大输出 Token 或不适用)",
                    extra={
                        "model": "(填写 model)",
                        "pitch": "(填写 pitch)",
                        "index_rate": "(填写 index_rate)",
                        "infer_host": "(填写 infer_host)",
                        "infer_path": "(填写 infer_path)",
                        "custom": {
                            "notes": "(按需填写 RVC 模型扩展字段)",
                        },
                    },
                )
            ],
            extra={
                "model": "(填写 model)",
                "pitch": "(填写 pitch)",
                "index_rate": "(填写 index_rate)",
                "infer_host": "(填写 infer_host)",
                "infer_path": "(填写 infer_path)",
                "custom": {
                    "notes": "(按需填写 RVC Provider 扩展字段)",
                },
            },
        )
        return ServiceSettingsGroup(
            enabled=True,
            default_provider_id=provider.provider_id,
            providers=[provider],
        )

    @classmethod
    def build_default_settings(cls) -> AppSettings:
        return AppSettings(
            schema_version="settings.v0.2",
            profiles=[
                RuntimeProfile(
                    profile_id="default",
                    display_name="默认配置",
                    llm=cls._build_llm_group(),
                    tts=cls._build_tts_group(),
                    stt=cls._build_stt_group(),
                    rvc=cls._build_rvc_group(),
                )
            ],
        ).ensure_minimum()

    @classmethod
    def ensure_settings_dir(cls) -> Path:
        settings_dir = cls.get_settings_dir()
        settings_dir.mkdir(parents=True, exist_ok=True)
        return settings_dir

    @classmethod
    def read_settings_file(cls, settings_path: Path) -> AppSettings:
        if not settings_path.exists():
            return cls.build_default_settings()

        try:
            with settings_path.open("r", encoding="utf-8") as file:
                raw_data = json.load(file)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return cls.build_default_settings()

        if not isinstance(raw_data, dict):
            return cls.build_default_settings()

        return AppSettings.from_dict(raw_data)

    @staticmethod
    def write_settings_file(settings_path: Path, settings: AppSettings) -> None:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = settings.ensure_minimum().to_dict()
        with settings_path.open("w", encoding="utf-8") as file:
            json.dump(serialized, file, ensure_ascii=False, indent=2)
