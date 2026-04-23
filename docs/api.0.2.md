# wanwan\_client 内部接口规范 v0.2

> 更新时间：2026-04-20\
> 文档类型：内部接口规范\
> 适用范围：wanwan\_client 语音链路内部阶段传输、前后端核心接口约定、后端内部模块结果对象

***

# 1. 文档目标

本文档用于统一 wanwan\_client 整体语音链路的接口格式与阶段消息格式。

当前链路为：

**用户发送语音 → 录音上传保存 → STT 语音转文字 → LLM 大模型生成文本回复 → TTS 文字转语音 → RVC 语音变声 → 前端播放输出**

本文档定义以下内容：

1. 请求分哪几类
2. 每类请求的请求格式
3. 每个阶段的请求内容
4. 每个阶段的成功响应格式
5. 每个阶段的失败响应格式
6. 文件保存位置
7. 时间戳与 trace\_id 规范
8. 内部统一格式与外部厂商 API 的关系

***

# 2. 总体设计原则

## 2.1 统一外层格式，payload 按阶段定义

所有阶段统一使用同一套外层字段：

- `trace_id`
- `session_id`
- `step`
- `status`
- `timestamp`
- `payload`
- `error`
- `meta`

说明：

- 外层字段统一且尽量保持稳定
- `payload` 为当前阶段业务数据区
- 不同阶段允许使用不同的 `payload` 内部字段
- 不要求外部厂商原生 API 与本文档一致
- 外部服务差异通过适配层处理

***

## 2.2 全链路统一使用 trace\_id

一次完整语音请求，从录音开始到最终播放结束，全程使用同一个 `trace_id`。

### trace\_id 生成规则

建议格式：

`trace_毫秒时间戳`

示例：

`trace_1713578123456`

### trace\_id 的作用

- 串联整条语音链路
- 标识一次独立请求
- 命名中间文件
- 对齐日志和错误定位

***

## 2.3 session\_id 用于标识会话

`session_id` 用于标识当前聊天会话。

示例：

`session_001`

当前阶段可以先简单实现，后期再升级为真实会话 ID。

***

## 2.4 timestamp 为当前阶段消息生成时间

所有阶段消息都必须带 `timestamp`。

### 规则

- 使用毫秒时间戳
- 由当前阶段生成
- 表示当前阶段结果对象生成时间

### 用途

- 查看调用顺序
- 辅助排查耗时
- 为后续更复杂状态流转预留基础字段

***

# 3. 请求分类

当前内部接口 / 阶段请求分为三类：

## 3.1 第一类：前端上传类请求

由前端发起，请求进入后端。

当前阶段主要包括：

- `record_upload`

特点：

- 通常为 HTTP 请求
- 通常使用 `multipart/form-data`
- 包含浏览器产生的 Blob / File

***

## 3.2 第二类：后端内部处理类请求

由后端内部阶段调用后端内部阶段。

当前阶段主要包括：

- `stt`
- `llm`
- `tts`
- `rvc`

特点：

- 不一定必须是 HTTP
- 可以是函数调用、模块调用、服务调用
- 推荐统一使用本文档定义的阶段消息格式

***

## 3.3 第三类：前端输出类请求 / 返回类请求

由后端向前端提供最终播放资源。

当前阶段主要包括：

- `playback`

特点：

- 负责向前端暴露可播放音频
- 负责生成音频 URL 或资源访问地址

***

# 4. 统一外层消息格式

