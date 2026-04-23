# STT Provider 适配说明

## 目标

`services/stt/providers` 只负责收口 STT provider 差异，不承接：

- UI
- pipeline 编排
- 录音入口
- 会话保存

项目内部只认统一的 `stt` 阶段结果，不允许把第三方原始响应直接往上抛。

## 通用接口

统一入口是 `SttProvider.transcribe(request) -> SttProviderResult`。

`SttProviderRequest` 负责承接：

- `provider_config`
- `model_config`
- `audio_ref`
- `language_hint`
- `prompt`
- `response_format`
- `audio_format`
- `request_mode`

`SttProviderResult` 统一返回：

- `text`
- `is_final`
- `utterances`
- `segments`
- `request_id`
- `provider_job_id`
- `meta`

## 通用层职责

通用层负责：

- provider 注册与选择
- `audio_ref` 输入表达
- 统一错误结构
- 统一阶段结果映射
- 同步 / 异步 provider 的统一调用口
- `sync_url / sync_base64 / async_url / async_base64` 四种模式的统一表达

provider 特有层负责：

- 认证头
- submit/query 或单次请求细节
- 请求体字段拼装
- 轮询策略
- 原始响应归一化

## 输入兼容

统一输入表达使用 `audio_ref`：

- `remote_url`
- `local_path`
- `base64_inline`

不同 provider 自己声明能吃哪一类输入。

如果 provider 需要远程 URL，但当前项目只有本地文件，必须显式报错，提示缺少“本地音频 -> 可访问 URL”桥接层，不能偷偷跳过。

如果 provider 需要 base64：

- `base64_inline` 可直接透传
- `local_path` 可在 provider 适配层读取本地文件并编码为 base64
- 不应偷偷把 `remote_url` 下载后再转 base64

## 同步 / 异步兼容

统一入口不区分同步或异步。

- 同步 provider：在 `transcribe()` 内直接请求并归一化返回
- 异步 provider：在 `transcribe()` 内自己封装 submit/query/polling

对项目内部表现始终是一次 `stt` 阶段调用。

## 四种模式

当前框架明确支持表达四种模式：

- `sync_url`
- `sync_base64`
- `async_url`
- `async_base64`

模式优先由 `request_mode` 指定。

如果没显式指定，则按 `audio_ref.type` 和 provider 声明的支持范围自动推断：

- `remote_url` 优先映射到 `*_url`
- `local_path` / `base64_inline` 优先映射到 `*_base64`

## 内部协议映射

统一映射到：

- `payload.output.text`
- `payload.output.utterances`
- `payload.output.segments`
- `meta.provider`
- `meta.model`
- `meta.capabilities`

不允许把 provider 原始 body 直接塞进 `payload.output`。

## 配置分层

通用字段放 `ProviderConfig` 顶层，例如：

- `service_name`
- `adapter_kind`
- `provider_id`
- `api_host`
- `api_path`
- `api_key`
- `api_key_env`
- `timeout_seconds`
- `default_model_id`

模型通用字段放 `ProviderModelConfig`，例如：

- `model_id`
- `display_name`
- `capabilities`

provider 特有配置放 `extra`，例如：

- `query_path`
- `query_interval_ms`
- `query_timeout_seconds`
- `resource_id`
- `auth_mode`
- `app_id`
- `request_mode`

## 当前 provider 落地

已接入：

- `doubao_flash`
  - `sync_url`
  - `sync_base64`
- `doubao_async`
  - `async_url`
  - `async_base64`

后续继续接：

- OpenAI-compatible STT
- 百度 / 火山 / 其他国内 STT
- 本地 Whisper

都不需要改内部 `stt` 协议。 
