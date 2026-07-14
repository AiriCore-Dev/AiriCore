# AiriCore One-Click Deploy

Scripts here automate the full setup described in the project's deploy guide:
install Miniconda (if missing), create a Python 3.11 conda env named `airicore`,
install `requirements.txt`, install the Playwright Chromium runtime, unpack the
split `memes.zip.00*` into the `meme_generator` package, install the
`YurukaFangTang.ttf` font, create `.env.prod` from the example, and generate a
self-signed cert in `./ssl/` (bot.py loads `./ssl/privkey.key` and
`./ssl/fullchain.pem`).

Run the script for your OS from anywhere; it resolves the project root relative
to its own location.

## Windows

Open PowerShell in this folder and run:

    powershell -ExecutionPolicy Bypass -File .\deploy_windows.ps1

If PowerShell blocks the script, the `-ExecutionPolicy Bypass` flag above
handles it for that single run.

## Linux

    bash deploy_linux.sh

On Linux the script also runs `playwright install-deps chromium` when `sudo` is
available, to pull the system libraries Chromium needs.

## macOS

    bash deploy_macos.sh

## After deploying

1. Edit `.env.prod` in the project root. Set at least `SUPERUSERS`,
   `ONEBOT_ACCESS_TOKEN`, `nickname`, and the LLM keys
   (`llm_api_key` / `llm_base_url` / `chat_llm_model`).
2. Point your OneBot v11 client (NapCat / Lagrange) at the bot. Default listen
   is `HOST=0.0.0.0` `PORT=15100` with WS route `/ws`.
3. Start the bot from the project root:
   - Windows: `launch_windows.bat`
   - Linux: `./launch_linux.sh`
   - macOS: `./launch_macos.sh`

`airi.py` wraps `bot.py` and auto-restarts it after a crash.

## Notes

- The scripts are idempotent. Re-running reuses an existing `airicore` env and
  leaves an existing `.env.prod` and `./ssl/` cert untouched.
- The generated SSL cert is self-signed. For a public HTTPS endpoint replace
  `./ssl/privkey.key` and `./ssl/fullchain.pem` with real certificates. To run
  without TLS, remove the `ssl_keyfile` / `ssl_certfile` args in `bot.py` and
  point the client at `ws://` instead of `wss://`.
- The font on Windows is installed per-user (no admin needed) via the per-user
  Fonts registry key.
