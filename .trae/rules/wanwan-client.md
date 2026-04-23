# wanwan-client

项目名：wanwan-client

目标：
- 当前优先完成 Windows 桌宠式语音助手 MVP
- 后续再扩展 Android
- 当前优先链路：设置接入 > 文本链路跑通 > TTS > 语音输出 > 录音 > STT 回填 > 会话保存

原则：
- Windows first
- Android ready
- MVP first
- 小步迭代
- 先跑通，再优化
- 不做无边界重构
- 不为未来假想需求过度设计
- 不顺手扩需求

目录原则：
- `core`：平台无关核心逻辑
- `services`：STT/LLM/TTS/RVC 与 provider 适配
- `infrastructure`：http、文件、日志、设置
- `desktop`：Windows UI、桌宠交互、路由、静态资源
- `shared`：常量、schema、工具
- `data`：角色、会话、配置、缓存、临时文件

协作规则：
1. 修改前先阅读相关文件、规则和上下文
2. 先说明将修改哪些文件
3. 默认只做当前任务直接相关改动
4. 不创建平行实现，不使用 `final/new/v2/backup/temp`
5. 改后说明：改动、原因、风险、验证方式
6. 优先分层定位：UI、配置、service、文件、本地存储、第三方服务
7. 默认遵守：
   - `docs/internal-api-spec.md`
   - `docs/internal-api-payloads.md`
   - `docs/internal-api-compat.md`
8. 默认按多 provider、多模型、能力可配置设计，不写死单一接口、单一模型或单一能力。