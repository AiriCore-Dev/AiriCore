# LLM Profile Hot Switch and Utils Consolidation Design

## Goal

Move all LLM source configuration out of `.env.prod`, centralize every LLM API call in `utils`, add persistent hot switching through `airiccswitch <profile>`, and consolidate utility modules that share one responsibility.

## Scope

The change covers:

- LLM profile storage, parsing, validation, activation, persistence, switching, client lifetime, model fallback, usage statistics, and shutdown.
- Airi chat, structured chat mechanisms, RCON translation, turtle soup, wish bottle moderation, and Kokomi natural-language queries.
- Deployment configuration, example configuration, documentation, and migration from the existing `.env.prod` values.
- Consolidation of related utility modules without combining modules that only have superficial similarities.

The change does not alter prompts, token budgets, temperatures, plugin business rules, or existing failure fallbacks.

## Profile Storage

Profiles live in `data/LLM/` and use the name `<profile>.conf`.

- `default.conf` contains the values migrated from the current `.env.prod` and is ignored by Git.
- `example.conf` contains safe placeholders and is tracked by Git.
- `active` contains only the active profile name and is ignored by Git.
- If `active` is missing, startup selects `default`.
- If `default.conf` is missing, startup copies `example.conf` to `default.conf` before loading it.

The deployment wizard creates or updates `default.conf`. It no longer writes LLM credentials or model names into `.env.prod`.

Each profile uses this shape:

```ini
base_url = https://api.example.com/v1
token = sk-xxxxxxxx

chat_model = gemini-3.7-flash
chat_text_model = gemini-3.7-flash
chat_fallback = gemini-3.6-flash, gemini-3.5-flash

other_model = gemini-3.7-flash
other_fallback = gemini-3.6-flash, gemini-3.5-flash
```

The parser accepts blank lines, `#` and `;` comments, optional single or double quotes, arbitrary whitespace around `=`, case-insensitive keys, comma-separated model lists, and legacy bracketed lists. Unknown keys produce a Chinese warning. Missing `base_url`, `token`, or `chat_model` makes the profile invalid.

Profile names may contain Chinese characters, Latin characters, digits, spaces, underscores, dots, and hyphens, but cannot equal `.` or `..` and cannot contain path separators. Commands accept a profile stem without the `.conf` suffix.

## Environment Migration

The following keys are removed from both `.env.prod` and `.env.prod_example`:

- `llm_api_key`
- `llm_base_url`
- `chat_llm_model`
- `chat_llm_model_text`
- `chat_llm_model_fallback`
- `other_llm_model`
- `other_llm_model_fallback`

LLM-adjacent settings such as bot whitelist, group blacklist, character name, aliases, and alias exclusions remain in `.env.prod`.

The deployment wizard, English deployment guide, Chinese deployment guide, and other references to the removed keys are updated to point to `data/LLM/default.conf`.

## Unified LLM Runtime

`utils/llm.py` becomes the only module allowed to import `AsyncOpenAI`, create an OpenAI client, or call `chat.completions.create`.

It owns:

- Immutable parsed profile values.
- Active and retired runtime generations.
- Client acquisition and release.
- Persistent profile selection.
- Chat, structured output, and auxiliary model calls.
- Model fallback and unavailable-model cooldown state.
- Usage source constants, counters, persistence, and query snapshots.
- Startup initialization and shutdown cleanup.

The public surface includes operations equivalent to:

- Initialize the runtime from the persisted selection.
- List profiles and inspect the active profile without exposing the full token.
- Switch profiles.
- Call Airi chat with automatic vision or text model selection.
- Call structured Airi mechanisms.
- Call auxiliary LLM features with optional output validation.
- Read usage statistics and unavailable-model snapshots.
- Flush statistics and close clients during shutdown.

Plugins retain prompt construction and business-specific result handling, but no plugin owns an LLM client, reads LLM source configuration, selects a model chain, or performs an API request.

## Hot-Switch Semantics

Each LLM call acquires a snapshot of the current runtime generation. Switching performs these steps under a shared switch lock:

1. Resolve and validate the requested profile name.
2. Read and fully parse the target profile.
3. Create the replacement client and runtime generation without issuing a network request.
4. Persist the requested profile name through temporary-file replacement.
5. Atomically replace the active generation.
6. Clear unavailable-model cooldown records inherited from the previous source.
7. Retire the previous generation.

Calls acquired before the swap continue using the previous generation. Calls acquired after the swap use the new generation immediately. A retired client closes when its final in-flight call releases it. Repeated switching therefore neither interrupts active calls nor leaks clients.

If parsing, validation, client creation, or persistence fails, the active generation remains unchanged. Concurrent switch commands execute serially, and the last successful command determines the active profile.

## Command Behavior

`airiccswitch` is registered in `airi_switch` with `SUPERUSER` permission.

- `airiccswitch <profile>` switches to that profile.
- `airiccswitch` reports the active profile and available profiles.
- Success output includes the profile name, Base URL, chat model, text model, and auxiliary model.
- Token output is always masked.
- Missing files, invalid names, invalid fields, and persistence failures return Chinese messages and do not change the active profile.

The command does not probe the remote service. Authentication and model availability remain part of normal calls and fallback handling.

## Preserved Failure Contracts

- Airi chat returns an empty string when every model fails.
- Structured Airi mechanisms return `None` when every model or parse attempt fails.
- RCON translation returns the original text when every model fails.
- Turtle soup propagates the final exception to its existing handling layer.
- Wish bottle moderation treats total failure as prohibited content.
- Kokomi natural-language queries return their existing error tuple structure.

Existing fallback order, JSON retry behavior, output validation, model-down TTL, and successful-call statistics remain behaviorally compatible.

## Utils Consolidation

The final utility layout follows responsibility boundaries:

| Module | Result |
|---|---|
| `utils/llm.py` | Absorbs `utils/llm_fallback.py`, `utils/llm_usage.py`, `plugins/airi_llm/llm_client.py`, and every direct plugin LLM API call. |
| `utils/observability.py` | Absorbs `utils/loop_monitor.py` and `utils/plugin_logger.py`. |
| `utils/messaging.py` | Absorbs `utils/notification.py` and `utils/uniseg_target.py`. |
| `utils/pyfairy_xiangqi.py` | Absorbs `utils/pyfairy_xiangqi_core.py` while retaining the executable UCCI entry point. |
| `utils/cache.py` | Remains unchanged as the existing consolidated cache module. |
| `utils/email.py` | Remains unchanged as the existing consolidated mail and template module. |
| `utils/network.py` | Remains independent for SSRF protection, DNS pinning, and guarded downloads. |
| `utils/onebot_query.py` | Remains independent for OneBot query caching, event observation, and adapter interception. |
| `utils/totp_2fa.py` | Remains independent for authentication algorithms and its command-line tool. |
| `utils/fontconfig.py` | Remains independent for Linux startup environment compatibility. |

Imports are migrated directly to the surviving modules. Compatibility shim files are not retained after all in-repository consumers are updated.

## Verification

Implementation follows test-first red-green cycles using temporary tests that are deleted after verification in accordance with project policy.

Coverage includes:

- Tolerant profile parsing, comments, quoting, both list syntaxes, unknown keys, missing required values, Chinese names, and path traversal rejection.
- Default selection, active-profile persistence, restart restoration, atomic write failure, and invalid-switch rollback.
- Concurrent switch serialization.
- Runtime generation acquisition, old-request completion, immediate new-request switching, and retired-client closure.
- Text versus vision model selection, fallback order, JSON retry and parsing, auxiliary validation, and cooldown reset after switching.
- All six plugin-level failure contracts.
- Deployment wizard creation and update of `default.conf` without writing LLM secrets into `.env.prod`.
- Static repository checks proving that `AsyncOpenAI` and `chat.completions.create` exist only in `utils/llm.py`.
- Absence of imports from deleted modules.
- Messaging and observability API compatibility.
- UCCI engine startup and handshake after the engine merge.
- `compileall`, existing applicable tests, all-plugin loading, and one real API smoke call through the active default profile.

After code verification, plugin directory mtimes are synchronized after cache cleanup and checked twice for idempotence. Temporary scripts and results are removed. Project memory files and the `MEMORY.md` index are updated with the final architecture and verification evidence.