所有阶段统一采用如下格式：

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "stt",
  "status": "success",
  "timestamp": 1713578124200,
  "payload": {},
  "error": null,
  "meta": {}
}
```

***

# 5. 外层字段定义

## 5.1 trace\_id

### 含义

全链路唯一标识。

### 必填

是

### 示例

```json
"trace_id": "trace_1713578123456"
```

***

## 5.2 session\_id

### 含义

当前会话标识。

### 必填

是

### 示例

```json
"session_id": "session_001"
```

***

## 5.3 step

### 含义

当前阶段名称。

### 必填

是

### 固定枚举

- `record_upload`
- `stt`
- `llm`
- `tts`
- `rvc`
- `playback`

### 示例

```json
"step": "tts"
```

***

## 5.4 status

### 含义

当前阶段执行状态。

### 必填

是

### 固定枚举

- `success`
- `failed`

### 示例

```json
"status": "success"
```

***

## 5.5 timestamp

### 含义

当前阶段结果生成时间。

### 必填

是

### 格式

毫秒时间戳

### 示例

```json
"timestamp": 1713578125600
```

***

## 5.6 payload

### 含义

当前阶段核心业务数据。

### 必填

是

### 规则

- 成功时必须返回业务数据对象
- 失败时通常返回空对象 `{}`

***

## 5.7 error

### 含义

错误对象。

### 必填

是

### 规则

- 成功时：`null`
- 失败时：必须为错误对象

### 统一错误对象格式

```json
{
  "code": "ERROR_CODE",
  "message": "错误说明"
}
```

***

## 5.8 meta

### 含义

附加信息对象。

### 必填

是

### 可包含内容

- provider
- model
- voice
- format
- source
- duration\_ms
- debug 信息

### 规则

没有附加信息时返回 `{}`

***

# 6. 统一响应格式

## 6.1 成功响应格式

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "阶段名",
  "status": "success",
  "timestamp": 1713578123456,
  "payload": {
    "具体业务数据": "..."
  },
  "error": null,
  "meta": {
    "附加信息": "..."
  }
}
```

***

