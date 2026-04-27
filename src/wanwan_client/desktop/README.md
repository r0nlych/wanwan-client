# desktop 模块说明

## 当前状态

旧 tkinter 前端（pet_window.py、debug_window.py 等）已废弃并删除。
正式前端迁移至 C# WPF（见 `src/WanwanDesktop/`）。

## 当前保留模块

- `controllers/` — `VoiceChainController`，Python 后端语音链路调度入口，供 CLI 和 C# Process 调用
- `playback/` — `LocalAudioPlayer`，本地 WAV 播放能力，`VoiceAudioPipeline` 硬依赖
- `app/` — 空包（旧 tkinter 窗口已删除）
- `input/` — 空包（旧录音模块已删除，C# 接管）
- `settings/` — 空包（旧设置页已删除，C# 接管）

## C# WPF 前端

新前端位于 `src/WanwanDesktop/`，通过 Process 调用 Python CLI 执行语音链路。
