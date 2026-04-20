# AGENTS.md

项目名：wanwan-client

目标：
- 当前阶段优先完成 Windows 客户端 MVP
- 后续再扩展 Android
- 当前优先链路：文本聊天 > TTS > 录音 > STT 回填 > 自动播报

原则：
- Windows first
- Android ready
- MVP first
- 小步迭代
- 先跑通，再优化
- 不做无边界重构
- 不为未来假想需求过度设计

目录原则：
- `core`：平台无关核心业务逻辑
- `services`：LLM/TTS/STT/RVC 封装
- `infrastructure`：http、文件、日志、设置
- `desktop`：Windows UI 与交互
- `shared`：常量、schema、工具
- `data`：角色、会话、配置、缓存、临时文件

协作规则：
1. 修改前先阅读相关文件
2. 先说明将改哪些文件
3. 默认只做当前任务直接相关改动
4. 不创建平行实现，不使用 `final_v2/new_new/temp2` 一类命名
5. 改完后说明：改动内容、原因、风险、验证方式

代码输出：
- 默认按适合初学者阅读的方式输出
- 带中文分段注释
- 代码后补充分段解释
- 不默认假设用户熟悉前端、后端、服务接入、音频链路

当前不优先处理：
- 实时双工语音
- 流式 RVC
- 回声消除
- 大规模跨平台重构