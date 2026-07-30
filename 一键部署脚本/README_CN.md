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
6. 启动 `.env.prod` 交互式配置向导 `_setup_env.py`，一问一答生成配置；已有配置会先问你要不要重配，跳过则保持原样。
7. 不存在时在 `./utils/ssl/` 生成自签名证书，已存在则保持不变。
8. 创建 `logs/` 与 `data/` 运行时目录，最后跑一次核心依赖自检。
9. 整理启动脚本：把当前系统对应的那个重命名为统一名字（Linux 为 `launch.sh`，macOS 为 `launch.command`，Windows 为 `launch.bat`），并删掉其余系统的启动脚本。
10. 全部部署步骤成功后，删除项目根目录中的 `memes.zip.001` 与 `memes.zip.002`。

> [!NOTE]
>
> 已有环境、`.env.prod` 和证书不会被覆盖。部署成功后分卷会被删除，如需再次完整运行部署脚本，请先放回这两个分卷。

### 配置向导 `_setup_env.py`

部署到第 6 步会自动进入向导，一问一答带你把 `.env.prod` 填完，不需要懂配置文件格式。

- 每一项都有大白话说明、填写示例，以及「留空会怎样」
- 输入 `?` 回车看这一项的详细解释（比如授权码去哪里生成、模型名去哪里抄）
- 直接回车用默认值；输入 `q` 随时退出，不会改动任何文件
- QQ 号、端口、URL、邮箱、小时数都会当场校验，填错会提示重填而不是等到启动才报错
- MC 服管、邮件、营销推送三块是可选的，开头一句 y/n 决定要不要问
- 最后会打印一张确认表（密钥自动打码），确认后才写入；已有 `.env.prod` 会先备份成 `.env.prod.bak.<时间戳>`
- 会顺手确认根目录 `.env` 里有 `ENVIRONMENT=prod`

单独运行（部署完之后想改配置）：

```
python 一键部署脚本/_setup_env.py
```

非交互环境（CI、`nohup`、管道）会自动跳过提问，退化成复制 `.env.prod_example`；也可以显式传 `--no-interactive`。

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
bash deploy_macos.command
```

  也可直接在 Finder 里双击 `deploy_macos.command`。

> [!WARNING]
>
> Windows ARM64 会强制创建 win-64 环境，通过系统模拟运行。
>
> 原因是 `meme_generator` 没有发布 win-arm64 轮子，混架构解释器不可行，走 x64 是唯一能保住全部功能的方案。

### 部署完成后

1. 配置项在部署过程中已由向导问过一遍。想改随时重跑 `python 一键部署脚本/_setup_env.py`，或手动编辑项目根目录的 `.env.prod`。最少要有 `SUPERUSERS`、`ONEBOT_ACCESS_TOKEN`、`nickname` 以及 LLM 三项 `llm_api_key` / `llm_base_url` / `chat_llm_model`。
2. 把 OneBot v11 客户端（NapCat / Lagrange 等）指向 bot。默认监听 `HOST=0.0.0.0` `PORT=15100`，WebSocket 路由 `/ws`；因为启用了 TLS，客户端用 `wss://`。
3. 从项目根目录启动：Linux 跑 `./launch.sh`，macOS 跑 `./launch.command`（也可在 Finder 里双击），Windows 跑 `launch.bat`（部署脚本已把对应系统的启动脚本改成这个名字）。`bot.py` 自带守护进程，崩溃后自动重启，按 Ctrl+C 退出。

### 监听端口

除主端口外还有两个插件各自起 HTTPS 服务，都复用 `./utils/ssl/` 下的同一套证书，证书缺失时会退化成 HTTP。用不到对应功能就不必开放端口。

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

- 生成的是自签名证书。要对公网提供 HTTPS，把 `./utils/ssl/privkey.key` 与 `./utils/ssl/fullchain.pem` 换成真证书即可。完全不想用 TLS 则删掉 `bot.py` 里的 `ssl_keyfile` / `ssl_certfile` 两个参数，客户端改用 `ws://`。
- Windows 的字体写进当前用户的 Fonts 注册表项，不需要管理员权限。
- 四处下载（Miniconda、conda channel、pip、Playwright）都是先国内镜像、失败自动回退官方源。
