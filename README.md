<div align="center">

  <a href="https://www.airi.asia">
    <img src="https://raw.githubusercontent.com/AiriCore-Dev/AiriCore/refs/heads/main/version.jpg" alt="AiriCore">
  </a>

# AiriCore

_✨ A high-performance QQ bot framework ✨_

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="license">
  <img src="https://img.shields.io/badge/python-3.11-blue.svg" alt="Python">
  <a href="https://www.airi.asia">
    <img src="https://img.shields.io/badge/website-airi.asia-brightgreen" alt="website">
  </a>
  <img src="https://img.shields.io/badge/QQ%20group-1084667424-orange" alt="qq group">
</p>

English | [中文](README_CN.md)

</div>

A high-performance QQ bot framework with LLM chat, rhythm-game lookups, World of Warships stats, Minecraft server management, board games, daily check-in, music requests, fortune telling and more group features.

- Website: https://www.airi.asia
- Bot groups: 1030569383 / 808085026, distributed dev group: 1084667424

### Features

#### LLM chat (Airi-LLM)

OpenAI-compatible API with conversation memory, a mood system, passive speaking and reduced activity at night.

#### Rhythm games

PJSK all-in-one lookups (pjskhelp), event bonus / pt calculators (bonus rate, solo pt, etc.).

#### World of Warships

Player stats and leaderboards (wws help).

#### Minecraft

RCON server management (/help, enabled for selected groups only).

#### Board games

Gomoku / Reversi / Go, plus Chinese chess backed by a bundled pure-Python engine (AI lv1-8 and PvP).

#### Entertainment

Check-in and collections, wish bottle, lateral-thinking puzzles, daily fortune, tarot, daily waifu, what-to-eat, NetEase music requests, meme / sticker generation, emoji mixing, minesweeper, abbreviation lookup and more.

#### Core

Help menu (帮助 / help), image packing (packpic), server status (状态), three-tier allow/deny lists, traffic statistics, group welcome messages.

> [!NOTE]
>
> Send `帮助` or `help` for the full command list.

### Deployment

Prerequisites: miniconda, and a reachable OneBot v11 implementation (NapCat / Lagrange, etc.).

1. Create and activate a Python 3.11 environment with miniconda.

2. Install the dependencies

```
pip install -r requirements.txt
```

3. Extract memes.zip into the environment's site-packages/meme-generator/memes/.

4. Install the font data/nonebot_plugin_meme_stickers/_shared/YurukaFangTang.ttf.

5. Copy out the config file and adjust it as needed

```
cp .env.prod_example .env.prod
```

6. Settle the launch script: on Linux rename `launch_linux.sh` to `launch.sh`, on macOS rename `launch_macos.command` to `launch.command`, on Windows rename `launch_windows.bat` to `launch.bat`, then delete the launch scripts for the other systems.

7. Start from the project root: `./launch.sh` on Linux, `./launch.command` on macOS (double-clicking it in Finder works too), `launch.bat` on Windows.

The entry point bot.py supervises itself and restarts automatically after a crash. OneBot clients connect to ws://127.0.0.1:15100/onebot/v11/ws by default.

> [!NOTE]
>
> See [手动部署教程.md](一键部署脚本/手动部署教程.md) for details (Chinese).

### Configuration

> Key settings live in `.env.prod`; see `.env.prod_example` for the full description of every key

#### `cache_mode`

- Default: `balanced`
- Description: cache strategy, with the following options:
  - `ram`
    - Description: cache every cacheable static file in memory, minimizing disk I/O. Fastest, highest memory usage.
  - `balanced`
    - Description: cache only frequently used files, trading off disk I/O against memory usage (recommended).
  - `disk`
    - Description: disable caching entirely, read every file from disk each time. Lowest memory usage at runtime.

> [!NOTE]
>
> Changing `cache_mode` requires a restart. Switching away from a mode does not delete existing `.pk` cache files (disk mode simply ignores them).

#### TLS

bot.py loads certificates from `./utils/ssl/` by default; adjust it yourself if you do not need HTTPS.

### License

MIT License, Copyright (c) 2026 AiriCore Dev. See [LICENSE](LICENSE).

Adapted from NoneBot · MIT.
