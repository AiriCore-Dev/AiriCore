# airi_help Point Salad 入口设计

## 目标

在 `airi_help` 的“娱乐插件”节点中加入 `airi_point_salad` 的入口，让群聊用户能从总帮助发现游戏并跳转到插件自身规则说明。

## 内容

新增一项 `MORE MORE JUMP！Point Salad`，标注为 2–6 人群聊选牌桌游、作者为 AiriCore Dev.，并提示发送 `sl rl` 查看玩法和完整指令。

## 范围

仅修改 `plugins/airi_help/__init__.py` 的“娱乐插件”文本。保持合并转发结构、节点数量、触发词、权限和图片处理不变，不在总帮助中重复列出完整游戏指令。

## 验证

静态确认新入口位于“娱乐插件”节点且包含 `sl rl`；初始化 NoneBot 后加载 `airi_help` 与全项目插件；运行 Ruff、AST 解析和差异检查。
