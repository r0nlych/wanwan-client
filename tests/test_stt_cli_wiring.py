"""
run-stt-audio 入口 wiring 测试：

走 main() 的真实命令分发路径（不直接调 SttService），
验证解析出的 --provider-id / --model-id 确实被转发到
SttService.transcribe()；未传时保持 None，交给 RuntimeConfig 选择。

RuntimeApp 与 SttService 均被替换为假实现：
不读配置文件、不访问网络、不消耗任何 API Key。
"""

from __future__ import annotations

import sys

import pytest

import src.wanwan_client.main as main_module


class FakeState:
    """最小 state：main() 只用到 state.runtime_config。"""

    def __init__(self) -> None:
        self.runtime_config = object()


class FakeApp:
    """替换 RuntimeApp，避免读取本地配置文件。"""

    def load_state(self) -> FakeState:
        return FakeState()


class RecordingSttService:
    """记录 transcribe 收到的全部参数，并返回成功结果。"""

    def __init__(self, runtime_config: object) -> None:
        self.runtime_config = runtime_config

    def transcribe(self, **kwargs: object) -> dict[str, str]:
        RecordingSttService.last_kwargs = kwargs
        return {"status": "success"}


@pytest.fixture
def patched_entry(monkeypatch: pytest.MonkeyPatch):
    """替换 main() 中真实的 App 与 STT 服务，记录转发参数。"""
    RecordingSttService.last_kwargs = None
    monkeypatch.setattr(main_module, "RuntimeApp", lambda: FakeApp())
    monkeypatch.setattr(main_module, "SttService", RecordingSttService)
    return RecordingSttService


def _run_cli(monkeypatch: pytest.MonkeyPatch, *extra_args: str) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["wanwan-client", "run-stt-audio", "sample.wav", *extra_args],
    )
    main_module.main()


def test_stt_cli_forwards_explicit_provider_and_model(
    monkeypatch: pytest.MonkeyPatch,
    patched_entry: type[RecordingSttService],
) -> None:
    _run_cli(
        monkeypatch,
        "--provider-id", "stt_primary",
        "--model-id", "stt_model_x",
    )

    kwargs = patched_entry.last_kwargs
    assert kwargs is not None
    # 显式参数必须原样到达 SttService.transcribe()
    assert kwargs["provider_id"] == "stt_primary"
    assert kwargs["model_id"] == "stt_model_x"
    # 其余转发参数保持既有结构
    assert kwargs["audio_ref"]["type"] == "local_path"
    assert str(kwargs["audio_ref"]["value"]).endswith("sample.wav")


def test_stt_cli_keeps_none_when_provider_and_model_omitted(
    monkeypatch: pytest.MonkeyPatch,
    patched_entry: type[RecordingSttService],
) -> None:
    _run_cli(monkeypatch)

    kwargs = patched_entry.last_kwargs
    assert kwargs is not None
    # 未传参数时必须是 None，由 RuntimeConfig 的默认选择逻辑决定 Provider/模型
    assert kwargs["provider_id"] is None
    assert kwargs["model_id"] is None


def test_stt_cli_forwards_optional_overrides_alongside_provider(
    monkeypatch: pytest.MonkeyPatch,
    patched_entry: type[RecordingSttService],
) -> None:
    _run_cli(
        monkeypatch,
        "--provider-id", "stt_primary",
        "--audio-format", "wav",
        "--request-mode", "sync_url",
    )

    kwargs = patched_entry.last_kwargs
    assert kwargs is not None
    assert kwargs["provider_id"] == "stt_primary"
    # 未传 --model-id 仍然是 None
    assert kwargs["model_id"] is None
    assert kwargs["audio_format"] == "wav"
    assert kwargs["request_mode"] == "sync_url"
