# Cache Mode Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ram`, `balanced`, and `disk` cache modes predictable under memory pressure while preserving existing plugin output and cache invalidation behavior.

**Architecture:** Add reusable byte-aware LRU and admission accounting in `utils/cache_policy.py`, expose mode budgets through `utils/cache_mode.py`, and migrate shared assets, Kokomi arrays, daily-check decoded products, and tarot derived data to the policy. Startup preload will estimate decoded costs, skip cold groups, and enforce a hard budget before loading.

**Tech Stack:** Python 3, Pillow, NumPy, pickle, unittest/pytest-compatible tests.

---

### Task 1: Add failing policy tests

**Files:**
- Create: `tests/test_cache_policy.py`

- [ ] **Step 1: Write tests for weighted LRU and admission**

```python
from utils.cache_policy import ByteLRU


def test_byte_lru_evicts_oldest_entries_until_budget_fits():
    cache = ByteLRU(10)
    cache.put("a", "A", 6)
    cache.put("b", "B", 4)
    assert cache.get("a") == "A"
    cache.put("c", "C", 7)
    assert cache.get("a") == "A"
    assert cache.get("b") is None
    assert cache.get("c") == "C"
    assert cache.bytes == 10


def test_byte_lru_rejects_single_entry_larger_than_budget():
    cache = ByteLRU(10)
    assert cache.put("large", "x", 11) is False
    assert len(cache) == 0
    assert cache.bytes == 0


def test_probationary_admission_requires_second_observation():
    cache = ByteLRU(10, probationary=True)
    assert cache.put("cold", "C", 4) is False
    assert cache.get("cold") is None
    assert cache.put("cold", "C", 4) is True
    assert cache.get("cold") == "C"


def test_byte_lru_replacement_updates_resident_bytes():
    cache = ByteLRU(10)
    cache.put("key", "A", 4)
    cache.put("key", "B", 7)
    assert cache.bytes == 7
    assert cache.get("key") == "B"
```

- [ ] **Step 2: Run tests and verify the missing policy fails**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest tests/test_cache_policy.py -q`

Expected: collection fails because `utils.cache_policy` does not exist.

### Task 2: Implement shared byte policy

**Files:**
- Create: `utils/cache_policy.py`
- Modify: `utils/cache_mode.py`
- Test: `tests/test_cache_policy.py`

- [ ] **Step 1: Implement `ByteLRU` with byte accounting, LRU eviction, optional probationary admission, and counters**

`ByteLRU` stores `(value, cost)` in an `OrderedDict`, tracks `bytes`, `hits`, `misses`, `evictions`, `admissions`, and `skips`, removes old entries until the new entry fits, rejects entries larger than the limit, and bounds its probation set to the same key budget.

- [ ] **Step 2: Add mode-specific byte budgets to `utils/cache_mode.py`**

Add internal defaults for shared images, Kokomi arrays, base64 values, decoded daily-check products, and fonts. Add `get_cache_budget_bytes(kind)` and `get_cache_stats()` helpers without adding environment keys.

- [ ] **Step 3: Run policy tests and verify they pass**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest tests/test_cache_policy.py -q`

Expected: all policy tests pass.

### Task 3: Migrate shared image, font, and base64 caches

**Files:**
- Modify: `utils/asset_cache.py`
- Create: `tests/test_asset_cache_modes.py`

- [ ] **Step 1: Write failing tests for byte limits and disk isolation**

Use temporary PNG and binary files, force `cache_mode._mode` between `balanced` and `disk`, and assert image cache bytes stay within the policy budget, oversized values are not retained, and disk reads leave `_images`, `_fonts`, and `_b64` empty.

- [ ] **Step 2: Migrate `asset_cache` containers to `ByteLRU`**

Use decoded RGBA bytes for image cost, encoded string length for base64 cost, and a bounded font estimate. Keep signature-aware invalidation, copy semantics, and existing `get_image`, `get_image_copy`, `get_font`, and `get_b64` signatures.

