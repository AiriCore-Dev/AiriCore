# Airi Game Server And Point Salad Web Design

## Goal

Create `airi_game_server` as the only AiriCore plugin listening on port 22319. It provides HTTPS APIs for the existing SEKAI roguelike and Point Salad. Add a static JavaScript Point Salad client in `airi_point_salad_web`, and update the existing `airi_asia_rougelike` client to use the new server without changing gameplay, content, or visual design.

The first release supports only SEKAI and Point Salad. The server structure must allow additional games to register later without moving their game rules into a shared network layer.

## Scope And Boundaries

`airi_game_server` owns:

- Uvicorn lifecycle, HTTPS validation, port 22319, CORS, common JSON responses, rate limiting, and request logging.
- QQ identity, Bot verification, email verification, signed web sessions, browser heartbeats, and room-code authorization.
- API adapters for `/api/sekai/*` and `/api/point-salad/*`.

`airi_daily_check` retains its Bot-side SEKAI entry points. Its current web API, authentication, persistence, and rate-limiting responsibilities move to the new plugin.

`airi_point_salad` retains its rules, scoring, state machine, persistence, Bot commands, rendering, and group-message behavior. It exposes a narrow service adapter to the game server so group commands and browser requests mutate the same authoritative game state.

`airi_asia_rougelike` remains a separately deployed static site. Its work is limited to the new API base and compatibility cleanup.

`airi_point_salad_web` is a separately deployed static site. It has no server runtime and calls the HTTPS API at port 22319.

## Server Architecture

`airi_game_server` is the sole owner of the Uvicorn process. On startup it validates the TLS certificate configuration before binding a public interface. It refuses a public, insecure authentication endpoint. It configures CORS as an explicit allowlist for the deployed SEKAI and Point Salad web origins.

The plugin contains a common API layer and two game adapters. The common layer handles authentication, authorization, standardized responses, error translation, rate limiting, and request identity. A game adapter translates HTTP requests into a game-specific service call and returns a versioned public snapshot. Game rules do not depend on FastAPI request objects or browser session details.

SEKAI keeps its current REST endpoint paths and token behavior during the migration. The new implementation provides compatibility aliases for the existing static client, then the static client is changed to the new common API-base configuration. No gameplay state or score semantics change.

## Identity And Authentication

Every game uses one AiriCore web identity based on a QQ number. A signed session token identifies that QQ number and its resolved display name.

### Bot Verification

Bot verification preserves the existing flow:

1. The website requests a short-lived verification code.
2. The player sends that code to Airi through the Bot.
3. Airi confirms the sender QQ number and nickname.
4. The browser receives a signed session token after polling the verification result.

### Email Verification

Email verification supports the same identity without requiring a Bot interaction:

1. The player submits an address matching `pure-numeric-qq@qq.com`.
2. AiriCore sends a one-time verification code using the existing shared mailer.
3. The player submits the code and receives a signed session token for the QQ number in the local part.

The email route validates the exact address form, applies per-QQ and per-IP send limits, a resend cooldown, short expiration, a bounded number of attempts, and hashed code storage. It never logs or returns a code or complete email address. If the account has no Bot-known nickname, the client displays the QQ number until Bot verification supplies a better name.

Both methods resolve to the same account, token format, room permissions, and heartbeat state. Existing SEKAI `/api/auth/request` and `/api/auth/poll` remain available during the client migration.

## Point Salad Rooms

Point Salad uses a generic session identifier rather than treating a group ID as the game identity. A session has one of two origins:

| Origin | Creation | Messaging | Access |
| --- | --- | --- | --- |
| Group room | Existing `,sl create` command | Group updates remain enabled | A room code may invite any authenticated QQ account during the lobby |
| Web room | Point Salad website | No Bot or group messages | Authenticated accounts use the room code during the lobby |

The Point Salad state model gains a session identifier and optional origin-group identifier. Existing saved group games migrate to group-origin sessions when loaded, preserving the old command behavior and avoiding collisions with web sessions.

Room codes are random, single-use, short-lived capabilities. They authorize one authenticated account to enter only the target room. For an unused lobby code, the owner may issue a replacement. Codes cannot join a started or finished room.

For group rooms, a code may add a cross-group web player to the same player list while the lobby is open. This player uses the same turn, rules, player cap, persistence, and scoring behavior as every other player. For web rooms, all creation, joining, starting, action, timeout, and result behavior is shown exclusively in the website.

## Point Salad API And State Flow

