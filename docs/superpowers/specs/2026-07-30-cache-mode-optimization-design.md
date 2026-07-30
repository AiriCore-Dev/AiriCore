# Cache Mode Optimization Design

## Problem

The three global cache modes do not currently optimize for the same resource cost:

- `ram` eagerly loads the full preload catalog and removes in-process limits. The current catalog contains about 3.23 GB of decoded Kokomi arrays, while an existing tarot pickle can add about 513 MB of base64 strings. The resulting memory pressure makes requests slower than `balanced`.
- `balanced` limits several caches by entry count. A single large image or array can therefore consume more memory than dozens of small assets.
- `disk` avoids retained Python cache state, but tarot upright images are still decoded and re-encoded on every request even though their source bytes can be sent directly.
- Derived base64 pickle caches can grow without a useful bound. The current tarot cache is a concrete example.

The design preserves the public `ram / balanced / disk` configuration while making resource admission and accounting predictable.

## Goals

1. Make the `ram` preload budget a hard upper bound for resources admitted by the preload coordinator.
2. Keep the `ram` working set fast by prioritizing small, high-frequency assets and excluding cold, high-cost groups from startup preload.
3. Make `balanced` memory limits byte-based across images, NumPy arrays, fonts, decoded products, and base64 strings.
4. Keep `disk` free of retained Python cache entries and remove avoidable transformation work.
5. Bound derived persistent caches and safely converge oversized legacy files.
6. Preserve file-signature invalidation, shared-read-only image semantics, and existing plugin output.

## Non-goals

- No runtime cache-mode switching; mode selection remains restart-scoped.
- No new external cache service or dependency.
- No cache of mutable consumer-owned images.
- No deletion of user state databases or source assets.
- No learning model or cross-process frequency database.

## Architecture

### Shared cache policy

Add a small policy layer in `utils/cache_mode.py` for byte budgets and cache accounting. Mode-specific modules continue to own serialization and resource decoding, but use shared helpers for admission, byte estimation, and counters. The first iteration uses documented internal defaults; it does not add more environment keys.

Each bounded in-process cache tracks:

- key and source signature;
- estimated resident bytes;
- last access order;
- hit, miss, eviction, and admission-skip counters.

RAM mode has no ordinary LRU eviction after admission, but preload admission is still bounded by the configured hard budget. Balanced mode evicts least-recently-used entries until the cache's byte budget is satisfied. Disk mode bypasses all Python cache containers.

### Mode behavior

#### `ram`

`utils/cache_preload.py` becomes a budget-aware coordinator:

1. Build a catalog with file size, estimated decoded size, loader type, and priority.
2. Reject an item before loading if its estimate cannot fit the remaining budget.
3. Load high-priority small assets first.
4. Exclude known cold groups from startup preload: Kokomi large backgrounds, all `dog_tag_*` groups, tarot card collections, and other groups whose decoded footprint is disproportionate to request frequency.
5. Record admitted, skipped, estimated, and actual bytes in the summary.

The coordinator reconciles actual resident bytes after each load. If decoding expands beyond the estimate, the item is removed from the cache before the next item is admitted. The total resident bytes reported by the coordinator never exceeds the configured budget by an unaccounted item.

The mode remains fast for repeatedly used assets because admitted resources stay resident. Cold resources load through the normal cache API when first requested. An on-demand item that cannot fit the remaining RAM budget is served without admission, so the hard limit remains effective.

#### `balanced`

Use separate byte budgets for shared images, Kokomi arrays, daily-check decoded products, fonts, and base64 values. Defaults are conservative and configurable through the existing environment configuration; each cache retains its own namespace so a large image cannot evict unrelated metadata.

Admission uses a small probationary LRU rule: the first access may be served without permanent admission when the cache is under pressure, while repeated accesses are promoted. This prevents one-off large resources from displacing frequently reused assets. Existing signature checks remain authoritative before a hit is returned.

#### `disk`

All Python-level resource caches return a fresh value from source or persistence on each call and do not mutate cache dictionaries or write cache pickle files. Existing user-facing behavior and error fallbacks remain unchanged.

## Persistent cache policy

### Tarot

`plugins/nonebot_plugin_tarot/cache.py` changes as follows:

- Upright cards read source bytes and base64-encode them directly.
- Reversed cards continue to rotate and encode through PIL.
- Persistent entries carry signature, value, timestamp, and byte length.
- A bounded byte budget and entry cap prevent unbounded growth.
- Legacy entries remain readable when valid. During access or flush, stale and over-budget entries are removed oldest-first, and the file is atomically replaced.
- Startup preload does not import or deserialize the tarot pickle. The coordinator reports its file size as skipped persistent data, preventing a large legacy pickle from entering RAM just to count entries.

The source card images remain authoritative, so removing derived cache entries is recoverable and does not delete user data. If a legacy tarot pickle exceeds the persistent byte cap, it is ignored rather than deserialized and is atomically replaced with a compact file on the next successful write.

### Other pickle caches

Apply the same byte-aware purge discipline to daily-check products, whateat base64, avatars, market articles, and switch metadata where their existing schemas permit it. Existing TTLs and file signatures remain unchanged. Flush remains atomic and failure-tolerant.

## Diagnostics

Extend `airiram` cache details with resident bytes and counters for each bounded cache. The preload section reports:

- configured budget;
- estimated and actual admitted bytes;
- skipped groups and reasons;
- cache hits, misses, admissions, and evictions.

Logs remain Chinese and report when a group is skipped or a legacy persistent cache is compacted.

## Error handling and compatibility

- Missing or unreadable assets continue to return the existing `None`/fallback behavior.
- Decode failures never poison an existing valid entry.
- Cache-file corruption resets only that cache and logs a warning.
- Legacy pickle entries are accepted when their shape and signature are valid; malformed entries are discarded individually.
- Atomic temporary-file replacement remains in use for all writes.
- Shared cached images remain read-only; callers that mutate images continue using copy APIs.

## Verification plan

Add focused tests before implementation for:

1. `ram` preload admission never exceeds its byte budget, skips cold groups, and reports actual bytes.
2. `balanced` evicts by resident bytes rather than item count and preserves recently reused entries.
3. `disk` leaves cache containers empty and performs fresh reads.
4. File-signature changes invalidate image, array, base64, and derived-product entries.
5. Tarot upright output equals direct source base64; reversed output remains pixel-equivalent to the current rotation path.
6. Oversized legacy tarot data is compacted without touching source assets.
7. Existing image rendering, copy isolation, TTL, and plugin-loading checks remain green.

Performance verification will compare repeated representative requests under each mode and record wall time, process RSS, cache hit rate, and eviction/admission counts. The acceptance criterion is that `ram` no longer exceeds its configured resident budget and its representative request latency is no worse than `balanced` because of memory pressure.
