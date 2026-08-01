# Airi Point Salad Official Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generated Point Salad card pool and shared-deck engine with the official 108-card catalog and official three-deck rules, preserve the existing themed quick/standard and classic/mix choices, render official-style information layouts, and rewrite the `aps_help` article.

**Architecture:** Load and validate all official card definitions from `assets/cards.json`, translate official produce keys through one explicit theme mapping, and store three independent decks in `GameState`. Classic mode runs the official engine, quick mode only reduces the official pool, and mix mode layers the existing Center and Live Mission systems on the same engine. Separate card-face rendering from board/result rendering so twelve official scoring layouts do not further inflate `renderer.py`.

**Tech Stack:** Python 3.11, dataclasses, JSON, Pillow, NoneBot/OneBot v11, pure-dictionary pickle persistence, `unittest`, Ruff, Poppler-derived PDF audit evidence, isolated `gpt-5.6-sol` visual review.

**Authoritative inputs:**

- `docs/superpowers/specs/2026-08-01-airi-point-salad-official-rules-design.md`
- `/private/tmp/airi_point_salad_official_report.md`
- `/Users/liko/Downloads/得分沙拉_中文版/英文规则.pdf`
- `/Users/liko/Downloads/得分沙拉_中文版/卡片.pdf`

**Repository constraints:**

- Preserve all unrelated staged and unstaged user changes.
- Do not add docstrings or code comments.
- Keep user-visible messages and logs in Chinese.
- Send runtime images as base64 only.
- Delete task-created temporary tests and previews after final verification.
- Do not commit PDF render intermediates or extracted official artwork.

---

### Task 1: Add the official catalog and strict rule model

**Files:**
- Create: `plugins/airi_point_salad/assets/cards.json`
- Modify: `plugins/airi_point_salad/models.py`
- Replace: `plugins/airi_point_salad/cards.py`
- Create temporarily: `/private/tmp/test_airi_point_salad_official_cards.py`

- [ ] **Step 1: Write failing catalog tests**

Create `/private/tmp/test_airi_point_salad_official_cards.py` with focused assertions against the wished-for API:

```python
from collections import Counter
import unittest

from plugins.airi_point_salad.cards import load_catalog
from plugins.airi_point_salad.models import RuleKind


class OfficialCatalogTests(unittest.TestCase):
    def test_catalog_has_every_official_card(self):
        cards = load_catalog()
        self.assertEqual(len(cards), 108)
        self.assertEqual(len({card.card_id for card in cards}), 108)
        group_counts = Counter(card.character for card in cards)
        self.assertEqual(len(group_counts), 6)
        self.assertEqual(set(group_counts.values()), {18})

    def test_catalog_has_official_rule_distribution(self):
        counts = Counter(card.rule.kind for card in load_catalog())
        self.assertEqual(counts[RuleKind.MOST], 6)
        self.assertEqual(counts[RuleKind.FEWEST], 6)
        self.assertEqual(counts[RuleKind.PARITY], 6)
        self.assertEqual(counts[RuleKind.LINEAR], 48)
        self.assertEqual(counts[RuleKind.SAME_PAIR], 6)
        self.assertEqual(counts[RuleKind.SAME_TRIPLE], 6)
        self.assertEqual(counts[RuleKind.SET], 24)
        self.assertEqual(counts[RuleKind.MISSING_TYPES], 1)
        self.assertEqual(counts[RuleKind.TYPES_AT_LEAST], 2)
        self.assertEqual(counts[RuleKind.FEWEST_TOTAL], 1)
        self.assertEqual(counts[RuleKind.MOST_TOTAL], 1)
        self.assertEqual(counts[RuleKind.COMPLETE_SET], 1)
```

Add tests that copy the JSON into a temporary directory, mutate one property at a time, and assert rejection for duplicate IDs, missing cards, invalid produce keys, wrong value types, unknown rule fields, NaN/Infinity, wrong per-produce counts, and duplicate source positions.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m unittest /private/tmp/test_airi_point_salad_official_cards.py -v
```

Expected: import or assertion failures because `load_catalog`, the twelve rule kinds, and `assets/cards.json` do not exist.

- [ ] **Step 3: Define the official rule data shape**

Replace the old five generated-rule variants with the official kinds while keeping serialization strict:

```python
class RuleKind(str, Enum):
    MOST = "most"
    FEWEST = "fewest"
    PARITY = "parity"
    LINEAR = "linear"
    SAME_PAIR = "same_pair"
    SAME_TRIPLE = "same_triple"
    SET = "set"
    MISSING_TYPES = "missing_types"
    TYPES_AT_LEAST = "types_at_least"
    FEWEST_TOTAL = "fewest_total"
    MOST_TOTAL = "most_total"
    COMPLETE_SET = "complete_set"