## 6.2 失败响应格式

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "阶段名",
  "status": "failed",
  "timestamp": 1713578123456,
  "payload": {},
  "error": {
    "code": "ERROR_CODE",
    "message": "错误说明"
  },
  "meta": {}
}
```

***

# 7. 文件保存规范

所有中间文件统一按 `trace_id` 命名。

## 7.1 录音原始文件保存位置

目录：

`data/temp/`

文件名：

`{trace_id}.webm`

示例：

`data/temp/trace_1713578123456.webm`

***

## 7.2 TTS 输出文件保存位置

目录：

`data/tts/`

文件名：

`{trace_id}.wav`

示例：

`data/tts/trace_1713578123456.wav`

***

## 7.3 RVC 输出文件保存位置

目录：

`data/rvc/`

文件名：

`{trace_id}.wav`

示例：

`data/rvc/trace_1713578123456.wav`

***

## 7.4 目录要求

如果目录不存在，后端必须自动创建。

***

## 7.5 文件清理策略

为避免临时文件占用过多磁盘空间，建议实现以下清理机制：

- **清理触发方式**：定时任务（如每24小时）或启动时检查
- **清理目标**：`data/temp/` 目录中超过24小时的文件
- **保留策略**：最近24小时内的文件不清理，确保正在处理的请求不受影响
- **实现建议**：使用文件的修改时间（mtime）作为判断依据

<!-- 更改日期：2026-04-20 -->

***

# 8. 阶段接口规范总表

| 阶段     | step            | 请求类型            | 输入核心内容                                | 成功输出核心内容                     | 文件输出                        |
| ------ | --------------- | --------------- | ------------------------------------- | ---------------------------- | --------------------------- |
| 录音上传保存 | `record_upload` | 前端上传类请求         | `audio` Blob、`trace_id`、`session_id`  | `audio_path`、`format`        | `data/temp/{trace_id}.webm` |
| 语音转文字  | `stt`           | 后端内部处理类请求       | `input_audio_path`                    | `text`、`language`            | 无                           |
| 大模型回复  | `llm`           | 后端内部处理类请求       | `user_text`、`history`、`system_prompt` | `reply_text`                 | 无                           |
| 文字转语音  | `tts`           | 后端内部处理类请求       | `input_text`                          | `output_audio_path`、`format` | `data/tts/{trace_id}.wav`   |
| 语音变声   | `rvc`           | 后端内部处理类请求       | `input_audio_path`                    | `output_audio_path`、`format` | `data/rvc/{trace_id}.wav`   |
| 播放输出   | `playback`      | 前端输出类请求 / 返回类请求 | `final_audio_path`                    | `audio_url`                  | 无                           |

***

# 9. 外部厂商适配原则

本文档是**内部统一接口规范**，不是外部厂商原生 API 规范。

说明：

- OpenAI、千问、DeepSeek、CosyVoice、Whisper、RVC 等外部服务原生参数格式可能不同
- 不要求外部服务直接兼容本文档
- 调用外部服务前，应由适配层将内部统一格式转换为对应厂商格式
- 外部服务返回结果后，应转换回本文档定义的统一格式

***

# 10. 当前版本范围

## 10.1 当前版本重点

- 统一外层字段
- 统一响应格式
- 统一错误对象格式
- 统一 trace\_id 与文件命名规则
- 统一各阶段输入输出核心结构

## 10.2 当前版本不处理的内容

- 完整状态机
- 任务队列
- 重试与取消机制
- 并发任务调度
- 数据库存储式链路编排

***

# 11. 版本说明

## v0.2

当前版本定位：

- 优先服务当前项目落地
- 先把主链路结构定下来
- 保证“能跑、能查、能扩展”
- 先不做过重设计

***

# 附录：阶段接口明细

# wanwan\_client 内部接口规范：阶段明细 v0.2

> 更新时间：2026-04-20\
> 文档类型：阶段接口明细\
> 关联文档：`wanwan_client_internal_api_spec.md`

***

# 1. record\_upload 阶段

## 1.1 阶段作用

接收前端录音 Blob，保存为后端临时音频文件。

## 1.2 请求类型

前端上传类请求

## 1.3 HTTP 接口定义

- 请求方法：`POST`
- 请求路径：`/api/record`
- Content-Type：`multipart/form-data`

## 1.4 请求字段

| 字段名         | 类型          | 必填 | 说明                     |
| ----------- | ----------- | -: | ---------------------- |
| audio       | File / Blob |  是 | 浏览器录音文件，字段名固定为 `audio` |
| trace\_id   | string      |  是 | 全链路唯一标识                |
| session\_id | string      |  是 | 当前会话标识                 |

## 1.5 文件保存位置

- 保存目录：`data/temp/`
- 保存文件名：`{trace_id}.webm`
- 示例：`data/temp/trace_1713578123456.webm`

## 1.6 成功响应

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "record_upload",
  "status": "success",
  "timestamp": 1713578123456,
  "payload": {
    "audio_path": "data/temp/trace_1713578123456.webm",
    "format": "webm"
  },
  "error": null,
  "meta": {
    "source": "frontend_media_recorder"
  }
}
```

## 1.7 失败响应

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "record_upload",
  "status": "failed",
  "timestamp": 1713578123456,
  "payload": {},
  "error": {
    "code": "RECORD_UPLOAD_NO_AUDIO",
    "message": "未检测到 audio 文件"
  },
  "meta": {}
}
```

***

# 2. stt 阶段

## 2.1 阶段作用

将录音文件转为文本。

## 2.2 请求类型

后端内部处理类请求

## 2.3 输入格式

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "stt",
  "status": "success",
  "timestamp": 1713578123900,
  "payload": {
    "input_audio_path": "data/temp/trace_1713578123456.webm"
  },
  "error": null,
  "meta": {
    "provider": "local",
    "model": "whisper"
  }
}
```

