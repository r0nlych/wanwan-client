# wanwan-client 重建阶段 2 说明

## 1. 目标

本阶段只处理配置相关骨架，不进入真实 provider 接入，不进入文本链路业务实现。

目标：

1. 落设置相关的最小骨架
2. 落运行时生效配置的最小骨架
3. 落 provider 配置模型的最小骨架
4. 明确这些模块分别放在哪些目录和文件里

## 2. 目录职责

### 2.1 `shared/schemas`

负责放结构化配置模型：

- `provider_config.py`
- `app_settings.py`

说明：
- 这里定义“设置长什么样”
- 不负责真实读写
- 不负责运行时装配

### 2.2 `infrastructure/settings`

负责放设置持久化入口：

- `settings_loader.py`
- `settings_repository.py`

说明：
- 这里定义“设置从哪里来、往哪里去”
- 当前阶段只保留文件路径和仓库边界
- 不接真实磁盘实现

### 2.3 `core/config`

负责放运行时生效配置装配：

- `config_manager.py`
- `runtime_config.py`

说明：
- 这里定义“哪些设置在当前运行中生效”
- 把持久化设置对象转换成主链路可消费对象
- 不写 provider 真实调用逻辑

### 2.4 `services/*/providers`

负责 provider 适配层落点：

- `services/llm/providers/`
- `services/tts/providers/`
- `services/stt/providers/`
- `services/rvc/providers/`

说明：
- 当前阶段只保留 README 和目录骨架
- 后续真实实现必须从统一配置对象读取 provider / model / endpoint

## 3. 当前最小模型范围

本阶段最小配置模型包含：

- 应用设置根对象
- 运行时配置档
- 桌宠最小交互设置
- provider 配置
- provider endpoint 配置
- provider model 配置

## 4. 当前不做

- 不接真实 JSON 文件读写
- 不接真实 provider
- 不进入文本链路、TTS、STT 业务实现
- 不扩成复杂设置页
- 不进入角色卡复杂设计

## 5. 后续阶段建议

阶段 3 最适合先进入：

1. 设置保存与加载的真实落地
2. 运行时 profile 选择收口
3. 文本链路最小编排入口

