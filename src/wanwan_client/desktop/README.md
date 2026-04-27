# desktop 模块说明

当前 `desktop` 目录只承载 Windows 本地客户端方向的代码。

## 当前定位

- `desktop` 用于本地桌宠 UI、输入输出交互和桌面端编排
- 项目不再承载 Web 应用、HTTP API 或旧网页聊天入口
- 语音链路通过本地 UI / `VoiceChainController` 调用，不通过网页路由

## 当前目录策略

- `app/`：桌面应用入口骨架
- `controllers/`：桌面端内部调用入口
- `pet/`：桌宠外观与状态骨架
- `input/`：文本输入、录音入口骨架
- `playback/`：本地播放控制
- `settings/`：本地设置入口骨架

## 清理说明

旧 Web 残留目录 `routes/`、`templates/`、`static/` 已移除。
后续桌面端继续走本地 UI + controller 方向。