- [ ] **Step 3: Run asset tests and verify they pass**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest tests/test_asset_cache_modes.py -q`

Expected: all asset mode tests pass.

### Task 4: Bound Kokomi and daily-check decoded memory

**Files:**
- Modify: `plugins/airi_kokomi_wows/cache.py`
- Modify: `plugins/airi_daily_check/base/cache.py`
- Create: `tests/test_plugin_cache_limits.py`

- [ ] **Step 1: Write failing tests for array and decoded-product byte eviction**

Create small temporary images/encoded products, populate each cache with entries whose total decoded bytes exceed the configured budget, and assert the oldest entry is evicted while a recently accessed entry survives. Assert RAM mode no longer admits an item that would exceed the preload budget.

- [ ] **Step 2: Migrate Kokomi arrays to byte-based LRU**

Use `numpy.ndarray.nbytes` as the resident cost, retain signature checks and defensive copies, and replace the fixed item cap with the shared array byte budget.

- [ ] **Step 3: Migrate daily-check `_images` and `_decoded` to byte-based LRU**

Use RGBA pixel bytes for images and `_value_bytes` for decoded products. Preserve persistence namespaces, TTLs, version invalidation, copy discipline, and disk no-op behavior. Track font entries through the shared font budget.

- [ ] **Step 4: Run plugin cache tests and verify they pass**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest tests/test_plugin_cache_limits.py -q`

Expected: all plugin cache limit tests pass.

### Task 5: Fix tarot derived-cache growth and transformation cost

**Files:**
- Modify: `plugins/nonebot_plugin_tarot/cache.py`
- Create: `tests/test_tarot_cache.py`

- [ ] **Step 1: Write failing tests for direct upright encoding and legacy-size protection**

Assert upright output equals `base64://` plus source bytes, reversed output decodes to a 180-degree rotation, and an oversized existing pickle is not deserialized during module initialization/preload.

- [ ] **Step 2: Implement bounded tarot persistence**

Read upright source bytes directly; keep PIL rotation only for reversed cards. Add a persistent byte cap and entry cap, reject malformed entries individually, skip oversized legacy files before `pickle.load`, and atomically replace the cache with a compact payload on the next successful write. Preserve signatures and existing public functions.

- [ ] **Step 3: Run tarot tests and verify they pass**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest tests/test_tarot_cache.py -q`

Expected: all tarot tests pass.

### Task 6: Make startup preload budget-aware

**Files:**
- Modify: `utils/cache_preload.py`
- Modify: `plugins/airi_switch/ram_inspector.py`
- Create: `tests/test_cache_preload.py`

- [ ] **Step 1: Write failing tests for pre-load estimates, cold-group exclusion, and hard budget**

Patch temporary asset groups/loaders and assert no loader runs when the estimated cost cannot fit, excluded Kokomi and tarot groups are not loaded, and the summary reports estimated, actual, skipped, and reason fields without exceeding the configured budget.

- [ ] **Step 2: Implement catalog estimates and admission**

Add file-header estimates for decoded images/arrays, order groups by priority and cost, remove tarot from `_PK_CACHES`, exclude known cold groups, pass remaining budget to providers, and reconcile actual loaded bytes after each item. Keep background startup behavior unchanged.

- [ ] **Step 3: Expose policy counters and preload reasons through `airiram`**

Read cache policy summaries without holding locks across formatting and append per-cache resident bytes, hit/miss, eviction, admission, and skip details to existing forward-message nodes.

- [ ] **Step 4: Run preload tests and verify they pass**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest tests/test_cache_preload.py -q`

Expected: all preload tests pass.

### Task 7: Full regression and memory record

**Files:**
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/cache-mode-config.md`
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/cache-preload-and-balanced-rollout.md`
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/MEMORY.md`

- [ ] **Step 1: Run focused cache tests**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest tests/test_cache_policy.py tests/test_asset_cache_modes.py tests/test_plugin_cache_limits.py tests/test_tarot_cache.py tests/test_cache_preload.py -q`

Expected: all focused tests pass.

- [ ] **Step 2: Run syntax and plugin-load checks**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m compileall -q utils plugins`

Expected: exit code 0.

- [ ] **Step 3: Run the repository's available smoke checks**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest -q`

Expected: no test failures; if no repository tests are discovered, record that fact and rely on focused tests plus compile/load checks.

- [ ] **Step 4: Update cache memory records**

Record the final byte budgets, preload exclusions, tarot migration behavior, and verification results in the cache memory files and add the new entry to `MEMORY.md`.

- [ ] **Step 5: Inspect diff and report only verified outcomes**

Run: `git diff --check` and `git status --short`

Expected: no whitespace errors; unrelated pre-existing modifications remain untouched.