## 2.4 成功响应

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "stt",
  "status": "success",
  "timestamp": 1713578124200,
  "payload": {
    "input_audio_path": "data/temp/trace_1713578123456.webm",
    "text": "你好，晚晚",
    "language": "zh"
  },
  "error": null,
  "meta": {
    "provider": "local",
    "model": "whisper"
  }
}
```

## 2.5 失败响应

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "stt",
  "status": "failed",
  "timestamp": 1713578124200,
  "payload": {},
  "error": {
    "code": "STT_RECOGNIZE_FAILED",
    "message": "STT 识别失败"
  },
  "meta": {
    "provider": "local",
    "model": "whisper"
  }
}
```

***

# 3. llm 阶段

## 3.1 阶段作用

根据 STT 文本和上下文生成回复文本。

## 3.2 请求类型

后端内部处理类请求

## 3.3 输入格式

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "llm",
  "status": "success",
  "timestamp": 1713578124500,
  "payload": {
    "user_text": "你好，晚晚",
    "history": [
      {
        "role": "user",
        "content": "之前的对话"
      }
    ],
    "system_prompt": "你是晚晚"
  },
  "error": null,
  "meta": {
    "provider": "openai",
    "model": "gpt-4o-mini"
  }
}
```

## 3.4 成功响应

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "llm",
  "status": "success",
  "timestamp": 1713578125000,
  "payload": {
    "user_text": "你好，晚晚",
    "reply_text": "我在，怎么了？"
  },
  "error": null,
  "meta": {
    "provider": "openai",
    "model": "gpt-4o-mini"
  }
}
```

## 3.5 失败响应

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "llm",
  "status": "failed",
  "timestamp": 1713578125000,
  "payload": {},
  "error": {
    "code": "LLM_GENERATE_FAILED",
    "message": "LLM 回复生成失败"
  },
  "meta": {
    "provider": "openai",
    "model": "gpt-4o-mini"
  }
}
```

***

# 4. tts 阶段

## 4.1 阶段作用

将 LLM 输出的文本转为基础语音音频。

## 4.2 请求类型

后端内部处理类请求

## 4.3 输入格式

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "tts",
  "status": "success",
  "timestamp": 1713578125200,
  "payload": {
    "input_text": "我在，怎么了？"
  },
  "error": null,
  "meta": {
    "provider": "cosyvoice",
    "voice": "wanwan_base"
  }
}
```

## 4.4 文件保存位置

- 保存目录：`data/tts/`
- 保存文件名：`{trace_id}.wav`

## 4.5 成功响应

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "tts",
  "status": "success",
  "timestamp": 1713578125600,
  "payload": {
    "input_text": "我在，怎么了？",
    "output_audio_path": "data/tts/trace_1713578123456.wav",
    "format": "wav"
  },
  "error": null,
  "meta": {
    "provider": "cosyvoice",
    "voice": "wanwan_base"
  }
}
```

## 4.6 失败响应

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "tts",
  "status": "failed",
  "timestamp": 1713578125600,
  "payload": {},
  "error": {
    "code": "TTS_GENERATE_FAILED",
    "message": "TTS 音频生成失败"
  },
  "meta": {
    "provider": "cosyvoice",
    "voice": "wanwan_base"
  }
}
```

***

# 5. rvc 阶段

## 5.1 阶段作用

将 TTS 输出的基础音频进行变声处理。

## 5.2 请求类型

后端内部处理类请求

## 5.3 输入格式

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "rvc",
  "status": "success",
  "timestamp": 1713578125900,
  "payload": {
    "input_audio_path": "data/tts/trace_1713578123456.wav"
  },
  "error": null,
  "meta": {
    "provider": "local_rvc",
    "model": "wanwan_rvc_v1"
  }
}
```

## 5.4 文件保存位置

- 保存目录：`data/rvc/`
- 保存文件名：`{trace_id}.wav`

## 5.5 成功响应

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "rvc",
  "status": "success",
  "timestamp": 1713578126300,
  "payload": {
    "input_audio_path": "data/tts/trace_1713578123456.wav",
    "output_audio_path": "data/rvc/trace_1713578123456.wav",
    "format": "wav"
  },
  "error": null,
  "meta": {
    "provider": "local_rvc",
    "model": "wanwan_rvc_v1"
  }
}
```

