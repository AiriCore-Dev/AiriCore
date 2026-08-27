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

## Revision evidence

### Complete `create_task` inventory

- `bot.py:448` cache preload uses `create_task(to_thread(...))`; task is retained in `_bg_tasks` and result is consumed by a callback.
- `utils/onebot_query.py:355` schedules delayed query work; owner/cancellation behavior requires follow-up.
- `utils/observability.py:139` starts the monitor task; `_task` is retained and stopped through the module lifecycle.
- `plugins/nonebot_plugin_meme_stickers/__init__.py:49` schedules update work from startup; no local task handle is retained at the call site.
- `plugins/nonebot_plugin_cchess/engine.py:62` schedules process reaping on the running loop; process lifecycle is coupled to engine instances.
- `plugins/airi_market/__init__.py:22` schedules the invite task on bot connect; task ownership is separate from the connect hook.
- `plugins/airi_blacklist/__init__.py:187` schedules periodic log saving during startup; shutdown persistence is separately registered.
- `plugins/airi_point_salad/service.py:299,322` schedules per-room expiry tasks from callbacks; duplicate/late expiry cancellation needs audit.
- `plugins/airi_llm/__init__.py:654` schedules a supplied coroutine and `:697` schedules batch processing; both are event-driven background work.

### Complete direct `nonebot.get_bots()` inventory

- `utils/messaging.py:20` global bot map used by broadcast messaging; routing impact is cross-plugin.
- `plugins/airi_daily_check/base/persistence.py:149` checks whether any bot is online before clearing state.
- `plugins/airi_new_group/__init__.py:71,227` selects/list-walks all bots for group broadcasts.
- `plugins/airi_point_salad/__init__.py:316` iterates all bots for notifications.
- `plugins/airi_mcrcon/__init__.py:520` selects from all bots for server notifications.
- `plugins/airi_switch/dedup.py:163,190` reads the global map for dedup/profile operations.
- `plugins/airi_switch/__init__.py:273,457` reads/list-walks all bots for status and management operations.
- `plugins/airi_llm/__init__.py:834,882,1014` validates/looks up the event Bot in the global map.
- `plugins/airi_market/handlers/commands.py:48` enumerates all bots for mail/article targeting.

### Actionable pickle loader inventory

| File:line | Trigger / data | Schema and error behavior | Reproducibility |
|---|---|---|---|
| `utils/llm.py:578` | startup/statistics read | loads stats pickle, catches load errors and falls back to empty state; schema migration is local | corrupt `daily_stats.pk` fixture |
| `plugins/nonebot_plugin_memes/manager.py:133` | manager initialization | loads dict payload, validates keys and regenerates on corruption | malformed manager fixture |
| `plugins/airi_switch/counter.py:55` | counter initialization | loads daily message stats; fallback/recovery handled by counter loader | malformed stats fixture |
| `plugins/airi_switch/cache.py:88` | cache initialization | loads cache payload with fallback to empty cache | malformed cache fixture |
| `plugins/nonebot_plugin_today_waifu/record.py:35` | startup record load | accepts persisted record shape and falls back when unreadable | corrupt/legacy record fixture |
| `plugins/nonebot_plugin_today_waifu/cache.py:72` | startup avatar cache load | reads cache payload and recovers empty cache on failure | corrupt cache fixture |
| `plugins/airi_turtle_soup/base/persistence.py:24` | startup game state | loads persisted game mapping with validation/fallback | corrupt state fixture |
| `plugins/airi_market/base/cache.py:71` | cache startup | loads cache payload with fallback | corrupt cache fixture |
| `plugins/airi_market/base/persistence.py:29` | market startup | loads market data and handles unreadable state | corrupt/legacy data fixture |
| `plugins/nonebot_plugin_tarot/cache.py:74` | tarot cache startup | loads cache mapping; invalid data is discarded | corrupt cache fixture |
| `plugins/nonebot_plugin_whateat_pic/cache.py:71` | image cache startup | loads cache metadata and falls back empty | corrupt cache fixture |
| `plugins/airi_point_salad/persistence.py:110` | game startup/restore | restricted `_PlainUnpickler` plus `GameState.from_dict` schema validation; bad main/backup is quarantined/recovered | malformed and legacy v2 fixtures |
| `plugins/airi_wish_bottle/base/persistence.py:27` | wish-bottle startup | loads persisted mapping with fallback and atomic save path | corrupt data fixture |
| `plugins/airi_mcrcon/__init__.py:343` | RCON data startup | loads persisted configuration/state; loader fallback is owner-specific | corrupt data fixture |
| `plugins/airi_llm/memory.py:179` | memory startup | loads memory store and falls back on invalid pickle | corrupt memory fixture |
| `plugins/airi_llm/memory.py:215` | per-context memory read | loads context pickle; invalid context is skipped/recovered | corrupt context fixture |
| `plugins/airi_daily_check/base/persistence.py:33` | daily state startup | loads state pickle with fallback | corrupt state fixture |
| `plugins/airi_daily_check/base/persistence.py:91` | challenge state startup | loads challenge pickle and falls back/rebuilds | corrupt challenge fixture |
| `plugins/airi_daily_check/base/royal_road_bridge.py:21` | settlement receipt read | loads receipt value; invalid receipt must not be treated as delivered | corrupt receipt fixture |
| `plugins/airi_daily_check/base/cache.py:130` | image/cache startup | loads cache payload and falls back | corrupt cache fixture |

These are all direct `pickle.load`/restricted-unpickler call sites found by the repository-wide search. Reproduction is deterministic with a temporary truncated/non-pickle file at each configured path; no fixtures were retained.

### Clean-process plugin-load probe

Probe command:

```text
PYTHONPATH=/Users/liko/Documents/GitHub/AiriCore /opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_plugin_probe.py
```

The probe called `nonebot.init()`, registered `nonebot.adapters.onebot.v11.Adapter`, loaded `nonebot_plugin_localstore` then `nonebot_plugin_alconna`, and called `nonebot.load_plugins("plugins")`. Result: dependency-first loads succeeded; 35 plugins loaded successfully; `airi_security_monitor` failed with `RuntimeError: airi_security_monitor 仅支持 Linux，当前平台为 darwin`. The loaded set included the locally present `airi_game_server`; the top-level directory count remains 36. Captured lifecycle order begins `startup`, `shutdown`, then LLM/scheduler/state/cache/game/server handlers in registration order; the full hook list is retained in the command output, with repeated `_run_tests` hooks from plugin imports. The probe file was deleted after execution.

### `pyfairy_xiangqi` Ruff classification

`python -c 'import utils.pyfairy_xiangqi'` returned `IMPORT_OK`. Running the module through `runpy.run_path(..., run_name="__main__")` also exited 0 because line 5 dynamically executes `pyfairy_xiangqi_core.py`, which defines `main`. Therefore `utils/pyfairy_xiangqi.py:8` is a Ruff static-analysis false positive caused by dynamic `exec`, not a runtime/import defect. It remains a baseline lint finding until the implementation is refactored or lint-excluded.

## Fix report

No production fixes were made in Task 1. This revision only expands the audit report with complete inventories and clean-process evidence. The only changed artifact is this report; existing LLM worktree changes remain untouched.
