# AiriCore Coordination Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit the full AiriCore codebase, fix evidence-backed defects, and establish consistent cross-plugin coordination for task lifecycle, Bot selection, shared state, persistence, and error propagation.

**Architecture:** Add a thin coordination utility layer that wraps existing NoneBot patterns without introducing a new event bus. Migrate only the highest-impact call sites after contract tests prove the shared behavior, then address independently reproduced bugs and measurable algorithm/resource hotspots.

**Tech Stack:** Python 3.11, NoneBot 2.5, OneBot V11, asyncio, APScheduler, pytest/unittest, Ruff, pickle-based existing persistence.

**Spec:** `docs/superpowers/specs/2026-08-27-airicore-coordination-audit-design.md`

## Global Constraints

- Preserve existing uncommitted LLM changes and do not reset or overwrite them.
- Keep “桃井爱莉” intact; otherwise use `AiriCore` or `Airi`; never create mixed forms such as “桃井Airi”.
- User-visible text remains Chinese; code adds no docstrings or comments.
- NoneBot dynamic tests use `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python` directly.
- NoneBot tests run `nonebot.init()`, register OneBot V11, load dependency plugins before target plugins, and do not import a plugin package before `load_plugin`.
- Every production fix starts with a failing test that is observed failing for the intended reason.
- Do not retain temporary test scripts or generated verification artifacts after validation.
- Synchronize modified plugin directory mtimes after all compilation and cache cleanup, and verify the second sync changes zero directories.
- Update the relevant memory file and `MEMORY.md` index after implementation.

## File Map

- Create: `utils/coordination.py` for task registration, cancellation, and shared operation context.
- Modify: `utils/messaging.py` to expose the coordination layer's Bot selection and fallback behavior without breaking current callers.
- Modify: `bot.py` to initialize and shut down registered tasks in the driver lifecycle.
- Modify: high-impact plugin entrypoints that currently call bare `asyncio.create_task` or scan `nonebot.get_bots()` directly, beginning with `airi_llm`, `airi_market`, `airi_point_salad`, `airi_new_group`, and `airi_switch`.
- Modify: persistence modules only where a reproduced load/flush/rollback defect is confirmed.
- Create temporarily then remove: focused regression tests under a temporary test directory or existing test location, depending on the discovered test layout.
- Create/update: `memory/airicore-coordination-audit-2026-08-27.md` and the index entry in `MEMORY.md`.

### Task 1: Establish runtime and repository audit baseline

**Files:**
- Read: `bot.py`, `utils/*.py`, `plugins/**/*.py`, `requirements.txt`, deployment scripts.
- Test output only: temporary files outside the repository.

**Interfaces:**
- Produces a checked runtime command, plugin count, import/load results, static findings, and a prioritized issue ledger for later tasks.

- [ ] **Step 1: Locate the required Python runtime and confirm dependencies**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python --version
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -c "import nonebot, aiohttp, httpx, PIL; print('deps-ok')"
```

Expected: Python 3.11.x and `deps-ok`.

- [ ] **Step 2: Run baseline static checks**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m compileall -q bot.py utils plugins
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/ruff check --select E9,F63,F7,F82 bot.py utils plugins
git diff --check
```

Expected: exit code 0 for each command; record any pre-existing failures without modifying them in this step.

- [ ] **Step 3: Build the coordination issue ledger**

Run targeted searches for `asyncio.create_task`, lifecycle decorators, direct `get_bots()`, cross-plugin imports, blocking I/O, pickle loads, and unbounded loops. Record each hit with trigger, owning module, cross-module impact, and whether it is reproducible.

- [ ] **Step 4: Commit baseline notes**

```bash
git status --short
git commit --allow-empty -m "chore: record coordination audit baseline"
```

### Task 2: Add and verify the task lifecycle coordination contract

**Files:**
- Create: `utils/coordination.py`
- Modify: `bot.py`
- Test: temporary focused coordination tests, removed after validation

**Interfaces:**
- Produces `TaskRegistry.create(coro, *, owner, key=None) -> asyncio.Task`, `TaskRegistry.cancel_all() -> Awaitable[None]`, `TaskRegistry.snapshot() -> tuple[TaskInfo, ...]`, and module-level `registry`.
- `TaskInfo` exposes immutable `owner` and `key` values for diagnostics.

- [ ] **Step 1: Write the failing contract tests**

