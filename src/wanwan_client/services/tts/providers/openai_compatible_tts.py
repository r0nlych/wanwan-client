"""
OpenAI-compatible TTS provider 适配器。
"""

from __future__ import annotations

from typing import Any

from src.wanwan_client.infrastructure.http.openai_compatible_client import (
    OpenAICompatibleHttpClient,
)
from src.wanwan_client.services.tts.providers.base import (
    TtsProviderRequest,
    TtsProviderResult,
)
class OpenAICompatibleTtsProvider:
    """
    最小真实可跑 TTS 适配器。
    """

    ADAPTER_VERSION = "phase6.tts.openai_compatible.v1"

    def synthesize_to_file(self, request: TtsProviderRequest) -> TtsProviderResult:
        text = request.text
        provider_config = request.provider_config
        model_config = request.model_config
        output_path = request.output_path
        client = OpenAICompatibleHttpClient(provider_config)
        voice = str(model_config.extra.get("voice", provider_config.extra.get("voice", "alloy")))
        response_format = str(
            model_config.extra.get("response_format", provider_config.extra.get("response_format", "wav"))
        )
        payload: dict[str, Any] = {
            "model": model_config.model_id,
            "input": text,
            "voice": voice,
            "response_format": response_format,
        }

        speed = model_config.extra.get("speed")
        if speed is not None:
            payload["speed"] = speed

        instructions = model_config.extra.get("instructions")
        if instructions:
            payload["instructions"] = instructions

        response = client.post_json(payload, accept="application/octet-stream")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)

        return TtsProviderResult(
            audio_ref={
                "type": "local_path",
                "value": str(output_path).replace("\\", "/"),
                "mime_type": self._guess_mime_type(response_format),
            },
            voice=voice,
            voice_type=voice,
            response_format=response_format,
            request_id=response.headers.get("x-request-id"),
            byte_size=output_path.stat().st_size,
        )

    def _guess_mime_type(self, response_format: str) -> str:
        mapping = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "aac": "audio/aac",
            "flac": "audio/flac",
            "pcm": "audio/pcm",
        }
        return mapping.get(response_format, "application/octet-stream")
