# LLM provider 骨架说明

当前目录只用于放置 LLM provider 适配层实现。

## 约束

- 不在这里写持久化配置
- 不在这里写主链路编排
- 不在这里定义内部统一协议
- 具体 provider 必须通过统一配置对象获取：
  - `provider_id`
  - `model_id`
  - `api_host`
  - `api_path`
  - `capabilities`

当前阶段只保留目录落点，不写具体实现。