## 5.6 失败响应

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "rvc",
  "status": "failed",
  "timestamp": 1713578126300,
  "payload": {},
  "error": {
    "code": "RVC_CONVERT_FAILED",
    "message": "RVC 变声失败"
  },
  "meta": {
    "provider": "local_rvc",
    "model": "wanwan_rvc_v1"
  }
}
```

***

# 6. playback 阶段

## 6.1 阶段作用

将最终音频提供给前端播放。

## 6.2 请求类型

前端输出类请求 / 返回类请求

## 6.3 输入格式

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "playback",
  "status": "success",
  "timestamp": 1713578126500,
  "payload": {
    "final_audio_path": "data/rvc/trace_1713578123456.wav"
  },
  "error": null,
  "meta": {}
}
```

## 6.4 成功响应

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "playback",
  "status": "success",
  "timestamp": 1713578126700,
  "payload": {
    "audio_url": "/api/audio/trace_1713578123456.wav"
  },
  "error": null,
  "meta": {}
}
```

## 6.5 失败响应

```json
{
  "trace_id": "trace_1713578123456",
  "session_id": "session_001",
  "step": "playback",
  "status": "failed",
  "timestamp": 1713578126700,
  "payload": {},
  "error": {
    "code": "PLAYBACK_URL_GENERATE_FAILED",
    "message": "播放地址生成失败"
  },
  "meta": {}
}
```

## 6.6 路由实现建议

`/api/audio/{trace_id}.wav` 路由的实现建议：

- **实现方式**：使用 Flask 的 `send_file` 函数，从 `data/rvc/` 目录读取文件
- **文件查找顺序**：先查找 `data/rvc/{trace_id}.wav`，如果不存在则查找 `data/tts/{trace_id}.wav`
- **响应头设置**：设置 `Content-Type: audio/wav`，确保浏览器正确播放
- **错误处理**：文件不存在时返回 404 错误，并记录日志

<!-- 更改日期：2026-04-20 -->

***

# 附录：错误码表

| 错误码                            | 阶段              | 说明            |
| ------------------------------ | --------------- | ------------- |
| `RECORD_UPLOAD_NO_AUDIO`       | `record_upload` | 未检测到 audio 文件 |
| `RECORD_UPLOAD_SAVE_FAILED`    | `record_upload` | 录音文件保存失败      |
| `STT_RECOGNIZE_FAILED`         | `stt`           | STT 识别失败      |
| `LLM_GENERATE_FAILED`          | `llm`           | LLM 回复生成失败    |
| `TTS_GENERATE_FAILED`          | `tts`           | TTS 音频生成失败    |
| `RVC_CONVERT_FAILED`           | `rvc`           | RVC 变声失败      |
| `PLAYBACK_URL_GENERATE_FAILED` | `playback`      | 播放地址生成失败      |
| `PLAYBACK_FILE_NOT_FOUND`      | `playback`      | 音频文件不存在       |

<!-- 更改日期：2026-04-20 -->

***

# 附录：前端ID生成示例

## trace\_id 生成示例

```javascript
function generateTraceId() {
  return 'trace_' + Date.now();
}
```

## session\_id 生成示例（临时实现）

```javascript
function generateSessionId() {
  // 临时实现：使用固定值，后续可升级为真实会话管理
  return 'session_001';
}
```

<!-- 更改日期：2026-04-20 -->

***

# 附录：安全性说明

## 音频文件访问控制

为保护用户隐私和系统安全，建议对 `/api/audio/` 路由实现以下安全措施：

- **临时URL**：生成带过期时间的临时访问链接
- **访问验证**：验证请求来源或使用简单的签名机制
- **文件权限**：确保音频文件仅能通过 API 访问，不可直接通过文件路径访问
- **日志记录**：记录音频文件的访问日志，便于审计和排查问题

<!-- 更改日期：2026-04-20 -->
