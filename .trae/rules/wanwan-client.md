wanwan-client 项目规则：

目标：先完成 Windows 客户端 MVP，后续再扩 Android。当前优先级：文本聊天 > TTS > 录音 > STT 回填 > 自动播报。未明确要求前，不做实时双工、流式 RVC、多模型切换、复杂跨平台重构、重型状态机和大规模重构。

结构职责：
core=平台无关逻辑；services=LLM/TTS/STT/RVC 封装；infrastructure=http/文件/日志/设置；desktop=Windows UI、路由、静态资源；shared=常量/工具/schema；data=配置/缓存/临时文件。

强约束：
1. 所有接口必须遵循 `docs/internal-api-spec.md`
2. 外层字段固定：trace_id、session_id、step、status、timestamp、payload、error、meta
3. `app.py` 只做路由、调度、返回，不持续堆复杂业务
4. services 优先返回纯业务结果，不直接深度耦合完整 HTTP 响应格式
5. 配置、模型名、provider、路径不得散落硬编码，逐步收口
6. 页面不写核心业务逻辑，不做平行实现，不复制出第二套流程
7. 新功能优先放入对应模块，保持高内聚、低耦合
8. 小步修改，只做当前任务直接相关改动
9. 改前先说明改哪些文件；改后必须说明：改动、原因、风险、验证方式
10. 先跑通主链路，再做接口收口和优化，不提前发散