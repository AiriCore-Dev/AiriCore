# Task 1 Coordination Audit Baseline

Date: 2026-08-27
Workspace: `/Users/liko/Documents/GitHub/AiriCore`

## Runtime and static baseline

Commands were run with `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python`.

| Check | Result |
|---|---|
| `python --version` | PASS, Python 3.11.15 |
| dependency import (`nonebot`, `aiohttp`, `httpx`, `PIL`) | PASS, `deps-ok` |
| `python -m compileall -q bot.py utils plugins` | PASS, exit 0 |
| `ruff check --select E9,F63,F7,F82 bot.py utils plugins` | FAIL, one F821 at `utils/pyfairy_xiangqi.py:8`: undefined `main` in the `__main__` branch |
| `git diff --check` | PASS, exit 0 |
| top-level plugin directories | 36 |
| Python files under `utils` and `plugins` | 340 |

An actual `python bot.py` launch was attempted in a subprocess with a six-second observation limit. It remained running until the limit and therefore produced no captured load summary; this is an inconclusive startup observation, not a plugin-load pass/fail. No production files were changed by the checks.

## Targeted coordination observations

Searches covered `asyncio.create_task`, lifecycle decorators, `nonebot.get_bots()`, cross-plugin imports, blocking I/O and pickle loads, and unbounded loops.

| Priority | Trigger / owner | Cross-module impact | Reproducibility / evidence |
|---|---|---|---|
| P1 | `asyncio.create_task` in `utils/observability.py:139`, `plugins/airi_blacklist/__init__.py:187`, `plugins/airi_llm/__init__.py:654,697`, `plugins/nonebot_plugin_meme_stickers/__init__.py:49` | Background work can outlive request/lifecycle scope; shutdown ownership and exception handling need audit. | Static, directly reproducible by exercising the corresponding startup/message paths. |
| P1 | `plugins/airi_new_group/__init__.py:71,227`, `plugins/airi_market/handlers/commands.py:48`, `plugins/airi_mcrcon/__init__.py:520`, `plugins/airi_switch/__init__.py:273,457` use `get_bots()` | Global bot selection can route sends to the wrong Bot in multi-bot deployments. | Static; multi-bot routing is reproducible with two connected Bot instances. |
| P1 | Pickle loads across `airi_llm`, `airi_daily_check`, `airi_market`, `airi_switch`, `airi_mcrcon`, `airi_turtle_soup`, `airi_wish_bottle`, `today_waifu`, `tarot`, `whateat_pic`, and others | Persistence schemas and untrusted/corrupt data handling are distributed; startup failures or unsafe object loading can affect plugin loading. | Static; corrupt/legacy fixture tests required per owner. |
| P1 | Blocking loops/I/O: `plugins/airi_switch/counter.py:104` (`time.sleep`), `bot.py:18-21` (`os.system`/sleep), synchronous file operations in handlers | Event-loop latency and shutdown coordination can regress, especially under concurrent events. | Static; latency/soak reproduction required. |
| P2 | Lifecycle registrations spread across `bot.py`, `utils/llm.py`, and many plugins (`on_startup`, `on_shutdown`, connect/disconnect) | Ordering and duplicate registration are implicit; startup dependencies such as Alconna/localstore must remain loaded first. | Static; clean-process startup is reproducible. |
| P2 | Unbounded `while True` loops in meme-sticker handlers, `airi_blacklist`, `observability`, `airi_wish_bottle`, `cchess`, Point Salad, and `totp_2fa` | Cancellation, retry ceilings, and resource release vary by owner. | Static; cancellation/timeout tests needed per loop. |
| P2 | Cross-plugin imports in `utils/cache.py` and Point Salad's optional `airi_game_server` bridge | Utility import order and locally ignored game-server code can make plugin loading environment-dependent. | Static; fresh-process import with/without optional module is reproducible. |

## Prioritized follow-up ledger

1. Validate and either fix or explicitly baseline the Ruff F821 before interpreting later static checks.
2. Add a clean-process plugin load probe that records each plugin success/failure and lifecycle registration order without starting a long-running server.
3. Audit all fire-and-forget tasks for tracked ownership, cancellation, and exception retrieval at shutdown.
4. Exercise two-Bot routing for every direct `get_bots()` consumer and require event-origin Bot routing where sends are group-specific.
5. Review every pickle loader's format/version validation, restricted unpickler policy, corruption quarantine, and atomic flush behavior.
6. Run bounded cancellation and latency probes for the listed loops and synchronous operations.

## Worktree preservation

The pre-existing worktree was preserved. Only this report is intended as the Task 1 artifact; no production code was edited.
