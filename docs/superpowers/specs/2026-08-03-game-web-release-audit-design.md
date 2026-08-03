# Game Web Release Audit Design

## Goal

Audit and correct the delivered Airi game-web changes as one release unit. The unit includes the Point Salad API adapter in `airi_game_server`, the shared authentication UI, the SEKAI and Point Salad source sites, their generated `prod` artifacts, their local obfuscator dependencies, and the content-hash update mechanism. The audit also corrects desktop and mobile UI layouts that obscure information, prevent a legal action, or make the current game state hard to understand.

## Scope

The audit covers these release surfaces:

- `plugins/airi_game_server/point_salad_api.py`, including service argument translation and group notification ordering.
- Shared Bot and email login source files, the SEKAI compatibility adapter, and their emitted production files.
- Point Salad room flow, legal action controls, polling, heartbeats, rendering, error recovery, and text rendering boundaries.
- SEKAI online-mode entry, authentication-event reentry, and legacy API compatibility.
- Both `build_prod.js` scripts, local `javascript-obfuscator` installation, source-to-prod copying, version computation, cache refresh, and release artifact parity.
- Desktop and mobile layouts for both sites, with emphasis on information hierarchy, touch targets, stable geometry, overflow, focus, and motion.

The audit does not change game rules, account identity semantics, the HTTPS-only deployment model, or the independent static-site deployment model.

## Audit Strategy

The selected approach is a contract-first release audit.

1. Establish contracts from the authoritative game service and existing SEKAI behavior. Verify each HTTP action preserves argument shape, authorization, turn checks, and group-message ordering.
2. Inspect browser source and generated artifacts for unsafe data insertion, lifecycle races, stale requests, missing version inputs, and source/prod divergence.
3. Correct confirmed issues in the smallest owning module. Rebuild both production directories only after source repairs.
4. Exercise the actual static entry pages and generated production pages at desktop and mobile viewports. Validate the paths a player can see: login, room recovery, room entry, turn changes, action feedback, cache update, and interrupted connectivity.

Static-only scanning is insufficient because obfuscation and version redirects can fail only in a browser. Browser-only testing is insufficient because it cannot prove server argument and group-notification contracts. The audit therefore requires both.

## Server And Browser Contracts

`point_salad_api.py` must translate web inputs into the exact command/service shapes used by the Bot. Center skill arguments must pass through the existing parser, and a two-item score-card action must retain its column plus slot meaning. Invalid inputs must result in the existing stable Chinese game error rather than an uncaught conversion error.

For a group-origin room, a successful browser action first sends the previous player's card-change message. It then checks the next player's current browser heartbeat and group membership. An active member receives `@xxx 轮到你了，请在网页端继续操作`; a non-active member receives the ordinary board and turn reminder; a player outside the origin group receives the board without an `@` mention. Web-origin rooms never send a group message.

The browser treats snapshots from 22319 as authoritative. It must serialize or safely discard overlapping refreshes, clear pending controls after failed actions, stop polling and heartbeats after logout or leave, and keep the latest known room recoverable after a temporary network failure. All externally sourced strings inserted into the DOM must use text nodes or escaped text, not interpolated HTML.

The shared authentication component must keep both source copies byte-identical. It must not create duplicate login modals, duplicate poll timers, or recursive online-mode entry when session refresh or authentication-state events repeat.

## UI Acceptance Rules

The table view must identify the current player, available action, market choice, selected cards, pending state, and connection state without relying on a transient toast alone. Only legal actions are enabled. A pending action has a stable disabled state and clears on both success and failure.

At desktop width, player information, the action area, and the market must remain visible without overlap. At mobile widths, the title art and top-right controls are centered or aligned intentionally, important controls have a minimum usable touch target, text wraps instead of clipping, and horizontally dense card content scrolls within its own region instead of widening the page. The layout must support keyboard focus and `prefers-reduced-motion` without breaking core actions.

Changes remain within the established visual language: no replacement game engine, landing page, or unrelated redesign.

## Versioning And Production Build Rules

Every publishable input contributes to the source and production `version.json` hash: HTML entry files, JavaScript, CSS, and every copied static asset. `version.json` itself is excluded to prevent a self-referential hash. Changing a card image or generated portrait must therefore force the entry-page redirect and cache-busted stylesheet and script URLs.

The production build operates only on explicit project-local source and destination paths. It may clear its explicit `prod` destination, then must reproduce all required runtime files. The build dependency stays in the project-local `.build_tools` directory and is not copied to the release folder. Obfuscated JavaScript retains every required public global and must pass syntax validation.

The entry page fetches `version.json` without cache, preserves the current path and URL fragment when switching to the new version query, and injects every runtime stylesheet and script with the resulting version query. A failed version fetch leaves the static page usable with a clear non-blocking fallback path.

## Verification

The final release gate requires:

- Python parsing, linting, focused API contract checks, and an Airi game-server route smoke test.
- JavaScript syntax checks for all source and production bundles, plus source/prod authentication parity checks.
- Rebuilt production folders and a manifest comparison confirming expected runtime files, asset copying, and equal source/prod versions.
- Browser checks for both source sites and Point Salad production at desktop and mobile sizes: version redirect, asset load, shared login modal, Bot/email method switch, modal close, focus behavior, no horizontal page overflow, and no console errors.
- Point Salad interactive checks using representative room snapshots: lobby, legal and illegal action state, pending state, connection recovery, turn indicator, and responsive action controls.
- Cleanup of temporary scripts, screenshots, preview caches, bytecode, and test-only files.

## Project Memory

After the verified repairs, project memory records a single operational update procedure: modify source and assets, run each `node build_prod.js`, deploy only `web_prod/` for SEKAI and `prod/` for Point Salad, confirm served `version.json`, open a stale version URL to verify redirect, and run the browser smoke checklist. The memory also records that assets participate in the content hash and that source changes alone are not a deployable release.
