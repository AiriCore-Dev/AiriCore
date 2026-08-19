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
6. Launch the interactive `.env.prod` setup wizard `_setup_env.py`, which builds the config through a guided Q&A. If a config already exists, it asks first and leaves it untouched when you decline.
7. Write the `enable_ssl` setting (off by default; provide certificates yourself when enabling it).
8. Create the `logs/` and `data/` runtime directories, then run a final core-dependency self-check.
9. Settle the launch script: rename the one matching the current system to a unified name (`launch.sh` on Linux, `launch.command` on macOS, `launch.bat` on Windows) and delete the launch scripts for the other systems.
10. After every deployment step succeeds, delete `memes.zip.001` and `memes.zip.002` from the project root.

> [!NOTE]
>
> Existing environments and `.env.prod` files are not overwritten. After a successful deployment removes the split archives, restore both files before running the full deployment script again.

### The setup wizard `_setup_env.py`

Step 6 drops you into the wizard, which fills in `.env.prod` through plain-language questions. No knowledge of the config format required.

- Every item comes with a plain explanation, a filled-in example, and what happens if you leave it blank
- Type `?` and press Enter for the long explanation (where to generate an SMTP auth code, where to copy a model name from, and so on)
- Press Enter to accept the default; type `q` to quit at any time without touching a single file
- QQ numbers, ports, URLs, email addresses and hour values are validated on the spot, so typos surface immediately instead of at startup
- The Minecraft, email and marketing blocks are optional; one y/n question decides whether they get asked at all
- A confirmation table is printed at the end with secrets masked; nothing is written until you confirm, and an existing `.env.prod` is backed up to `.env.prod.bak.<timestamp>`
- It also makes sure the root `.env` contains `ENVIRONMENT=prod`

Run it on its own (to change the config after deployment):

```
python 一键部署脚本/_setup_env.py
```

In non-interactive environments (CI, `nohup`, pipes) it skips the questions and falls back to copying `.env.prod_example`. You can also pass `--no-interactive` explicitly.

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
bash deploy_macos.command
```

  You can also just double-click `deploy_macos.command` in Finder.

> [!WARNING]
>
> On Windows ARM64 a win-64 environment is created on purpose and runs through system emulation.
>
> `meme_generator` publishes no win-arm64 wheel, a mixed-architecture interpreter is not viable, and x64 is the only option that keeps every feature working.

### After deployment

1. The wizard already walked you through the config during deployment. Re-run `python 一键部署脚本/_setup_env.py` to update it; LLM profiles live in `data/LLM/default.conf` and can be hot-switched with `airiccswitch <profile>`. `.env.prod` contains only bot and plugin business settings.
2. Point your OneBot v11 client (NapCat / Lagrange, etc.) at the bot. It listens on `HOST=0.0.0.0` `PORT=15100` by default with the WebSocket route `/ws`; use `ws://` when `enable_ssl=false`, or `wss://` after changing it to `true`.
3. Start from the project root: `./launch.sh` on Linux, `./launch.command` on macOS (double-clicking it in Finder works too), `launch.bat` on Windows (the deploy script already renamed your system's launch script to that name). `bot.py` supervises itself and restarts after a crash; press Ctrl+C to exit.

### Listening ports

The marketing unsubscribe service uses `market_port` and follows the protocol selected by `enable_ssl`.

| Port | Source | Config key |
|---|---|---|
| 15100 | bot core (OneBot reverse WS) | `PORT` |
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

- `enable_ssl` defaults to `false`. Change it to `true` to make the bot and marketing service load `./utils/ssl/privkey.key` and `./utils/ssl/fullchain.pem`; with it disabled, use `ws://`.
- On Windows the font is registered under the current user's Fonts registry key, so administrator rights are not required.
- All four downloads (Miniconda, conda channel, pip, Playwright) try a China mirror first and fall back to the official source automatically.

### License

MIT License, Copyright (c) 2026 AiriCore Dev. See [LICENSE](../LICENSE).

Adapted from NoneBot · MIT.
