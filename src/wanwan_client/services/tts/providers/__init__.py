"""
TTS provider exports.
"""

from src.wanwan_client.services.tts.providers.doubao_tts import DoubaoTtsProvider
from src.wanwan_client.services.tts.providers.openai_compatible_tts import OpenAICompatibleTtsProvider
from src.wanwan_client.services.tts.providers.registry import TtsProviderRegistry

__all__ = [
    "DoubaoTtsProvider",
    "OpenAICompatibleTtsProvider",
    "TtsProviderRegistry",
]