Cover task registration, completed-task removal, exception logging without unhandled-task warnings, idempotent cancellation, and cancellation propagation. Assert that a task created through the registry is absent from `snapshot()` after completion and after shutdown cancellation.

- [ ] **Step 2: Run the focused tests and verify the expected failure**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest <temporary-test-file> -q
```

Expected: import or attribute failures because the registry contract does not yet exist.

- [ ] **Step 3: Implement the minimal registry**

Use a lock-free event-loop-owned set of task records, attach a done callback that removes the task and consumes non-cancellation exceptions through the shared logger, and make `cancel_all()` cancel then await a snapshot with `return_exceptions=True`.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run the same command. Expected: all lifecycle contract tests pass with no asyncio warning output.

- [ ] **Step 5: Wire driver shutdown and commit**

Register a shutdown hook in `bot.py` that awaits `registry.cancel_all()` before other flush operations that depend on background tasks. Run compileall and commit:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m compileall -q utils/coordination.py bot.py
git add bot.py utils/coordination.py
git commit -m "feat: coordinate background task lifecycle"
```

### Task 3: Unify cross-plugin Bot selection and fallback messaging

**Files:**
- Modify: `utils/messaging.py`
- Modify: direct multi-Bot senders identified in `airi_new_group`, `airi_market`, `airi_point_salad`, `airi_mcrcon`, and `airi_switch` only when their current behavior is covered by tests.
- Test: focused messaging contract tests, removed after validation

**Interfaces:**
- Produces `select_bot(bots, configured_account, *, preferred=None) -> Optional[Bot]` and `send_group_with_fallback(message, *, group_id, preferred=None, configured_account=None, bots=None, tag="群消息") -> SendResult`.
- `SendResult` records `sent`, `bot_id`, and `error` without exposing mutable internal collections.

- [ ] **Step 1: Write failing tests for deterministic Bot selection**

Test configured account priority, preferred live Bot priority, stable sorted fallback, empty registry, and a failed first send followed by one fallback attempt. Assert no duplicate sends and that the returned result identifies the successful Bot or the final error.

- [ ] **Step 2: Run tests and observe the expected failure**

Expected: missing `select_bot` or `send_group_with_fallback` symbols.

- [ ] **Step 3: Implement minimal selection and fallback**

Normalize all Bot keys to strings, prefer an explicitly live Bot when present, then configured account, then stable sorted key. Attempt each eligible Bot at most once, keep the last exception, and return a structured result.

- [ ] **Step 4: Run tests and verify green**

Expected: all messaging contract tests pass.

- [ ] **Step 5: Migrate one call site at a time and commit**

Replace direct registry scans only where behavior is equivalent, preserving message payloads and existing lock boundaries. Run each plugin's focused test after migration, then commit:

```bash
git add utils/messaging.py plugins/airi_new_group plugins/airi_market plugins/airi_point_salad plugins/airi_mcrcon plugins/airi_switch
git commit -m "refactor: unify cross-plugin bot messaging"
```

### Task 4: Migrate high-impact background tasks and validate lifecycle isolation

**Files:**
- Modify: `plugins/airi_llm/__init__.py`
- Modify: `plugins/airi_market/__init__.py`
- Modify: `plugins/airi_point_salad/service.py`
- Modify: `plugins/nonebot_plugin_meme_stickers/__init__.py`
- Modify: `utils/onebot_query.py` and `utils/observability.py` only where registry ownership is unambiguous.
- Test: focused task-isolation tests, removed after validation

**Interfaces:**
- Consumes `utils.coordination.registry.create` from Task 2.
- Produces owner-tagged tasks that are cancelled on shutdown/disconnect and do not leak across replaced games, groups, or Bot instances.

- [ ] **Step 1: Write failing lifecycle regression tests**

Cover replacing a Point Salad room, cancelling a passive Airi response, disconnecting a Bot during an OneBot query refresh, and stopping observability. Assert the old task cannot mutate the new state and registry snapshots return to baseline.

- [ ] **Step 2: Run focused tests and observe failure**

Expected: old tasks remain pending or can still call the replaced state because current call sites use bare `asyncio.create_task`.

- [ ] **Step 3: Migrate minimal call sites**

Use owner strings such as `airi_llm`, `airi_point_salad:<group_id>`, `onebot_query:<bot_id>`, and `observability`. Preserve existing task cancellation semantics and do not hold business locks while awaiting cancellation.

