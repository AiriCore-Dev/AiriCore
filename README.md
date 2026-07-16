![AiriCore](https://raw.githubusercontent.com/AiriCore-Dev/AiriCore/refs/heads/main/plitvice.avif)

# AiriCore v26.7 Plitvice

一款高性能 QQ 机器人框架，集成智能对话、音游查询、战舰世界水表、Minecraft 服管、棋类对弈、签到点歌占卜等群聊功能。

- 官方网站：https://www.airi.asia
- Bot使用群：1030569383 / 808085026，开发者交流群：1051523491

## 功能一览

- 智能对话 Airi-LLM：接入 OpenAI 兼容 API，带对话记忆与情绪系统、被动发言与夜间降频。
- 音游查询：PJSK 综合查询（pjskhelp）、烤倍率 / pt 计算器（计算倍率、单人pt 等）。
- 战舰世界 WoWS：水表与排行榜查询（wws help）。
- Minecraft：RCON 服管（/help，仅部分群开放）。
- 棋类：五子棋 / 黑白棋 / 围棋，以及内置纯 Python 引擎的中国象棋（人机 lv1-8 与 PvP）。
- 娱乐：签到收藏、心愿瓶、海龟汤、今日运势、塔罗占卜、今日老婆、今天吃什么、网易云点歌、表情包 / 贴纸制作、emoji 合成、扫雷、缩写查询等。
- 基础：帮助菜单（帮助 / help）、图片打包（packpic）、服务器状态（状态）、三级黑白名单、收发统计、入群欢迎等。

发送 `帮助` 或 `help` 查看完整指令列表。

## 部署

前置：miniconda，以及一个可连接的 OneBot v11 实现（如 NapCat / Lagrange）。

1. 用 miniconda 创建并激活 Python 3.11 环境。
2. `pip install -r requirements.txt`
3. 将 memes.zip 解压到环境 site-packages/meme-generator/memes/。
4. 安装字体 data/nonebot_plugin_meme_stickers/_shared/YurukaFangTang.ttf。
5. `cp .env.prod_example .env.prod` 并按需修改配置。
6. 根目录启动：Linux 用 `./launch_linux.sh`，macOS 用 `./launch_macos.sh`，Windows 用 `launch_windows.bat`。

入口 airi.py 会包装 bot.py 并在崩溃后自动重启。OneBot 客户端默认连接 ws://127.0.0.1:15100/onebot/v11/ws。

详见 部署教程.md。

## 配置

关键项位于 .env.prod：HOST/PORT、SUPERUSERS、ONEBOT_ACCESS_TOKEN、nickname，以及 LLM 接入（llm_api_key / llm_base_url / chat_llm_model）、cchess_engine_path、unified_password / _2fa_key 等。

缓存策略 cache_mode（默认 balanced）：

- ram：把可缓存的固定文件全部缓存进内存，最大限度降低磁盘 I/O，运行最快，但内存占用最高。
- balanced：仅缓存高频使用的文件，兼顾磁盘 I/O 与内存占用（推荐）。
- disk：完全停用缓存，所有文件每次都从磁盘读取，运行期间内存占用最小。

改动 cache_mode 后需重启生效；切走某模式不会删除已有的 .pk 缓存文件（disk 模式下仅忽略不读写）。

bot.py 默认加载 ./ssl/ 下证书，若无需 HTTPS 请自行调整。

## 许可证

MIT License，Copyright (c) 2026 AiriCore Dev. 详见 LICENSE。
