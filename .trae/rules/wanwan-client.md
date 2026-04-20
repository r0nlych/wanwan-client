# wanwan-client 项目规则

目标：先完成 Windows 客户端 MVP，后续再扩展 Android。当前优先级：文本聊天 > TTS > 录音 > STT 回填 > 自动播报。未明确要求前，不做实时双工、流式 RVC、复杂跨平台重构。

结构规范：
- `src/wanwan_client/core`：平台无关业务逻辑
- `services`：LLM/TTS/STT/RVC 封装
- `infrastructure`：http、文件、日志、设置
- `desktop`：Windows UI 与交互
- `shared`：常量、工具、schema
- `data`：角色/会话/配置/缓存/临时文件

技术限制：
- 主语言 Python
- UI 先走轻量方案
- 第三方能力统一经 `services` 接入
- 配置优先 JSON 外置，不硬编码密钥和本机私有路径

命名规则：
- 目录/文件/函数/变量：`snake_case`
- 类：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`
- 禁止 `final_v2`、`new_new`、`temp2`

工作规则：
1. 先理解目标并阅读相关文件
2. 先说明将修改哪些文件
3. 默认小步修改，只做当前任务直接相关改动
4. 页面不写核心业务逻辑，不做平行实现
5. 改完说明：改动、原因、风险、验证方式

代码输出：
- 默认中文
- 代码按逻辑块加中文注释
- 代码后补充分段解释：改了哪些文件、每段作用、运行后会发生什么
- 除非明确要求，只给代码是禁止的