@dataclass(slots=True)
class ScoreRule:
    kind: RuleKind
    target: Character | None = None
    points: int = 0
    odd_points: int = 0
    threshold: int = 0
    weights: dict[Character, int] = field(default_factory=dict)
    requirements: dict[Character, int] = field(default_factory=dict)
```

Extend `Card` with `produce` and `source` strings so persisted state and rendered IDs retain official provenance. Update `_rule_to_dict`, `_rule_from_dict`, `_card_to_dict`, and `_card_from_dict` with exact-type checks and no implicit coercion.

- [ ] **Step 4: Populate all 108 JSON records**

Use section D of `/private/tmp/airi_point_salad_official_report.md` as the exact row-by-row source. Preserve `CAB/CAR/LET/ONI/PEP/TOM-01..18`, `p1-r1c1..p12-r3c3`, official produce keys, types, coefficients, thresholds, and points. Use this approved mapping:

```json
{
  "cabbage": "haruka",
  "carrot": "shizuku",
  "lettuce": "minori",
  "onion": "airi",
  "pepper": "rin",
  "tomato": "miku"
}
```

Represent `linear` coefficients under `weights`; `set` requirements under `requirements`; `parity` with `points=7` and `odd_points=3`; repeated groups with `target`, `threshold`, and `points`; special types with the report’s threshold and points.

- [ ] **Step 5: Implement strict catalog loading**

Expose:

```python
CATALOG_PATH = Path(__file__).resolve().parent / "assets" / "cards.json"


@lru_cache(maxsize=1)
def load_catalog() -> tuple[Card, ...]:
    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file, parse_constant=_reject_constant)
    return _decode_catalog(payload)