The browser reads room snapshots and submits actions through `/api/point-salad/*`. All mutations delegate to the existing `GameService` transaction path, including its session lock, rollback, persistence, expiry timer, and game-rule validation. Browser requests never reimplement card selection, score calculation, or turn validation.

Each snapshot contains the session origin, version, phase, player and action permissions, current player, public board data, and viewer-specific actionable data. Mutating requests include the observed version. A stale or conflicting request returns a structured Chinese conflict response with the current version, and the client reloads the snapshot.

The initial endpoints are:

- Create a web room.
- Create and redeem a Point Salad room code.
- List authorized active rooms for the current user.
- Read a room snapshot and rules.
- Send a room heartbeat.
- Join, leave, start, stop, take, flip, and use a skill.

All API responses use a common JSON envelope. Invalid input, expired authentication, invitation failure, permission denial, stale state, invalid turn, finished room, mail failure, and unavailable network conditions map to explicit Chinese user-facing errors.

## Browser Presence And Group Notifications

An active Point Salad browser page periodically submits a room heartbeat. The server marks the player as web-active only for a short TTL. The browser refreshes the room snapshot with short polling and redraws only after its version changes. It presents an in-page turn notice for web rooms and group rooms alike.

For every successful action in a group-origin session, the Bot adapter first sends the existing previous-player card-change update. It then evaluates the next player:

- If the next player is an active browser player and is currently a member of the origin group, send `@xxx 轮到你了，请在网页端继续操作`.
- Otherwise, send the existing group board and turn prompt.
- If the next player is not an origin-group member, do not send an `@` mention. The website remains the turn notification channel.

Membership is checked at notification time instead of persisted in the game state. A failed membership query is treated as not mentionable. Web-origin sessions never invoke the Bot notification adapter.

## Point Salad Static Client

`airi_point_salad_web` uses plain HTML, CSS, and ES modules. It is independently deployed over HTTPS and has no server-side rendering or application runtime. The client has four operational views:

- Authentication, with separate Bot-verification and email-verification panels.
- Room entry, with create-web-room, room-code join, and authorized-active-room recovery actions.
- Lobby, with origin-aware room details, players, mode, speed, room code, and owner-only start and unused-code replacement controls.
- Game table, with the market, decks, public missions, current turn, public player information, viewer actions, and reconnection status.

The client keeps only the signed token and recently authorized session identifiers in browser storage. It never treats browser data as the source of truth. Connection failure moves the table into an explicit read-only state; recovery fetches the newest snapshot.

The layout is a dense tabletop UI for 2 to 6 players: fixed action controls, a clear market and turn hierarchy, and responsive vertical regions on narrow screens. It avoids a marketing landing page and decorative nested cards.

Point Salad card data and visual assets are synchronized from the plugin through a controlled static-resource process. The deployed static artifact uses base64 image data rather than runtime local-path references. This keeps the web representation aligned with the Bot-rendered card catalog.

## Error Handling And Security

- Public authentication requires TLS. Startup fails closed if public HTTPS credentials are absent.
- CORS permits only the configured static-site origins and the required methods and headers.
- Bearer tokens are verified on every protected request. Expired or invalid tokens force a fresh login.
- Room codes are scoped, single-use, short-lived, and never grant broad game or group access.
- Browser mutations are serialized by the same authoritative session lock as Bot commands.
- Unexpected service errors are logged with request context but return a stable Chinese generic failure response. Sensitive verification values are excluded from logs.
- A browser presence timeout only affects notification behavior; it never ends a game or revokes the player's room membership.

## Verification

The implementation must demonstrate:

- Bot and email authentication success, expiration, invalid code, resend cooling, attempt caps, and rate limits.
- SEKAI legacy endpoint compatibility and successful authentication after its client switches to the common API base.
- Point Salad group-origin and web-origin games across 2 to 6 players, including lobby, full game, timeout, persistence reload, and result calculation.
- Cross-group web players joining a group room and never receiving a group mention when not a current origin-group member.
- Web-active group members receiving the browser continuation prompt after the previous-player card-change update; inactive users receiving the existing board and turn prompt.
- Concurrent browser and Bot actions accepting exactly one valid state transition.
- Existing group-game persistence upgrading safely and corrupt-state recovery preserving current behavior.
- Static client flows on desktop and mobile: both login methods, create, invite, join, reload, reconnect, legal and illegal actions, and finished games.

Temporary verification scripts, previews, screenshots, and bytecode artifacts are removed after validation unless the repository already owns the test file.
