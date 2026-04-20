# wanwan_base

## Purpose
为 wanwan-client 提供统一的项目开发约束，确保目录结构、命名规范、改动范围和输出格式一致。

## Project Context
- 当前目标：先完成 Windows 客户端 MVP
- 后续目标：扩展 Android 客户端
- 当前重点：文本聊天、TTS、录音、STT 回填
- 当前阶段不提前做实时双工、流式 RVC、复杂跨平台重构

## Directory Rules
- `src/wanwan_client/core/`：平台无关核心业务逻辑
- `src/wanwan_client/services/`：外部服务封装
- `src/wanwan_client/infrastructure/`：http、文件、日志、设置
- `src/wanwan_client/desktop/`：Windows UI 与交互
- `src/wanwan_client/shared/`：常量、schema、工具
- `data/`：运行数据
- `logs/`：日志
- `tests/`：测试

## Naming Rules
- 目录/文件/函数/变量：snake_case
- 类：PascalCase
- 常量：UPPER_SNAKE_CASE
- 禁止：final_v2、new_new、temp2、backup_final

## Working Rules
1. 先读相关文件，再修改
2. 先说明要改哪些文件
3. 默认小步修改，不做无关重构
4. 页面层不写核心业务逻辑
5. 外部服务统一经 services 层封装
6. 改完后说明：改了什么、为什么、风险、验证方式

## Hard Rules
- 不硬编码 API Key 和本机私有路径
- 不创建平行实现
- 不把运行数据混进源码目录
- 不把测试代码写进正式业务路径
- 优先保证可运行、可验证、可回退
