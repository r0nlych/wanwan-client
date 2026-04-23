# wanwan-client 重建阶段 3 说明

## 1. 目标

本阶段只处理设置本地持久化最小闭环，不进入 provider 真实接入，不进入文本链路业务实现。

目标：

1. 让设置可以保存到本地文件
2. 让设置可以从本地文件读回
3. 让 `active_profile` 可以被正确选择
4. 当配置缺失或读取失败时，提供最小默认回退

## 2. 职责保持不变

### 2.1 `shared/schemas`

负责：

- 定义设置对象结构
- 定义对象与字典之间的最小转换
- 定义最小默认回退规则

不负责：

- 文件读写
- provider 调用
- 主链路业务编排

### 2.2 `infrastructure/settings`

负责：

- 设置文件路径
- 本地 JSON 读写
- 缺失文件和读取失败时回退默认设置

不负责：

- 运行时 profile 选择
- provider 真实接入

### 2.3 `core/config`

负责：

- 从设置对象构建运行时生效配置
- 按 `active_profile_id` 选择当前 profile
- profile 缺失时回退到首个可用 profile

不负责：

- 持久化格式定义
- provider 请求逻辑

## 3. 当前最小闭环

当前阶段形成的最小闭环：

1. `AppSettings` 可序列化为字典
2. `AppSettings` 可从字典恢复
3. `SettingsRepository.save()` 可写入本地 JSON
4. `SettingsRepository.load()` 可从本地 JSON 读回
5. `RuntimeConfig.from_settings()` 可基于 `active_profile_id` 选择生效 profile
6. 文件缺失、文件损坏、配置缺失时可回退到默认设置

## 4. 当前不做

- 不做复杂 schema 迁移
- 不做复杂字段校验
- 不做多层错误分类
- 不做设置页 UI
- 不做 provider 健康检查
- 不进入文本链路

## 5. 后续阶段建议

阶段 4 最适合先进入：

1. 设置页或最小设置入口接入
2. profile 切换与保存动作接入 UI
3. 文本链路最小编排入口

