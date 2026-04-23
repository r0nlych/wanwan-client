# wanwan-client 重建阶段 4 说明

## 1. 目标

本阶段只处理“配置应用最小入口”，不进入桌宠 UI，不进入设置页，不进入 provider 真实接入。

目标：

1. 建立配置应用入口，负责读取当前设置并生成当前运行时配置
2. 提供最小能力：
   - 获取当前 `active_profile`
   - 获取可用 `profiles`
   - 切换 `active_profile`
   - 保存并重新生成 `runtime_config`

## 2. 目录职责

### 2.1 `core/app`

负责：

- 作为应用层最小收口点
- 组合 `core/config` 与 `infrastructure/settings`
- 向未来 UI 或其他入口暴露统一配置应用动作

不负责：

- 桌宠 UI
- 设置页逻辑
- provider 调用
- 主链路业务编排

### 2.2 `core/config`

继续负责：

- 设置对象到运行时配置对象的转换
- profile 切换后的运行时配置重建

### 2.3 `main.py`

当前只作为最小启动验证入口：

- 读取配置应用状态
- 打印当前 active profile 与可用 profiles

## 3. 当前最小能力

当前阶段形成的应用层最小能力：

1. 读取当前设置并生成 `RuntimeAppState`
2. 获取当前 `active_profile`
3. 获取当前可用 `profiles`
4. 切换 `active_profile`
5. 保存并重新生成 `runtime_config`

## 4. 当前不做

- 不做设置页
- 不做桌宠 UI
- 不做 provider 初始化
- 不做文本链路
- 不做复杂生命周期管理

## 5. 后续阶段建议

阶段 5 最适合先进入：

1. 最小设置入口或调试入口接入
2. 文本链路最小编排入口
3. 后续再逐步接入 provider 真实调用

