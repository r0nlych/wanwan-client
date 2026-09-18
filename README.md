# wanwan-client

Windows-first 的桌宠式语音助手 MVP。当前正式桌面前端使用 C# WPF，Python 负责配置、Provider、LLM、STT、TTS、会话存储和语音链路编排；后续再考虑 Android 客户端。

## 当前进度

- WPF 透明桌宠主窗口，支持收起/展开、拖动和右键菜单
- 7 套角色状态图：空闲、聆听、思考、说话开/闭嘴、成功、错误
- 文本输入：Enter 发送、Shift+Enter 换行、2000 字限制
- 文本链路：WPF → Python → LLM → TTS → WPF 播放
- 语音入口：点击麦克风即可开始录音，再次点击停止并发送
- 状态展示：空闲、聆听、处理、播放、完成、错误
- 本地会话历史：文本和语音统一保存为 JSONL，桌面端可查看最近 50 条
- 连续文本对话：显式授权后，向当前 LLM 携带同一 session 最近最多 6 轮
- 错误展示与恢复：普通链路错误只在桌宠气泡内展示，支持「我知道了」「重试」「打开设置」「重试播放」

当前不包含实时双工语音、流式 RVC、回声消除、云端会话同步和 Android UI。

## 目录

```text
src/WanwanDesktop/                 C# WPF 桌面端
src/wanwan_client/core/            平台无关 Pipeline 与 Runtime
src/wanwan_client/services/        LLM / STT / TTS / 存储适配
src/wanwan_client/infrastructure/  配置、日志与基础设施
data/config/                       本地运行配置
data/conversations/                本地会话记录（已被 Git 忽略）
tests/                             Python 自动化测试
```

## 本地运行

要求：Windows、.NET 10 SDK、Python 3.10+。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item data\config\app_settings.example.json data\config\app_settings.json
dotnet run --project src\WanwanDesktop\WanwanDesktop.csproj
```

API Key 可以填写到本地设置页，也可以从 `.env.example` 复制为 `.env` 后配置。`.env`、运行配置、日志、会话、录音和 TTS 文件均不会提交到 Git。

## 一键启动（Windows）

以上依赖装好之后，日常启动只需双击：

```bat
scripts\dev_start.bat
```

脚本按三步执行：

1. 用 `.venv\Scripts\python.exe` 运行 `scripts\check_env.py` 做环境自检（项目结构、配置文件、虚拟环境、运行目录可写性）
2. 检查 `dotnet` 命令是否可用
3. 自检通过后执行 `dotnet run --project src\WanwanDesktop\WanwanDesktop.csproj` 启动 WPF 桌宠，退出后显示退出码

自检输出区分 `[错误]` 和 `[警告]`：出现 `[错误]` 时脚本不启动桌宠，保留窗口显示处理办法并返回非零退出码；`[警告]` 不影响启动。

脚本只做检查：不联网、不安装依赖、不自动创建或覆盖 `data\config\app_settings.json`、不修改系统环境。也可以单独运行自检：

```powershell
.\.venv\Scripts\python.exe scripts\check_env.py
```

## 桌面交互

- 点击猫咪或底部“输入”按钮：展开文本面板
- 点击麦克风：开始录音；再次点击：停止并发送
- 播放过程中点击麦克风：停止播放
- 右键菜单：设置、日志、历史相关入口和退出
- “启用连续对话（最近 6 轮）”：确认隐私提示后启用
- “新建文本会话”：生成新 session，后续消息不再读取旧 session 上下文

连续对话默认关闭。启用后只读取当前 session 中成功、完整的文本轮次；最多 6 轮、12000 字符。其他 session、失败记录、语音记录和非法角色不会发送给 LLM。设置窗口关闭后会自动撤销本次授权。

## 错误展示与恢复

- 录音、文本、音频和播放等普通链路错误统一显示在桌宠气泡中，不再弹出阻塞式对话框；只有启动失败等致命错误仍使用模态对话框。
- 气泡正文只显示面向用户的友好文案，悬停可查看 `step`、`error_code` 等定位信息；原始技术信息写入桌面日志（`logs/wanwan_desktop.log`，敏感字段按字段名脱敏）。
- 「我知道了」：只关闭错误提示并回到空闲，不调用后端。
- 「重试」：复用原有文本发送链路，重试最后一次提交失败的原文。
- 「打开设置」：复用现有设置窗口，用于配置类和鉴权类错误。
- 「重试播放」：只重放上一次通过校验的本地 WAV，不重新调用 LLM / TTS。
- 开始新一轮录音、文本发送或音频任务时，上一轮的错误按钮立即失效，避免过期操作被误触发。

## 验证

```powershell
python -m pytest -q -p no:cacheprovider
dotnet build src\WanwanDesktop\WanwanDesktop.csproj --no-restore
```

当前回归基线：Python 58 项测试通过，WPF 构建 0 警告、0 错误。

## 接口约定

内部链路继续遵守 `docs/internal-api-spec.md`、`docs/internal-api-payloads.md` 和 `docs/internal-api-compat.md`。资源引用使用 `audio_ref`，阶段状态支持 `success`、`failed`、`skipped` 等 v0.3 状态。
