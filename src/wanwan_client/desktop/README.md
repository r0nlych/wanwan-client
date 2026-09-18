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

新前端位于 `src/WanwanDesktop/`，通过 Process 调用 Python CLI 执行文本和语音链路。

### 已接入能力

- `MainWindow`：透明桌宠、文本输入、录音、播放、状态切换和右键菜单
- `PythonBackendService`：使用 `ProcessStartInfo.ArgumentList` 安全传递中文、多行文本和 session ID
- `AudioRecorderService`：WPF 侧录音与取消
- `AudioPlayerService`：WPF 侧 WAV 播放、音量和停止
- `ConversationHistoryService`：只读加载 `data/conversations/*.jsonl` 最近 50 条
- `HistoryWindow`：展示文本/语音历史，不修改原始 JSONL
- `MainWindow` 错误恢复：普通链路错误只在气泡内展示，提供「我知道了」「重试」「打开设置」「重试播放」

### 文本链路

```text
WPF MessageInput
  → PythonBackendService
  → run-text-audio --no-play
  → TextAudioPipeline
  → LLM → TTS
  → reply_text + audio_ref
  → WPF 气泡与 WAV 播放
```

Python 使用 `--no-play` 时仍返回 `playback: skipped` 和有效 `audio_ref`，由 WPF 统一控制播放状态、停止按钮和音量。未指定该参数的旧 CLI 调用继续由 Python 播放。

### 会话与连续上下文

- 文本和语音结果统一追加到 `data/conversations/{YYYY-MM-DD}.jsonl`
- WPF 启动时创建新的文本 `session_id`
- 连续对话默认关闭，必须在右键菜单明确确认后启用
- 仅加载同一 session 的成功文本轮次
- 上限为最近 6 轮、12000 字符
- Pipeline 再次过滤非法角色、孤立消息和不完整轮次
- 新建文本会话会更换 session ID
- 设置窗口关闭后撤销连续上下文授权，避免 Provider 变化后沿用旧授权

当前语音链路不会混入文本连续上下文，这是本阶段的明确边界。

### 桌面端验证

```powershell
dotnet build src\WanwanDesktop\WanwanDesktop.csproj --no-restore
python -m pytest -q -p no:cacheprovider
```

验收时还需人工确认：文本回复显示、WAV 实际出声、播放停止、录音开始/取消/发送、历史窗口和新建会话。
