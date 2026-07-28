<div align="center">

  <a href="https://www.airi.asia">
    <img src="https://raw.githubusercontent.com/AiriCore-Dev/AiriCore/refs/heads/main/version.jpg" alt="AiriCore">
  </a>

# AiriCore

_✨ 一款高性能 QQ 机器人框架 ✨_

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="license">
  <img src="https://img.shields.io/badge/python-3.11-blue.svg" alt="Python">
  <a href="https://www.airi.asia">
    <img src="https://img.shields.io/badge/website-airi.asia-brightgreen" alt="website">
  </a>
  <img src="https://img.shields.io/badge/QQ%E7%BE%A4-1084667424-orange" alt="qq group">
</p>

[English](README.md) | 中文

</div>

一款高性能 QQ 机器人框架，集成智能对话、音游查询、战舰世界水表、Minecraft 服管、棋类对弈、签到点歌占卜等群聊功能。

- 官方网站：https://www.airi.asia
- Bot使用群：1030569383 / 808085026，分布式交流群：1084667424

### 功能一览

#### 智能对话 Airi-LLM

接入 OpenAI 兼容 API，带对话记忆与情绪系统、被动发言与夜间降频。

#### 音游查询

PJSK 综合查询（pjskhelp）、烤倍率 / pt 计算器（计算倍率、单人pt 等）。

#### 战舰世界 WoWS

水表与排行榜查询（wws help）。

#### Minecraft

RCON 服管（/help，仅部分群开放）。

#### 棋类

五子棋 / 黑白棋 / 围棋，以及内置纯 Python 引擎的中国象棋（人机 lv1-8 与 PvP）。

#### 娱乐

签到收藏、心愿瓶、海龟汤、今日运势、塔罗占卜、今日老婆、今天吃什么、网易云点歌、表情包 / 贴纸制作、emoji 合成、扫雷、缩写查询等。

#### 基础

帮助菜单（帮助 / help）、图片打包（packpic）、服务器状态（状态）、三级黑白名单、收发统计、入群欢迎等。

> [!NOTE]
>
> 发送 `帮助` 或 `help` 查看完整指令列表。

### 部署

前置：miniconda，以及一个可连接的 OneBot v11 实现（如 NapCat / Lagrange）。

1. 用 miniconda 创建并激活 Python 3.11 环境。

2. 安装依赖

```
pip install -r requirements.txt
```

3. 将 memes.zip 解压到环境 site-packages/meme-generator/memes/。

4. 安装字体 data/nonebot_plugin_meme_stickers/_shared/YurukaFangTang.ttf。

5. 复制配置文件并按需修改

```
cp .env.prod_example .env.prod
```

6. 整理启动脚本：Linux 把 `launch_linux.sh` 改名为 `launch.sh`，macOS 把 `launch_macos.sh` 改名为 `launch.sh`，Windows 把 `launch_windows.bat` 改名为 `launch.bat`，并删除其余系统的启动脚本。

7. 根目录启动：Linux / macOS 用 `./launch.sh`，Windows 用 `launch.bat`。

入口 airi.py 会包装 bot.py 并在崩溃后自动重启。OneBot 客户端默认连接 ws://127.0.0.1:15100/onebot/v11/ws。

> [!NOTE]
>
> 详见 [手动部署教程.md](一键部署脚本/手动部署教程.md)。

### 配置项

> 关键项位于 `.env.prod`，详细说明请查看 `.env.prod_example`

#### `cache_mode`

- 默认：`balanced`
- 说明：缓存策略，其中具体可选项如下：
  - `ram`
    - 说明：把可缓存的固定文件全部缓存进内存，最大限度降低磁盘 I/O，运行最快，但内存占用最高。
  - `balanced`
    - 说明：仅缓存高频使用的文件，兼顾磁盘 I/O 与内存占用（推荐）。
  - `disk`
    - 说明：完全停用缓存，所有文件每次都从磁盘读取，运行期间内存占用最小。

> [!NOTE]
>
> 改动 `cache_mode` 后需重启生效；切走某模式不会删除已有的 `.pk` 缓存文件（disk 模式下仅忽略不读写）。

#### TLS

bot.py 默认加载 ./ssl/ 下证书，若无需 HTTPS 请自行调整。

### 许可证

MIT License，Copyright (c) 2026 AiriCore Dev. 详见 [LICENSE](LICENSE)。
