"""
Doubao STT 结果归一化测试：

- result 存在但 text 为空（没有识别到语音）→ STT_NO_SPEECH
- result 对象缺失（协议结构错误）→ 仍为 STT_SCHEMA_MISMATCH
- 正常文本 → 正常解析

只调用本地 _normalize_result，不访问网络。
"""

from __future__ import annotations

import pytest

from src.wanwan_client.services.stt.providers.base import (
    SttProviderError,
    SttProviderRequest,
)
from src.wanwan_client.services.stt.providers.doubao_stt import DoubaoFlashSttProvider
from src.wanwan_client.shared.schemas import ProviderConfig, ProviderModelConfig


def _build_request() -> SttProviderRequest:
    return SttProviderRequest(
        trace_id="trace_test",
        session_id="session_test",
        provider_config=ProviderConfig(),
        model_config=ProviderModelConfig(),
        audio_ref={"type": "local_path", "value": "sample.wav"},
    )


def test_empty_text_is_no_speech_error() -> None:
    provider = DoubaoFlashSttProvider()

    with pytest.raises(SttProviderError) as exc_info:
        provider._normalize_result(
            request=_build_request(),
            request_mode="sync_base64",
            provider_job_id=None,
            request_id="req-1",
            # 豆包对静音音频的真实返回形态：result 在但没有 text
            response_json={"result": {}},
        )

    error = exc_info.value
    assert error.code == "STT_NO_SPEECH"
    assert error.error_type == "no_speech"
    assert error.retryable is False


def test_missing_result_object_remains_schema_mismatch() -> None:
    provider = DoubaoFlashSttProvider()

    with pytest.raises(SttProviderError) as exc_info:
        provider._normalize_result(
            request=_build_request(),
            request_mode="sync_base64",
            provider_job_id=None,
            request_id="req-2",
            response_json={"code": "20000000"},
        )

    error = exc_info.value
    assert error.code == "STT_SCHEMA_MISMATCH"
    assert error.retryable is False


def test_recognized_text_is_normalized() -> None:
    provider = DoubaoFlashSttProvider()

    result = provider._normalize_result(
        request=_build_request(),
        request_mode="sync_base64",
        provider_job_id=None,
        request_id="req-3",
        response_json={
            "result": {
                "text": "哈喽，可以听到吗？",
                "utterances": [],
            },
            "audio_info": {"duration": 1200},
        },
    )

    assert result.text == "哈喽，可以听到吗？"
    assert result.is_final is True
    assert result.request_id == "req-3"