```

Make `_decode_catalog` validate the schema version, exact key sets, mapping bijection, all 108 IDs, all 108 source positions, six groups of 18, and rule-specific field sets before constructing immutable catalog entries.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run the same unittest command. Expected: every catalog and rejection test passes.

- [ ] **Step 7: Commit only Task 1 files**

```bash
git add plugins/airi_point_salad/assets/cards.json plugins/airi_point_salad/models.py plugins/airi_point_salad/cards.py
git commit -m "feat: add official point salad catalog"
```

### Task 2: Implement official scoring and final tie-breaking

**Files:**
- Modify: `plugins/airi_point_salad/scoring.py`
- Modify: `plugins/airi_point_salad/models.py`
- Create temporarily: `/private/tmp/test_airi_point_salad_official_scoring.py`

- [ ] **Step 1: Write failing scoring tests**

Build real `GameState` and `PlayerState` objects and cover all twelve rule kinds. Include these decisive cases:

```python
self.assertEqual(score_rule(linear_rule, own, all_counts), -2)
self.assertEqual(score_rule(parity_rule, empty, all_counts), 7)
self.assertEqual(score_rule(pair_rule, five_targets, all_counts), 10)
self.assertEqual(score_rule(triple_rule, seven_targets, all_counts), 16)
self.assertEqual(score_rule(complete_rule, six_counts, all_counts), 24)
```

Add tied `most`, tied `fewest`, `most_total`, and `fewest_total` cases where every tied holder scores. Add a Miku wildcard case proving only the selected score card receives one extra mapped character. Add two equal-total players with different `last_action_turn` values and assert the later player ranks first with unique ranks.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: failures from the old five-kind scorer and old character-count/Mission tie-break keys.

- [ ] **Step 3: Implement a comparison-aware score context**

Use a single function boundary:

```python
def score_rule(
    rule: ScoreRule,
    own_counts: dict[Character, int],
    all_counts: tuple[dict[Character, int], ...],
) -> int:
    if rule.kind is RuleKind.MOST:
        value = own_counts[rule.target]
        return rule.points if value == max(counts[rule.target] for counts in all_counts) else 0
    if rule.kind is RuleKind.FEWEST:
        value = own_counts[rule.target]
        return rule.points if value == min(counts[rule.target] for counts in all_counts) else 0
    if rule.kind is RuleKind.PARITY:
        return rule.points if own_counts[rule.target] % 2 == 0 else rule.odd_points
    if rule.kind is RuleKind.LINEAR:
        return sum(own_counts[character] * weight for character, weight in rule.weights.items())
    if rule.kind in {RuleKind.SAME_PAIR, RuleKind.SAME_TRIPLE}:
        return own_counts[rule.target] // rule.threshold * rule.points
    if rule.kind is RuleKind.SET:
        groups = min(own_counts[character] // amount for character, amount in rule.requirements.items())
        return groups * rule.points
    if rule.kind is RuleKind.MISSING_TYPES:
        return sum(own_counts[character] == 0 for character in Character) * rule.points
    if rule.kind is RuleKind.TYPES_AT_LEAST:
        return sum(own_counts[character] >= rule.threshold for character in Character) * rule.points
    if rule.kind is RuleKind.MOST_TOTAL:
        total = sum(own_counts.values())
        return rule.points if total == max(sum(counts.values()) for counts in all_counts) else 0
    if rule.kind is RuleKind.FEWEST_TOTAL:
        total = sum(own_counts.values())
        return rule.points if total == min(sum(counts.values()) for counts in all_counts) else 0
    if rule.kind is RuleKind.COMPLETE_SET:
        return min(own_counts.values()) * rule.points
    raise ValueError("未知计分规则")
```

Implement linear sums, parity with zero even, floor division for repeated groups, minimum-count sets, missing/threshold type counts, all-player comparisons with ties accepted, total comparisons, and six-character complete sets.

- [ ] **Step 4: Integrate wildcard and ranking**

Compute immutable base counts for all players once per scoring pass. For the chosen Miku score card, copy only the holder’s counts and add one mapped character before evaluating that card. Add `last_action_turn: int = -1` to `PlayerState` serialization. Sort final ranks by `(total, last_action_turn)` descending and assign unique ordinal ranks.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the scoring unittest. Expected: all twelve rule kinds, wildcard isolation, comparison ties, negative results, and final tie-breaking pass.

- [ ] **Step 6: Commit only Task 2 files**

```bash
git add plugins/airi_point_salad/scoring.py plugins/airi_point_salad/models.py
git commit -m "feat: implement official point salad scoring"
```

### Task 3: Replace the shared deck with the official three-deck engine

**Files:**
- Modify: `plugins/airi_point_salad/models.py`
- Modify: `plugins/airi_point_salad/cards.py`
- Modify: `plugins/airi_point_salad/game.py`
- Create temporarily: `/private/tmp/test_airi_point_salad_three_decks.py`

- [ ] **Step 1: Write failing deck and market tests**

Cover 2–6 players for quick and standard sizes, catalog-only cards, deterministic seeds, three piles with size difference at most one, random-but-deterministic first player, initial two-card markets per column, same-column refill, and termination only when all three piles and all market positions are empty.

Add an exact split test:

```python
state.decks = [[], ["bottom-a", "bottom-b", "keep-a", "top"], ["other"]]
rebalance_empty_decks(state)
self.assertEqual(state.decks[0], ["bottom-a", "bottom-b"])
self.assertEqual(state.decks[1], ["keep-a", "top"])
```

Add a largest-pile tie test proving the lower column index is chosen.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: failures because `GameState` has one `deck`, a separate `score_market`, fixed host-first order, and shared refill.

- [ ] **Step 3: Build deterministic official subsets**

Expose:

```python
def cards_per_character(player_count: int, speed: GameSpeed) -> int:
    return player_count * (2 if speed is GameSpeed.QUICK else 3)


def build_decks(player_count: int, speed: GameSpeed, seed: int) -> tuple[dict[str, Card], list[list[str]], int]:
    rng = random.Random(seed)
    count = cards_per_character(player_count, speed)
    selected = []
    for character in Character:
        group = [card for card in load_catalog() if card.character is character]
        selected.extend(rng.sample(group, count))
    rng.shuffle(selected)
    decks = [[], [], []]
    for index, card in enumerate(selected):
        decks[index % 3].append(card.card_id)
    cards = {card.card_id: card for card in selected}
    return cards, decks, rng.randrange(player_count)
```

Sample each mapped character group independently from its 18 official cards, combine and shuffle using one `random.Random(seed)`, distribute in round-robin order across three lists, and draw the first player from the same deterministic random stream.

- [ ] **Step 4: Replace the state fields**

Replace `deck` and `score_market` with:

```python
decks: list[list[str]] = field(default_factory=lambda: [[], [], []])
starting_player: int = 0
post_flip_user_id: str | None = None
post_flip_available: bool = False
```

Update strict `to_dict/from_dict` shape validation so `decks` is exactly three arrays and `character_market` is exactly three rows of two values.

- [ ] **Step 5: Implement column refill and split behavior**

Make `take_score` pop `state.decks[column][-1]`. Make every character-market vacancy pop only from its own column. Add deterministic empty-pile splitting that moves the bottom `len(source)//2` cards without changing the source top. Repeat split/refill until no more official moves exist.

- [ ] **Step 6: Randomize start and preserve mixed initialization**

Set `current_player` and `starting_player` to the returned random index, then assign Centers and missions only for mix mode. Keep the turn ring in player-list order.

- [ ] **Step 7: Run focused tests and verify GREEN**

Expected: all size, determinism, split, column-refill, initial market, and official termination tests pass.

- [ ] **Step 8: Commit only Task 3 files**

```bash
git add plugins/airi_point_salad/models.py plugins/airi_point_salad/cards.py plugins/airi_point_salad/game.py
git commit -m "feat: add official three-deck game engine"
```

### Task 4: Support post-action flipping and adapt mixed-mode skills

**Files:**
- Modify: `plugins/airi_point_salad/game.py`
- Modify: `plugins/airi_point_salad/skills.py`
- Modify: `plugins/airi_point_salad/missions.py`
- Modify: `plugins/airi_point_salad/service.py`
- Create temporarily: `/private/tmp/test_airi_point_salad_turn_windows.py`

- [ ] **Step 1: Write failing turn-window tests**

Cover:

- current player flips before taking and cannot flip again afterward;
- a player takes a score card and flips that newly acquired card before the next valid action;
- a failed next-player command does not close the previous window;
- board/help viewing does not close the window;
- the next player’s successful flip, take, skill prepare, or skill resolve closes it;
- Airi Center’s no-flip turn creates no post-action window;
- Rin and completed Minori actions create a window when no earlier flip was used;
- all mutations roll back the window together with state when prepare/render/save fails.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: post-action flip attempts fail because the turn pointer has advanced and `turn_flips` was reset.

- [ ] **Step 3: Separate current-turn and previous-turn flip eligibility**

Add helpers that close a previous window only inside a successful current-player state mutation. Change `flip_score` to accept either the current player’s unused pre-action opportunity or `post_flip_user_id` with `post_flip_available`. Clear the window after a post-action flip.

- [ ] **Step 4: Record completed action order**

Before advancing the player pointer, write the acting player’s `last_action_turn = state.turn_number`. Open the post-action window only if the player did not flip earlier and no skill forbids it. Reset the new current player’s `turn_flips` independently.

- [ ] **Step 5: Adapt Center skills to three decks**

Change Haruka refresh to remove the target pile top plus its two market cards, place them at that pile’s bottom in stable order, and refill that column. Keep Minori, Airi, Shizuku, Miku, and Rin semantics while routing every turn-ending skill through the new official finish/window function.

- [ ] **Step 6: Run focused tests and verify GREEN**

Expected: official before/after flipping and all existing mixed-mode skill transactions pass.

- [ ] **Step 7: Commit only Task 4 files**

```bash
git add plugins/airi_point_salad/game.py plugins/airi_point_salad/skills.py plugins/airi_point_salad/missions.py plugins/airi_point_salad/service.py
git commit -m "feat: support official flip timing"
```

### Task 5: Version persistence and delete legacy saves

**Files:**
- Modify: `plugins/airi_point_salad/persistence.py`
- Modify: `plugins/airi_point_salad/models.py`
- Create temporarily: `/private/tmp/test_airi_point_salad_persistence_v2.py`

- [ ] **Step 1: Write failing persistence tests**

Use a temporary directory and assert:

- a valid version-2 main file loads;
- a valid version-2 backup recovers when the main file is corrupt;
- a legacy pure-games dictionary main file is deleted and returns no games;
- legacy `.pk.bak`, `.json`, and `.json.bak` files are deleted individually;
- a valid version-2 backup is not deleted merely because the main file is legacy;
- newly saved payloads contain `schema_version=2` and `games`;
- only pure dictionaries are pickled and the restricted unpickler remains active.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: the current store treats an unversioned root as current data and migrates legacy JSON instead of deleting it.

- [ ] **Step 3: Implement versioned roots**

Write:

```python
PAYLOAD_VERSION = 2


def _encode(games: dict[str, GameState]) -> dict:
    return {
        "schema_version": PAYLOAD_VERSION,
        "games": {group_id: state.to_dict() for group_id, state in games.items()},
    }
```

Recognize version-2 payloads exactly. Delete only files positively identified as legacy. Preserve the existing atomic temporary file, fsync, backup, corrupt-file quarantine, and restricted unpickling behavior for new-version files.

- [ ] **Step 4: Run focused tests and verify GREEN**

Expected: all legacy deletion, new backup recovery, and round-trip tests pass.

- [ ] **Step 5: Commit only Task 5 files**

```bash
git add plugins/airi_point_salad/persistence.py plugins/airi_point_salad/models.py
git commit -m "feat: reset point salad persistence schema"
```

### Task 6: Rewire commands, service responses, and in-bot help

**Files:**
- Modify: `plugins/airi_point_salad/commands.py`
- Modify: `plugins/airi_point_salad/service.py`
- Modify: `plugins/airi_point_salad/help.py`
- Modify: `plugins/airi_point_salad/__init__.py`
- Create temporarily: `/private/tmp/test_airi_point_salad_help_and_service.py`

- [ ] **Step 1: Write failing integration tests**

Assert the parser keeps all existing aliases and command forms. Assert `,sl` says speed changes only quantity, classic is the official base, mix adds extensions, and `,sl rl` covers three decks, same-column refill, empty-pile splitting, pre/post flipping, twelve scoring types, official tie-breaking, Center, and Mission.

Assert detailed help still uses six forward nodes, the first node contains text followed by a base64 cover image, and no local path is sent.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: old help still describes a shared deck, pre-take-only flipping, five generated rule kinds, and old tie-breaking.

- [ ] **Step 3: Rewrite summary and detailed help**

Keep the current command syntax. Update `USAGE`, `rules_text`, and `help_sections` with the official engine and explicit quick/mix extension boundaries. Preserve `https://www.airi.asia/posts/aps_help/`, the current help cover, six-node forwarding, Chinese failure messages, and `base64://` image delivery.

- [ ] **Step 4: Update turn notifications**

Make the prepared board response mention the randomized current player and post-flip opportunity without producing duplicate turn mentions. Continue sending `@ + image` only when a new current-player turn begins.

- [ ] **Step 5: Run focused tests and verify GREEN**

Expected: command compatibility, help content, forward-node structure, cover fallback, and service responses pass.

- [ ] **Step 6: Commit only Task 6 files**

```bash
git add plugins/airi_point_salad/commands.py plugins/airi_point_salad/service.py plugins/airi_point_salad/help.py plugins/airi_point_salad/__init__.py
git commit -m "feat: document official point salad gameplay"
```

### Task 7: Render official-style themed scoring cards and three-deck boards

**Files:**
- Create: `plugins/airi_point_salad/card_renderer.py`
- Modify: `plugins/airi_point_salad/renderer.py`
- Reuse: `plugins/airi_point_salad/art_assets.py`
- Create temporarily: `/private/tmp/test_airi_point_salad_official_renderer.py`
- Create temporarily: `/private/tmp/airi_point_salad_official_previews/`

- [ ] **Step 1: Write failing renderer contract tests**

For at least one real catalog card per rule kind, assert `render_score_back` returns a 750×1050 RGBA image with rounded transparent corners. Assert character fronts and icons retain current generated assets. Assert a board reads the top of each `decks[column]`, displays each pile’s remaining count, renders six market positions, and returns a decodable `base64://` JPEG below 3 MiB.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: failures because the old renderer knows only five rule kinds and reads `score_market` plus one shared deck.

- [ ] **Step 3: Extract card-face rendering**

Move character fronts, character icons, score backs, rule-layout helpers, and their cache keys into `card_renderer.py`. Keep `renderer.py` responsible for board/result composition and import or re-export the public card functions required by existing callers.

- [ ] **Step 4: Implement the shared official card frame**

Preserve the current base, title, theme portraits, Q art, gold border, 24 px antialiased corners, and 65% portrait-shadow opacity. Add mirrored triangular corner tags for the reverse-side character and a central pale plate. Keep the stable official ID at the bottom.

- [ ] **Step 5: Implement specialized rule layouts**

Use separate helpers for comparison, parity, linear rows, repeated same-character groups, mixed sets, type thresholds, total comparisons, and complete sets. Match official information relationships: icons adjacent to their coefficients, visible plus/equal signs, discrete score badges, consistent row spacing, and red negative values.

- [ ] **Step 6: Update board and result rendering**

Render each pile top as its public score card, label per-column remaining counts, retain A1–C2 coordinates, show post-flip status, and replace the old tie/Mission wording with the official ranking result while still including Mission points in mix mode.

- [ ] **Step 7: Run renderer tests and verify GREEN**

Expected: all twelve card types, character surfaces, boards, and results meet dimensions, base64, transport-size, and cache contracts.

- [ ] **Step 8: Produce isolated visual-review previews**

Render twelve representative score cards, one six-player standard board, one result, and six character fronts into `/private/tmp/airi_point_salad_official_previews/`. Compress every review image below 512 KiB and verify sizes before any visual model call.

- [ ] **Step 9: Dispatch isolated `gpt-5.6-sol` visual QA**

Send only the compressed previews to a fresh subagent. Require a text-only report covering clipping, overlap, official information order, coefficient/icon association, corner tags, negative-value contrast, and board readability. Fix every reported defect and repeat review until approved. Do not send preview images into the controller context.

- [ ] **Step 10: Commit only Task 7 source files**

```bash
git add plugins/airi_point_salad/card_renderer.py plugins/airi_point_salad/renderer.py
git commit -m "feat: render official point salad card layouts"
```

### Task 8: Rewrite aps_help and rebuild its illustrations

**Files:**
- Modify: `plugins/airi_point_salad/aps_help/index.mdx`
- Create: `plugins/airi_point_salad/aps_help/build_assets.py`
- Modify: `plugins/airi_point_salad/aps_help/cover.png`
- Modify: `plugins/airi_point_salad/aps_help/market-guide.png`
- Modify: `plugins/airi_point_salad/aps_help/turn-flow.png`
- Modify: `plugins/airi_point_salad/aps_help/scoring-guide.png`
- Create: `plugins/airi_point_salad/aps_help/scoring-special.png`
- Modify: `plugins/airi_point_salad/aps_help/mixed-mode.png`
- Modify: `plugins/airi_point_salad/aps_help/center-skills.png`
- Create temporarily: `/private/tmp/test_airi_point_salad_aps_help.py`

- [ ] **Step 1: Write failing article contract tests**

Parse frontmatter and Markdown and assert the final article contains the confirmed quantity table, three independent piles, empty-pile splitting, same-column refill, pre/post flip wording, twelve official rule groups, official action-order tie-break, classic/mix layering, all command examples, and timeout behavior. Assert it does not claim a shared deck, pre-action-only flipping, five score types, or character/Mission tie-breaks. Assert every referenced image exists.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: the current article fails all new-rule assertions and lacks `scoring-special.png` plus a reproducible builder.

- [ ] **Step 3: Rewrite the article**

Keep the existing title, route-compatible frontmatter, cover filename, and Chinese player-facing tone. Follow the ten-section structure in the approved design. Separate standard classic as the exact official quantity setup, quick as a reduced-pool variant, and mix as the only source of Center/Mission content.

- [ ] **Step 4: Build reproducible illustrations**

Create `build_assets.py` that imports the final catalog, card renderer, board renderer, and existing theme assets. Generate all seven PNGs deterministically without duplicating scoring or game rules in the builder. Use arrows, labels, and callouts for three-pile flow and post-action flipping.

- [ ] **Step 5: Run article tests and asset builder twice**

Run the contract test, run `build_assets.py`, hash every PNG, run it again, and assert hashes remain identical.

- [ ] **Step 6: Perform isolated visual QA**

Compress every article image below 512 KiB, verify sizes, and send them only to a fresh `gpt-5.6-sol` subagent. Require text-only feedback for font size, arrow direction, cropping, Chinese legibility, and consistency with the final engine. Fix and re-run until approved.

- [ ] **Step 7: Commit only Task 8 files**

```bash
git add plugins/airi_point_salad/aps_help
git commit -m "docs: rewrite point salad gameplay article"
```

### Task 9: Run full regression, clean artifacts, and update memory

**Files:**
- Verify: `plugins/airi_point_salad/`
- Verify: all project Python files and plugin registrations
- Update: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-point-salad.md`
- Update if needed: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-point-salad-models.md`
- Update: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/MEMORY.md`
- Remove: all `/private/tmp/test_airi_point_salad_*.py`
- Remove: `/private/tmp/airi_point_salad_official_previews/`
- Remove after catalog verification: `/private/tmp/airi_point_salad_official_report.md`

- [ ] **Step 1: Simulate every supported combination**

Run deterministic complete-game simulations for 2–6 players × quick/standard × classic/mix. Assert each of the 20 games reaches `FINISHED`, uses only official catalog IDs, never duplicates a physical card, maintains three valid piles, and produces a uniquely ranked result.

- [ ] **Step 2: Verify the full official catalog against the independent audit**

Compare all 108 JSON signatures with section D of `/private/tmp/airi_point_salad_official_report.md`. Assert the exact type distribution `6/6/6/48/6/6/24/1/2/1/1/1`, six groups of 18, and no unmatched source positions.

- [ ] **Step 3: Run code health checks**

Run Ruff on every changed Python file, parse every repository Python file with `ast.parse`, compile into an isolated temporary bytecode directory, run `git diff --check`, and initialize NoneBot to load every project plugin. Expected: zero errors or warnings caused by this work.

- [ ] **Step 4: Re-run final rendering evidence**

Render all twelve rule kinds, a worst-case six-player standard mix board, a classic result, a mix result, and every `aps_help` asset. Assert decode success, base64 runtime boundaries, 3 MiB transport limits, and deterministic article assets.

- [ ] **Step 5: Remove temporary artifacts**

Delete every task-created unittest, preview, compressed review copy, scratch directory, and isolated bytecode output. Preserve formal `assets/cards.json`, runtime assets, article source, article PNGs, and user files that predated this task.

- [ ] **Step 6: Sync plugin directory mtimes**

Run the repository’s recursive bottom-up directory-mtime synchronization workflow twice. The temporary implementation must skip `.git`, `__pycache__`, `.claude`, virtual environments, `node_modules`, IDE/cache directories, and symlinks; ignore `.pyc/.pyo/.pk/.log/.DS_Store` outside runtime `data/log/logs` paths; set each directory to the maximum accepted child mtime with `os.utime`; and report a changed-directory count. Expected: the first run reports only intended directory timestamp changes and the second reports `changed dirs: 0`. Delete the temporary synchronizer afterward.

- [ ] **Step 7: Update project memory**

Record the official catalog, rule kinds, three-deck engine, flip-window adaptation, persistence reset, renderer split, `aps_help` rewrite, visual QA limits, and fresh verification results in the point-salad memories and refresh the `MEMORY.md` index description.

- [ ] **Step 8: Commit any verification fixes and keep memory external**

If verification required source fixes, stage only those exact repository paths and commit them with `git commit -m "chore: verify official point salad rollout"`. The project memory directory is outside the repository and must be updated separately, never passed to `git add`.

### Task 10: Final cross-task review and integration

**Files:**
- Review: every commit and changed file from Tasks 1–9

- [ ] **Step 1: Dispatch final specification reviewer**

Provide the approved design, this full plan, the official audit report, and the complete diff. Require a requirement-by-requirement verdict covering all 108 cards, official classic rules, mix layering, visual layout, article rewrite, legacy deletion, and image-size isolation.

- [ ] **Step 2: Dispatch final code-quality reviewer**

After specification approval, require review of strict decoding, state invariants, transaction rollback, deterministic randomness, scoring correctness, renderer/cache boundaries, persistence deletion safety, help consistency, and test evidence.

- [ ] **Step 3: Fix and re-review every finding**

Route each finding back to the responsible implementer subagent. Repeat specification review before quality review whenever behavior changes. Do not leave accepted known issues.

- [ ] **Step 4: Run one final fresh verification suite**

Repeat the complete simulation, focused tests, Ruff, AST, isolated compile, plugin load, renderer verification, article checks, mtime idempotence, and `git diff --check` after the last fix.

- [ ] **Step 5: Finish the development branch**

Use `superpowers:finishing-a-development-branch` to merge the verified branch back to local `main` without losing pre-existing user changes, then rerun the final verification on merged `main` and remove the temporary branch/worktree.
