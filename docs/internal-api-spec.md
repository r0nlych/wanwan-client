# wanwan-client 内部接口规范 v0.3

## 1. 目标

本规范用于约束 wanwan-client 内部各阶段之间的统一数据传输格式。

适用范围：
- `record_upload`
- `stt`
- `llm`
- `tts`
- `rvc`
- `playback`
- 后续新增阶段

本规范是**内部统一协议**，不是外部厂商原生 API 协议。  
外部服务提供方（OpenAI-compatible、DeepSeek、Gemini、本地服务、第三方 TTS/STT/RVC 等）的差异，必须在 `services/provider` 适配层完成转换，不得直接污染内部协议。

设计目标：
- 长期可用
- 稳定健壮
- 可扩展
- 兼容多 provider、多模型、多能力
- 支持文本、音频、文件、URL、对象引用等多种数据形态
- 支持同步、异步、流式、部分完成、跳过、取消、降级
- 上游服务数据格式变化时，可通过适配层局部修正，不破坏主链路协议

---

## 2. 外层统一结构

所有内部阶段输入输出对象统一使用以下外层字段：

- `trace_id`
- `session_id`
- `step`
- `status`
- `timestamp`
- `payload`
- `error`
- `meta`

示例：

```json
{
  "trace_id": "trace_20260421_001",
  "session_id": "session_abc123",
  "step": "llm",
  "status": "success",
  "timestamp": "2026-04-21T22:00:00+08:00",
  "payload": {},
  "error": null,
  "meta": {}
}
```

规则：
1. 外层字段名固定，不得擅自新增平级替代字段
2. 业务内容优先进入 `payload`
3. 上下文、来源、调试、兼容、耗时等进入 `meta`
4. 错误信息进入 `error`
5. 不得把 provider 原始响应直接当作内部阶段对象返回

---

## 3. 外层字段定义

### 3.1 trace_id
- 类型：`string`
- 说明：一次完整主链路的全局追踪 ID
- 要求：同一次链路内所有阶段必须一致

### 3.2 session_id
- 类型：`string`
- 说明：当前会话 ID
- 要求：同一会话内可复用，不同会话应变化

### 3.3 step
- 类型：`string`
- 说明：当前阶段名
- 建议值：
  - `record_upload`
  - `stt`
  - `llm`
  - `tts`
  - `rvc`
  - `playback`

### 3.4 status
- 类型：`string`
- 允许值：
  - `success`
  - `failed`
  - `running`
  - `partial`
  - `skipped`
  - `cancelled`
  - `degraded`

说明：
- `success`：阶段成功完成
- `failed`：阶段失败
- `running`：阶段执行中
- `partial`：阶段部分完成，有可用结果但不完整
- `skipped`：阶段被跳过
- `cancelled`：阶段被取消
- `degraded`：阶段降级完成

### 3.5 timestamp
- 类型：`string`
- 格式：ISO 8601
- 示例：`2026-04-21T22:00:00+08:00`

### 3.6 payload
- 类型：`object`
- 说明：当前阶段的业务输入输出主体
- 详细规则见 `internal-api-payloads.md`

### 3.7 error
- 类型：`object | null`
- 说明：失败、部分失败、降级时的错误信息
- 成功时应为 `null`

### 3.8 meta
- 类型：`object`
- 说明：阶段上下文、服务来源、模型信息、能力信息、兼容信息、耗时与调试信息

---

## 4. meta 最小要求

不同阶段允许扩展 `meta`，但以下字段建议统一支持：

- `provider`：实际调用的服务提供方
- `model`：实际调用的模型名或模型 ID
- `capabilities`：能力标签数组
- `content_type`：核心内容类型
- `protocol_version`：内部协议版本
- `adapter_version`：适配层版本
- `duration_ms`：阶段耗时
- `retry_count`：重试次数
- `request_id`：外部服务请求 ID（如有）
- `degraded_from`：降级来源阶段或原始方案
- `notes`：补充说明

建议：
- `stt / llm / tts / rvc` 默认带 `provider`
- `llm / stt / tts / rvc` 有模型概念时默认带 `model`
- `capabilities` 建议使用：
  - `chat`
  - `vision`
  - `reasoning`
  - `tools`
  - `audio_in`
  - `audio_out`
  - `voice_convert`

---

## 5. error 统一结构

`error` 统一使用以下结构：

```json
{
  "code": "TTS_TIMEOUT",
  "message": "TTS service request timed out",
  "type": "provider_timeout",
  "retryable": true,
  "details": {},
  "raw_ref": null
}
```