- [ ] **Step 4: Run focused tests and verify green**

Expected: replaced states remain isolated, cancellation is observed, and registry snapshots are empty or at the documented steady state.

- [ ] **Step 5: Commit**

```bash
git add plugins/airi_llm plugins/airi_market plugins/airi_point_salad plugins/nonebot_plugin_meme_stickers utils/onebot_query.py utils/observability.py
git commit -m "fix: isolate plugin background task lifecycles"
```

### Task 5: Audit and fix reproduced coordination bugs and algorithm hotspots

**Files:**
- Modify only the modules named by the issue ledger, expected candidates include `plugins/airi_turtle_soup`, `plugins/airi_mcrcon`, `plugins/airi_daily_check`, `plugins/airi_wish_bottle`, `plugins/nonebot_plugin_boardgame`, `plugins/nonebot_plugin_minesweeper`, `plugins/nonebot_plugin_cchess`, `plugins/airi_llm/memory.py`, and persistence modules.
- Test: one regression test per confirmed issue, removed after validation unless it belongs to the existing permanent suite.

**Interfaces:**
- Consumes coordination contracts from Tasks 2-4 where applicable.
- Produces behavior-preserving fixes with explicit evidence for each trigger and a before/after complexity or resource measurement for optimizations.

- [ ] **Step 1: Reproduce the highest-impact ledger item**

Construct the smallest scenario that triggers one issue, such as concurrent finalization, cross-group state mutation, lock-held network wait, duplicate Bot sends, malformed persistence, or an unbounded/degenerate game loop. Capture the failing assertion and relevant logs.

- [ ] **Step 2: Write and run the regression test before changing production code**

The test must fail for the identified behavior and pass unchanged after the fix. Do not combine unrelated findings in one test.

- [ ] **Step 3: Trace the root cause and implement one minimal fix**

Keep lock scope around validation/commit only, move external I/O outside locks, make cancellation propagate, bound loops and retries, preserve old persistence formats, and avoid adding broad catches that hide errors.

- [ ] **Step 4: Measure algorithm/resource impact when applicable**

Use a deterministic input and record runtime, allocations, task count, or complexity before and after. Reject an optimization that changes behavior without a measurable or provable benefit.

- [ ] **Step 5: Run the regression and affected plugin checks, then commit each coherent fix**

Use focused airidev NoneBot loading where required and commit each issue separately with a message naming the behavior fixed.

### Task 6: Full coordination verification, cleanup, and memory update

**Files:**
- Read/verify: all modified source files, `requirements.txt`, deployment scripts.
- Create/update: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airicore-coordination-audit-2026-08-27.md`
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/MEMORY.md`

**Interfaces:**
- Consumes all fixes and contracts from Tasks 1-5.
- Produces final evidence, residual-risk list, and durable project memory.

- [ ] **Step 1: Run full static verification**

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m compileall -q bot.py utils plugins
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/ruff check --select E9,F63,F7,F82 bot.py utils plugins
git diff --check
```

- [ ] **Step 2: Run the NoneBot plugin loading smoke test**

Use a temporary script with `nonebot.init()`, `driver.register_adapter(OB11Adapter)`, dependency-first loading, and `load_plugins("plugins")`. Record all loaded and failed modules, then remove the script.

- [ ] **Step 3: Run coordination and regression checks**

Verify task registry baseline after shutdown, no pending task warnings, deterministic Bot fallback, lock release after exceptions/cancellation, persistence recovery, and no cross-group/Bot state contamination.

- [ ] **Step 4: Remove temporary tests and generated artifacts**

Delete only files created for this audit, then re-run compileall so no temporary bytecode or caches affect the result.

- [ ] **Step 5: Synchronize plugin directory mtimes**

Run the repository's documented mtime synchronization procedure after compilation and cache cleanup; repeat it and require `changed dirs: 0`.

- [ ] **Step 6: Update memory and commit durable audit notes**

Record modified files, confirmed bugs, coordination contracts, commands and results, unresolved environmental limits, and residual risks. Update the index, then commit documentation separately.

- [ ] **Step 7: Final verification before completion claim**

Re-run the complete verification commands from Steps 1-3 after the final commit and report exact exit codes, plugin counts, test counts, and any checks that could not run.
