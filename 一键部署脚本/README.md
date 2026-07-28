<div align="center">

# AiriCore One-Click Deployment

English | [中文](README_CN.md)

</div>

Full automation of the flow described in [手动部署教程.md](手动部署教程.md). The scripts resolve the project root from their own location, so they can be run from any directory.

### What the scripts do

1. Detect conda (PATH and common install paths); if missing, download Miniconda and install it silently into the user directory.
2. Create the conda environment `airicore` (Python 3.11), reusing it if it already exists.
3. Install `requirements.txt` and the Playwright Chromium runtime (on Linux, also Chromium's system dependencies).
4. Join the split archives `memes.zip.001` / `memes.zip.002` and extract them into the `meme_generator` package directory.
5. Install the font `YurukaFangTang.ttf` system-wide (on Windows, per current user, no administrator needed).
6. Copy `.env.prod` from `.env.prod_example` if absent; leave it untouched if present.
7. Generate a self-signed certificate in `./ssl/` if absent; leave it untouched if present.
8. Create the `logs/` and `data/` runtime directories, then run a final core-dependency self-check.
9. Settle the launch script: rename the one matching the current system to a unified name (`launch.sh` on Linux / macOS, `launch.bat` on Windows) and delete the launch scripts for the other systems.

> [!NOTE]
>
> Every step is idempotent; re-running never overwrites an existing environment, `.env.prod` or certificate.

### How to run on each system

- Windows, from a PowerShell session opened in this directory

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
> On Windows ARM64 a win-64 environment is created on purpose and runs through system emulation.
>
> `meme_generator` publishes no win-arm64 wheel, a mixed-architecture interpreter is not viable, and x64 is the only option that keeps every feature working.

### After deployment

1. Edit `.env.prod` in the project root. At minimum fill in `SUPERUSERS`, `ONEBOT_ACCESS_TOKEN`, `nickname`, and the three LLM keys `llm_api_key` / `llm_base_url` / `chat_llm_model`.
2. Point your OneBot v11 client (NapCat / Lagrange, etc.) at the bot. It listens on `HOST=0.0.0.0` `PORT=15100` by default with the WebSocket route `/ws`; since TLS is enabled, use `wss://` on the client.
3. Start from the project root: `./launch.sh` on Linux / macOS, `launch.bat` on Windows (the deploy script already renamed your system's launch script to that name). `airi.py` wraps `bot.py` and restarts it after a crash; press Ctrl+C to exit.

### Listening ports

Besides the main port, two plugins each start their own HTTPS service. Both reuse the same certificate pair under `./ssl/` and fall back to HTTP when it is missing. There is no need to open a port for a feature you do not use.

| Port | Source | Config key |
|---|---|---|
| 15100 | bot core (OneBot reverse WS) | `PORT` |
| 22319 | airi_daily_check roguelike Web API | `web_api_port` |
| 22320 | airi_market email unsubscribe service | `market_port` |

### Cache modes

#### `cache_mode`

- Default: `balanced`
- Description: `cache_mode` in `.env.prod` has three levels:
  - `ram`
    - Description: full in-memory cache, preloaded at startup up to `cache_preload_budget_mb` . Fastest, memory hungry.
  - `balanced`
    - Description: memory and disk balanced, hot data in memory and cold data on disk. The default.
  - `disk`
    - Description: prefer disk, lowest memory usage, suitable for small-memory VPS instances.

### Notes

- The generated certificate is self-signed. To serve HTTPS publicly, replace `./ssl/privkey.key` and `./ssl/fullchain.pem` with real ones. To drop TLS entirely, remove the `ssl_keyfile` / `ssl_certfile` arguments in `bot.py` and switch the client to `ws://`.
- On Windows the font is registered under the current user's Fonts registry key, so administrator rights are not required.
- All four downloads (Miniconda, conda channel, pip, Playwright) try a China mirror first and fall back to the official source automatically.
