<div align="center">

# AiriCore 一键部署

[English](README.md) | 中文

</div>

对应 [手动部署教程.md](手动部署教程.md) 的全流程自动化。脚本会根据自身位置解析项目根目录，从任意目录执行都可以。

### 脚本做了什么

1. 探测 conda（PATH 与常见安装路径），没有就下载 Miniconda 静默安装到用户目录。
2. 创建 conda 环境 `airicore`（Python 3.11），已存在则复用。
3. 装 `requirements.txt`，装 Playwright Chromium 运行时（Linux 额外装 Chromium 的系统依赖）。
4. 把分卷 `memes.zip.001` / `memes.zip.002` 拼接后解压进 `meme_generator` 包目录。
5. 安装字体 `YurukaFangTang.ttf` 到系统（Windows 走当前用户，无需管理员）。
6. 不存在时从 `.env.prod_example` 复制出 `.env.prod`，已存在则保持不变。
7. 不存在时在 `./ssl/` 生成自签名证书，已存在则保持不变。
8. 创建 `logs/` 与 `data/` 运行时目录，最后跑一次核心依赖自检。
9. 整理启动脚本：把当前系统对应的那个重命名为统一名字（Linux / macOS 为 `launch.sh`，Windows 为 `launch.bat`），并删掉其余系统的启动脚本。

> [!NOTE]
>
> 全部步骤幂等，重复执行不会覆盖已有的环境、`.env.prod` 和证书。

### 各系统执行方式

- Windows，在本目录打开 PowerShell

```
powershell -ExecutionPolicy Bypass -File .\deploy_windows.ps1
```

- Linux

```
bash deploy_linux.sh
```

- macOS

```
bash deploy_macos.sh
```

> [!WARNING]
>
> Windows ARM64 会强制创建 win-64 环境，通过系统模拟运行。
>
> 原因是 `meme_generator` 没有发布 win-arm64 轮子，混架构解释器不可行，走 x64 是唯一能保住全部功能的方案。

### 部署完成后

1. 编辑项目根目录的 `.env.prod`，至少填 `SUPERUSERS`、`ONEBOT_ACCESS_TOKEN`、`nickname`，以及 LLM 三项 `llm_api_key` / `llm_base_url` / `chat_llm_model`。
2. 把 OneBot v11 客户端（NapCat / Lagrange 等）指向 bot。默认监听 `HOST=0.0.0.0` `PORT=15100`，WebSocket 路由 `/ws`；因为启用了 TLS，客户端用 `wss://`。
3. 从项目根目录启动：Linux / macOS 跑 `./launch.sh`，Windows 跑 `launch.bat`（部署脚本已把对应系统的启动脚本改成这个名字）。`airi.py` 包装 `bot.py` 并在崩溃后自动重启，按 Ctrl+C 退出。

### 监听端口

除主端口外还有两个插件各自起 HTTPS 服务，都复用 `./ssl/` 下的同一套证书，证书缺失时会退化成 HTTP。用不到对应功能就不必开放端口。

| 端口 | 来源 | 配置项 |
|---|---|---|
| 15100 | bot 主体（OneBot 反向 WS） | `PORT` |
| 22319 | airi_daily_check 肉鸽 Web API | `web_api_port` |
| 22320 | airi_market 邮件退订服务 | `market_port` |

### 缓存模式

#### `cache_mode`

- 默认：`balanced`
- 说明：`.env.prod` 的 `cache_mode` 有三档：
  - `ram`
    - 说明：全量内存缓存，启动时按 `cache_preload_budget_mb` 预热，最快但吃内存。
  - `balanced`
    - 说明：内存加磁盘均衡，热数据留内存、冷数据落盘，默认值。
  - `disk`
    - 说明：尽量落盘，内存占用最低，适合小内存 VPS。

### 说明

- 生成的是自签名证书。要对公网提供 HTTPS，把 `./ssl/privkey.key` 与 `./ssl/fullchain.pem` 换成真证书即可。完全不想用 TLS 则删掉 `bot.py` 里的 `ssl_keyfile` / `ssl_certfile` 两个参数，客户端改用 `ws://`。
- Windows 的字体写进当前用户的 Fonts 注册表项，不需要管理员权限。
- 四处下载（Miniconda、conda channel、pip、Playwright）都是先国内镜像、失败自动回退官方源。
