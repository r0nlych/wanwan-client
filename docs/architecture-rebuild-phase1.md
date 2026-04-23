# wanwan-client 重建阶段 1 说明

## 1. 目标

本阶段只处理结构层问题，不进入业务实现。

目标：

1. 冻结旧 Web 壳和旧占位实现
2. 建立新的最小项目骨架
3. 让仓库进入“新方向可继续开发、旧方向不再扩展”的状态

## 2. 当前方向

- 当前目标：Windows 桌宠式语音助手 MVP
- 当前优先链路：设置接入 > 文本链路跑通 > TTS > 语音输出 > 录音 > STT 回填 > 会话保存
- `desktop`：本地桌宠 UI / 输入输出交互
- `services`：多 provider、多模型、能力可配置
- `rvc`：保留能力位，但当前不是阻塞项

## 3. 阶段 1 处理原则

- 不删除旧代码
- 不迁移旧实现逻辑
- 不直接写业务功能
- 不扩展复杂聊天客户端能力
- 只做冻结标记、目录职责收口、最小骨架落地

## 4. 冻结范围

### 4.1 旧 Web 壳

- `src/wanwan_client/desktop/app.py`
- `src/wanwan_client/desktop/routes/`
- `src/wanwan_client/desktop/templates/`
- `src/wanwan_client/desktop/static/`

说明：
- 这些文件和目录属于旧 Flask + 网页聊天页方向
- 当前只保留为历史参考
- 后续默认不继续扩展

### 4.2 旧占位实现

- `src/wanwan_client/core/chat/chat_manager.py`
- `src/wanwan_client/core/audio/audio_pipeline.py`
- `src/wanwan_client/core/session/session_manager.py`
- `src/wanwan_client/core/character/character_manager.py`
- `src/wanwan_client/core/config/config_manager.py`
- `src/wanwan_client/services/storage/conversation_store.py`
- `src/wanwan_client/services/tts/alltalk_client.py`
- `src/wanwan_client/services/rvc/rvc_client.py`

说明：
- 这些文件目前不代表稳定实现
- 当前阶段只保留入口，不在其上继续扩展

## 5. 新最小骨架

本阶段新增以下目录骨架：

- `src/wanwan_client/core/app/`
- `src/wanwan_client/core/pipeline/`
- `src/wanwan_client/services/llm/providers/`
- `src/wanwan_client/services/tts/providers/`
- `src/wanwan_client/services/stt/providers/`
- `src/wanwan_client/services/rvc/providers/`
- `src/wanwan_client/infrastructure/resources/`
- `src/wanwan_client/desktop/app/`
- `src/wanwan_client/desktop/pet/`
- `src/wanwan_client/desktop/input/`
- `src/wanwan_client/desktop/playback/`
- `src/wanwan_client/desktop/settings/`

## 6. 后续阶段建议

阶段 2 最适合先进入：

1. 设置接入骨架
2. 多 provider 配置模型
3. 文本链路最小编排入口

在此之前，不建议先回头扩旧 Web 页面或旧浏览器上传接口。

