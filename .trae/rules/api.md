接口开发规则：

1. 本项目所有新增或修改的内部接口实现、阶段结果对象、错误返回结构，默认必须同时遵循：
- `docs/internal-api-spec.md`
- `docs/internal-api-payloads.md`
- `docs/internal-api-compat.md`

2. 当前代码与文档不一致时，默认优先按文档修正；除非用户明确要求临时偏离。

3. 外层字段固定，不得擅自新增同级替代字段：
trace_id
session_id
step
status
timestamp
payload
error
meta

4. 外层结构必须统一；阶段 payload 结构优先遵循 `docs/internal-api-payloads.md`；兼容、异常、降级、版本演进优先遵循 `docs/internal-api-compat.md`。

5. 实现接口后必须自检：
- 是否符合三份接口文档
- 是否使用统一错误结构
- 是否正确使用状态值：success / failed / running / partial / skipped / cancelled / degraded
- 是否使用 `trace_id` 贯穿链路
- 是否通过适配层处理第三方原始响应，而不是直接污染内部协议

6. 如某阶段暂时无法完全对齐文档，必须明确说明：已对齐部分、未对齐部分、原因、后续收口方式。

7. 内部阶段接口规范只约束内部链路结构，不等于外部服务层只能支持单一厂商、单一路径或单一模型。不得将统一结构误实现为固定单一 LLM/STT/TTS/RVC 接口。

8. 服务接入层默认按“多 provider、多模型、能力可配置”设计；provider、model、api_host、api_path、capabilities、context_window、max_output_tokens 等属于服务层配置，不属于外层固定字段。