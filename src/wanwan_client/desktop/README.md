# desktop 模块说明

当前目录已进入桌宠重建阶段。

## 当前定位

- `desktop` 以 Windows 本地桌宠 UI、输入输出交互为主
- 不再默认承载旧 Web 主体
- 旧 `routes/templates/static` 仅保留为历史参考，不继续扩展

## 阶段 1 目录策略

- `app/`：桌宠应用入口骨架
- `pet/`：桌宠外观与状态骨架
- `input/`：文本输入、录音入口骨架
- `playback/`：本地播放控制骨架
- `settings/`：本地设置入口骨架

## 冻结说明

以下目录属于旧方向残留：

- `routes/`
- `templates/`
- `static/`

当前阶段不删除它们，但后续默认不继续扩展。

