"""
主链路编排骨架。

阶段 1 只建立目录落点，后续用于承接文本链路、TTS、播放、录音、STT 回填等流程编排。
"""

from src.wanwan_client.core.pipeline.text_audio_pipeline import TextAudioPipeline
from src.wanwan_client.core.pipeline.voice_audio_pipeline import VoiceAudioPipeline

__all__ = [
    "TextAudioPipeline",
    "VoiceAudioPipeline",
]