字段说明：
- `code`：内部错误码，必须稳定
- `message`：面向开发排障的错误描述
- `type`：错误分类
- `retryable`：是否可重试
- `details`：结构化补充信息
- `raw_ref`：原始错误引用，避免直接塞大段原文

### 5.1 type 建议值
- `validation_error`
- `provider_error`
- `provider_timeout`
- `provider_unavailable`
- `schema_mismatch`
- `compat_error`
- `file_error`
- `network_error`
- `cancelled`
- `unknown_error`

### 5.2 错误处理规则
1. 上游原始错误不得直接污染外层结构
2. 外部错误先归一化，再写入 `error`
3. 大段原始响应、HTML、二进制、traceback 不直接塞入 `message`
4. 原始响应可通过 `raw_ref` 指向日志或临时文件引用
5. `partial / degraded` 状态下允许同时存在 `payload` 与 `error`

---

## 6. 通用兼容规则

### 6.1 适配层原则
- 所有外部 API 响应都必须先进入 provider 适配层
- 适配层负责：
  - 字段映射
  - 结构校验
  - 类型归一化
  - 默认值补齐
  - 兼容旧格式/新格式
- 主链路模块不直接消费第三方原始响应

### 6.2 未知字段原则
- 上游新增字段时，默认不报错
- 未映射字段可暂存入 `meta.notes` 或 `error.details`
- 不因为上游多字段而破坏内部协议

### 6.3 缺失字段原则
- 必填字段缺失时，返回 `failed` 或 `partial`
- 不得静默吞掉关键字段缺失
- 必须通过 `error.type = schema_mismatch` 或 `compat_error` 显式标记

### 6.4 类型漂移原则
例如字符串变数组、对象变字符串、路径变 URL：
- 必须在适配层归一
- 无法归一时返回结构化错误
- 不允许主链路内到处写临时兼容分支

### 6.5 版本演进原则
- 当前协议版本：`v0.3`
- 后续新增字段优先向后兼容
- 非必要不修改外层 8 个字段
- 破坏性变更必须提升协议版本号并保留迁移说明

---

## 7. 资源引用原则

长期协议不得只依赖“本地文件路径”表达资源。  
所有阶段应优先支持**资源引用**思维。

建议统一使用以下 ref 概念：
- `audio_ref`
- `text_ref`
- `file_ref`
- `image_ref`
- `video_ref`

一个 ref 可承载：
- 本地相对路径
- 远程 URL
- 缓存键
- 对象 ID
- base64 描述对象
- 临时资源句柄

推荐结构：

```json
{
  "type": "local_path",
  "value": "data/tts/out_001.wav",
  "mime_type": "audio/wav"
}
```

`type` 建议值：
- `local_path`
- `remote_url`
- `cache_key`
- `object_id`
- `base64_inline`

---

## 8. 通用成功/失败判定

### 成功
- `status = success`
- `error = null`
- `payload.output` 中存在本阶段最小可用结果

### 失败
- `status = failed`
- `error != null`
- `payload.output` 可为空

### 部分完成
- `status = partial`
- `payload.output` 有部分结果
- `error != null`

### 降级完成
- `status = degraded`
- 已产出替代方案结果
- `meta.degraded_from` 应说明原始方案
- `error` 应说明为何降级

### 跳过
- `status = skipped`
- 本阶段未执行，但属于合法链路分支
- 例如未启用 RVC 时跳过 `rvc`

---

## 9. 最小可用结果要求

每个阶段成功时，`payload.output` 必须至少包含一个最小可用结果：

- `record_upload`：可用音频引用或上传结果
- `stt`：可用文本
- `llm`：可用回复文本或回复消息
- `tts`：可用语音引用
- `rvc`：可用转换后语音引用
- `playback`：可播放引用或播放结果

具体定义见 `internal-api-payloads.md`

---

## 10. 文档关系

- 本文件：总规范、外层结构、状态、meta、error、兼容规则
- `internal-api-payloads.md`：各阶段 payload 结构定义
- `internal-api-compat.md`：兼容策略、异常处理、演进规则补充

---

## 11. 当前版本建议

当前 Windows MVP 开发可先使用同步实现，但数据结构应按本规范保留：
- `running / partial / degraded / skipped / cancelled`
- 资源引用
- provider 适配层
- 多模型、多 provider 兼容

即使当前实现未完全用到，也不得在协议层删掉这些能力入口。
