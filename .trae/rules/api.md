接口开发规则：

1. 本项目所有新增或修改的接口实现、阶段结果对象、错误返回结构，默认必须遵循：
docs/internal-api-spec.md

2. 如果当前代码与接口文档不一致，优先按文档修正；除非用户明确要求临时偏离规范。

3. 不得擅自发明新的外层字段命名。统一外层字段固定为：
trace_id
session_id
step
status
timestamp
payload
error
meta

4. 各阶段 payload 可按业务定义，但返回外层结构必须统一。

5. 实现接口后，必须自检：
- 是否符合 docs/internal-api-spec.md
- 是否使用统一错误结构
- 是否使用统一状态值 success / failed
- 是否使用 trace_id 贯穿链路

6. 如果某个阶段暂时无法完全对齐文档，实现后必须明确说明：
- 哪些部分已对齐
- 哪些部分暂未对齐
- 为什么暂未对齐