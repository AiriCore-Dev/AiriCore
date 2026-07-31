# airi_point_salad Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a restart-safe MORE MORE JUMP！ themed Point Salad group-chat plugin with quick/standard speed, classic/mix rules, multilingual commands, v2-style cards, and base64-rendered game boards.

**Architecture:** Keep the deterministic card, scoring, turn, skill, and mission logic in focused pure-Python modules. Put group locks, atomic persistence, timeout recovery, and transactional mutation in a service layer, then keep the NoneBot matcher as a thin adapter. Render supplied transparent character art with Pillow into cached 5:7 cards and compose one board image after each legal mutation.

**Tech Stack:** Python 3.11, NoneBot 2.5, OneBot V11, Pillow 10.4, dataclasses, asyncio, JSON, pytest

---

## File map

Create these plugin files:

- `plugins/airi_point_salad/__init__.py`: matcher registration, lifecycle hooks, OneBot context extraction, response sending.
- `plugins/airi_point_salad/models.py`: enums and serializable game-state dataclasses.
- `plugins/airi_point_salad/cards.py`: balanced deck construction and rule definitions.
- `plugins/airi_point_salad/scoring.py`: score-rule evaluation and final ranking.
- `plugins/airi_point_salad/game.py`: classic room lifecycle, market, turn, take, flip, refill, and end detection.
- `plugins/airi_point_salad/skills.py`: six Center skills and their pending-action state.
- `plugins/airi_point_salad/missions.py`: Live Mission definitions, checking, claiming, and refill.
- `plugins/airi_point_salad/commands.py`: Chinese/full-English/abbreviated token normalization and command parsing.
- `plugins/airi_point_salad/persistence.py`: JSON encode/decode, atomic save, backup recovery, and corrupt-file quarantine.
- `plugins/airi_point_salad/service.py`: per-group locks, transactional mutation, permissions, dispatch, and timeouts.
- `plugins/airi_point_salad/renderer.py`: v2 cards, character icons, boards, rules, and result images.
- `plugins/airi_point_salad/assets/characters/*.png`: renamed copies of the six supplied transparent character images.
- `plugins/airi_point_salad/assets/logo.png`: renamed copy of the supplied logo.
- `plugins/airi_point_salad/assets/font.ttf`: bundled CJK font copied from the existing repository asset.

Modify these repository files:

- `plugins/airi_help/__init__.py`: add the game and its primary command to entertainment help.
- `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/MEMORY.md`: index the completed plugin memory.
- `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-point-salad.md`: record architecture, commands, verification, and pitfalls.

All task-created test files live under `/tmp/airi_point_salad_tests/` and are removed in the final task. They must not be committed.

### Task 1: Stage assets and define serializable state

**Files:**
- Create: `plugins/airi_point_salad/assets/characters/miku.png`
- Create: `plugins/airi_point_salad/assets/characters/minori.png`
- Create: `plugins/airi_point_salad/assets/characters/rin.png`
- Create: `plugins/airi_point_salad/assets/characters/shizuku.png`
- Create: `plugins/airi_point_salad/assets/characters/airi.png`
- Create: `plugins/airi_point_salad/assets/characters/haruka.png`
- Create: `plugins/airi_point_salad/assets/logo.png`
- Create: `plugins/airi_point_salad/assets/font.ttf`
- Create: `plugins/airi_point_salad/models.py`
- Test: `/tmp/airi_point_salad_tests/test_models.py`

- [ ] **Step 1: Copy the supplied assets under stable ASCII names**

Run:

```bash
mkdir -p plugins/airi_point_salad/assets/characters
cp /Users/liko/Downloads/初音未来.png plugins/airi_point_salad/assets/characters/miku.png
cp /Users/liko/Downloads/花里实乃理.png plugins/airi_point_salad/assets/characters/minori.png
cp /Users/liko/Downloads/镜音铃.png plugins/airi_point_salad/assets/characters/rin.png
cp /Users/liko/Downloads/日野森雫.png plugins/airi_point_salad/assets/characters/shizuku.png
cp /Users/liko/Downloads/桃井爱莉.png plugins/airi_point_salad/assets/characters/airi.png
cp /Users/liko/Downloads/桐谷遥.png plugins/airi_point_salad/assets/characters/haruka.png
cp /Users/liko/Downloads/Moremore_jump_logo_trans.png plugins/airi_point_salad/assets/logo.png
cp plugins/airi_kokomi_wows/fonts/SHSCN.ttf plugins/airi_point_salad/assets/font.ttf
```

Expected: `file plugins/airi_point_salad/assets/characters/*.png plugins/airi_point_salad/assets/logo.png plugins/airi_point_salad/assets/font.ttf` reports six PNG character assets, one PNG logo, and one TrueType font.

- [ ] **Step 2: Write the failing serialization test**

Create `/tmp/airi_point_salad_tests/test_models.py`:

```python
from plugins.airi_point_salad.models import Character, GameMode, GameSpeed, GameState, Phase


def test_game_state_round_trip():
    state = GameState(group_id="100", host_id="1", speed=GameSpeed.QUICK, mode=GameMode.MIX)
    state.phase = Phase.PLAYING
    restored = GameState.from_dict(state.to_dict())
    assert restored == state
    assert Character.AIRI.display_name == "桃井爱莉"
```

- [ ] **Step 3: Run the test and verify it fails**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest /tmp/airi_point_salad_tests/test_models.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'plugins.airi_point_salad'`.

- [ ] **Step 4: Implement enums and dataclasses in `models.py`**

Use these public types and field names:

```python
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Character(str, Enum):
    MINORI = "minori"
    HARUKA = "haruka"
    AIRI = "airi"
    SHIZUKU = "shizuku"
    MIKU = "miku"
    RIN = "rin"

    @property
    def display_name(self):
        return {
            self.MINORI: "花里实乃理",
            self.HARUKA: "桐谷遥",
            self.AIRI: "桃井爱莉",
            self.SHIZUKU: "日野森雫",
            self.MIKU: "初音未来",
            self.RIN: "镜音铃",
        }[self]


class GameSpeed(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"


class GameMode(str, Enum):
    CLASSIC = "classic"
    MIX = "mix"


class Phase(str, Enum):
    LOBBY = "lobby"
    PLAYING = "playing"
    FINISHED = "finished"


class Face(str, Enum):
    SCORE = "score"
    CHARACTER = "character"


class RuleKind(str, Enum):
    EACH = "each"
    PAIR = "pair"
    SET = "set"
    COMPARE = "compare"
    RISK = "risk"


@dataclass(slots=True)
class ScoreRule:
    kind: RuleKind
    characters: list[Character]
    points: int
    penalty: int = 0
    relation: str = ""


@dataclass(slots=True)
class Card:
    card_id: str
    character: Character
    rule: ScoreRule


@dataclass(slots=True)
class PlayerState:
    user_id: str
    name: str
    score_cards: list[str] = field(default_factory=list)
    character_cards: list[str] = field(default_factory=list)
    center: Character | None = None
    skill_used: bool = False
    mission_ids: list[str] = field(default_factory=list)
    mission_points: int = 0
    skill_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GameState:
    group_id: str
    host_id: str
    speed: GameSpeed
    mode: GameMode
    phase: Phase = Phase.LOBBY
    players: list[PlayerState] = field(default_factory=list)
    cards: dict[str, Card] = field(default_factory=dict)
    deck: list[str] = field(default_factory=list)
    score_market: list[str | None] = field(default_factory=lambda: [None, None, None])
    character_market: list[list[str | None]] = field(default_factory=lambda: [[None, None] for _ in range(3)])
    current_player: int = 0
    turn_number: int = 0
    turn_flips: int = 0
    centers: list[Character] = field(default_factory=list)
    mission_deck: list[str] = field(default_factory=list)
    active_missions: list[str] = field(default_factory=list)
    pending_skill: dict[str, Any] = field(default_factory=dict)
    seed: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self):
        return encode_value(asdict(self))

    @classmethod
    def from_dict(cls, data):
        return decode_game_state(data)
```

Implement `encode_value` and `decode_game_state` explicitly so every enum, nested `Card`, `ScoreRule`, and `PlayerState` round-trips without `pickle`.

- [ ] **Step 5: Run the model test**

Run the Task 1 pytest command again.

Expected: `1 passed`.

- [ ] **Step 6: Commit the assets and state model**

```bash
git add plugins/airi_point_salad/assets plugins/airi_point_salad/models.py
git commit -m "feat: add point salad assets and state model"
```

### Task 2: Build balanced decks and deterministic scoring

**Files:**
- Create: `plugins/airi_point_salad/cards.py`
- Create: `plugins/airi_point_salad/scoring.py`
- Test: `/tmp/airi_point_salad_tests/test_cards_scoring.py`

- [ ] **Step 1: Write failing deck and scoring tests**

Create `/tmp/airi_point_salad_tests/test_cards_scoring.py`:

```python
from collections import Counter

from plugins.airi_point_salad.cards import build_deck
from plugins.airi_point_salad.models import Character, GameSpeed, RuleKind, ScoreRule
from plugins.airi_point_salad.scoring import score_rule


def test_deck_sizes_and_balance():
    for players in range(2, 7):
        for speed, per_player in ((GameSpeed.QUICK, 12), (GameSpeed.STANDARD, 18)):
            cards = build_deck(players, speed, seed=42)
            counts = Counter(card.character for card in cards)
            assert len(cards) == players * per_player
            assert len(set(counts.values())) == 1


def test_rule_kinds():
    counts = {character: 0 for character in Character}
    counts[Character.MIKU] = 3
    counts[Character.HARUKA] = 2
    assert score_rule(ScoreRule(RuleKind.EACH, [Character.MIKU], 2), counts) == 6
    assert score_rule(ScoreRule(RuleKind.PAIR, [Character.MIKU, Character.HARUKA], 5), counts) == 10
    assert score_rule(ScoreRule(RuleKind.COMPARE, [Character.MIKU, Character.HARUKA], 8, relation=">"), counts) == 8
    assert score_rule(ScoreRule(RuleKind.RISK, [Character.MIKU, Character.HARUKA], 3, penalty=-1), counts) == 7
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest /tmp/airi_point_salad_tests/test_cards_scoring.py -q
```

Expected: FAIL because `cards.py` and `scoring.py` do not exist.

- [ ] **Step 3: Implement deterministic deck construction**

In `cards.py`, expose:

```python
CHARACTERS = tuple(Character)


def cards_per_character(player_count: int, speed: GameSpeed) -> int:
    if not 2 <= player_count <= 6:
        raise ValueError("仅支持 2–6 名玩家")
    return player_count * (2 if speed is GameSpeed.QUICK else 3)


def build_rule(character: Character, index: int) -> ScoreRule:
    others = [item for item in CHARACTERS if item is not character]
    variant = index % 5
    if variant == 0:
        return ScoreRule(RuleKind.EACH, [character], 2)
    if variant == 1:
        return ScoreRule(RuleKind.PAIR, [character, others[index % len(others)]], 5)
    if variant == 2:
        return ScoreRule(RuleKind.SET, [character, others[index % 5], others[(index + 1) % 5]], 7)
    if variant == 3:
        return ScoreRule(RuleKind.COMPARE, [character, others[index % 5]], 8, relation=">")
    return ScoreRule(RuleKind.RISK, [character, others[index % 5]], 3, penalty=-1)


def build_deck(player_count: int, speed: GameSpeed, seed: int) -> list[Card]:
    cards = []
    count = cards_per_character(player_count, speed)
    for character in CHARACTERS:
        for index in range(count):
            card_id = f"{character.value}-{index:02d}"
            cards.append(Card(card_id, character, build_rule(character, index)))
    random.Random(seed).shuffle(cards)
    return cards
```

Adjust pair/set selection if the initial modulo sequence repeats a character inside a set. Add a final assertion that all set rules contain unique characters.

- [ ] **Step 4: Implement scoring and ranking**

In `scoring.py`, expose:

```python
def score_rule(rule: ScoreRule, counts: dict[Character, int]) -> int:
    values = [counts.get(character, 0) for character in rule.characters]
    if rule.kind is RuleKind.EACH:
        return values[0] * rule.points
    if rule.kind is RuleKind.PAIR:
        return min(values) * rule.points
    if rule.kind is RuleKind.SET:
        return min(values) * rule.points
    if rule.kind is RuleKind.COMPARE:
        matched = {
            ">": values[0] > values[1],
            "<": values[0] < values[1],
            "=": values[0] == values[1],
        }.get(rule.relation, False)
        return rule.points if matched else 0
    if rule.kind is RuleKind.RISK:
        return values[0] * rule.points + values[1] * rule.penalty
    raise ValueError("未知计分规则")
```

Also add `score_player(state, player) -> ScoreBreakdown` and `rank_players(state) -> list[RankedPlayer]`. Apply Miku's saved wildcard only to its selected score card. Sort by total score, character-card count, mission count, then assign equal rank to exact ties.

- [ ] **Step 5: Run Task 2 tests and add ranking boundary cases**

Add tests for negative risk totals, compare equality, one Miku wildcard application, and shared winners. Run the Task 2 pytest command.

Expected: all Task 2 tests pass.

- [ ] **Step 6: Commit deck and scoring logic**

```bash
git add plugins/airi_point_salad/cards.py plugins/airi_point_salad/scoring.py
git commit -m "feat: add point salad deck and scoring"
```

### Task 3: Implement the classic game state machine

**Files:**
- Create: `plugins/airi_point_salad/game.py`
- Test: `/tmp/airi_point_salad_tests/test_game.py`

- [ ] **Step 1: Write failing lifecycle and turn tests**

Create `/tmp/airi_point_salad_tests/test_game.py`:

```python
import pytest

from plugins.airi_point_salad.game import GameError, add_player, create_game, flip_score, start_game, take_characters, take_score
from plugins.airi_point_salad.models import Face, GameMode, GameSpeed, Phase


def started_game():
    state = create_game("100", "1", "Host", GameSpeed.QUICK, GameMode.CLASSIC, seed=7, now=10)
    add_player(state, "2", "Guest", now=11)
    start_game(state, "1", now=12)
    return state


def test_start_and_take_score():
    state = started_game()
    card_id = state.score_market[0]
    take_score(state, "1", 0, now=13)
    assert card_id in state.players[0].score_cards
    assert state.current_player == 1


def test_flip_before_take():
    state = started_game()
    take_score(state, "1", 0, now=13)
    take_score(state, "2", 0, now=14)
    card_id = state.players[0].score_cards[0]
    flip_score(state, "1", 0, now=15)
    assert card_id not in state.players[0].score_cards
    assert card_id in state.players[0].character_cards
    with pytest.raises(GameError):
        flip_score(state, "1", 0, now=16)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest /tmp/airi_point_salad_tests/test_game.py -q
```

Expected: FAIL because `game.py` does not exist.

- [ ] **Step 3: Implement room lifecycle and validation**

Expose these functions from `game.py`:

```python
class GameError(ValueError):
    pass


def create_game(group_id, host_id, host_name, speed, mode, seed, now) -> GameState:
    state = GameState(group_id, host_id, speed, mode, seed=seed, created_at=now, updated_at=now)
    state.players.append(PlayerState(host_id, host_name))
    return state


def add_player(state, user_id, name, now):
    if state.phase is not Phase.LOBBY:
        raise GameError("游戏已经开始")
    if any(player.user_id == user_id for player in state.players):
        raise GameError("你已经加入本局")
    if len(state.players) >= 6:
        raise GameError("本局人数已满")
    state.players.append(PlayerState(user_id, name))
    state.updated_at = now


def start_game(state, user_id, now):
    if user_id != state.host_id:
        raise GameError("只有房主可以开始游戏")
    if len(state.players) < 2:
        raise GameError("至少需要 2 名玩家")
    cards = build_deck(len(state.players), state.speed, state.seed)
    state.cards = {card.card_id: card for card in cards}
    state.deck = [card.card_id for card in cards]
    state.phase = Phase.PLAYING
    refill_market(state)
    state.updated_at = now
```

Add `remove_player`, `get_player`, `require_turn`, and `stop_game`. Starting a mix game delegates Center and Mission initialization to Task 4 without importing NoneBot.

- [ ] **Step 4: Implement market actions and turn advancement**

Implement:

```python
def flip_score(state, user_id, score_index, now):
    player = require_turn(state, user_id)
    if state.turn_flips >= 1:
        raise GameError("本回合已经翻过牌")
    card_id = pop_index(player.score_cards, score_index, "计分牌编号无效")
    player.character_cards.append(card_id)
    state.turn_flips += 1
    state.updated_at = now


def take_score(state, user_id, column, now):
    player = require_turn(state, user_id)
    card_id = require_score_slot(state, column)
    state.score_market[column] = None
    player.score_cards.append(card_id)
    finish_action(state, now)


def take_characters(state, user_id, slots, now):
    player = require_turn(state, user_id)
    available = available_character_slots(state)
    required = min(2, len(available))
    if len(slots) != required or len(set(slots)) != len(slots):
        raise GameError(f"本回合需要拿取 {required} 张不同位置的角色牌")
    card_ids = [require_character_slot(state, slot) for slot in slots]
    for column, row in slots:
        state.character_market[column][row] = None
    player.character_cards.extend(card_ids)
    finish_action(state, now)
```

`finish_action` refills empty slots from `deck`, increments `turn_number`, advances to the next player, resets `turn_flips`, and marks `Phase.FINISHED` only when deck and all market slots are empty.

- [ ] **Step 5: Add exhaustive engine edge tests**

Add tests for duplicate slots, taking one remaining card at game end, wrong turn, starting with 1 or 7 players, leaving only in lobby, host-only start, market refill, and natural finish. Run all Task 1–3 tests.

Expected: all tests pass.

- [ ] **Step 6: Commit the classic engine**

```bash
git add plugins/airi_point_salad/game.py
git commit -m "feat: add point salad classic engine"
```

### Task 4: Add Center skills and Live Missions

**Files:**
- Create: `plugins/airi_point_salad/skills.py`
- Create: `plugins/airi_point_salad/missions.py`
- Modify: `plugins/airi_point_salad/game.py`
- Test: `/tmp/airi_point_salad_tests/test_mix.py`

- [ ] **Step 1: Write failing mixed-mode tests**

Create `/tmp/airi_point_salad_tests/test_mix.py` with one test per Center and these shared assertions:

```python
def test_skill_failure_does_not_consume_skill(mix_game):
    player = mix_game.players[mix_game.current_player]
    with pytest.raises(GameError):
        use_skill(mix_game, player.user_id, ["invalid"], now=20)
    assert player.skill_used is False


def test_one_mission_per_turn(mix_game):
    player = mix_game.players[mix_game.current_player]
    first = claim_completed_mission(mix_game, player, TurnSummary(character_ids=[]))
    second = claim_completed_mission(mix_game, player, TurnSummary(character_ids=[]))
    assert first is not None
    assert second is None
```

Include deterministic Center assignment, two active missions, mission refill, Minori's armed swap flow, Haruka refresh, Airi score-plus-character, Shizuku extra flip, Miku wildcard payload, and Rin's three-distinct take.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest /tmp/airi_point_salad_tests/test_mix.py -q
```

Expected: FAIL because `skills.py` and `missions.py` do not exist.

- [ ] **Step 3: Implement Mission definitions and checks**

Define:

```python
@dataclass(frozen=True, slots=True)
class Mission:
    mission_id: str
    kind: str
    amount: int
    points: int
    characters: tuple[Character, ...] = ()


@dataclass(slots=True)
class TurnSummary:
    character_ids: list[str]
    score_ids: list[str] = field(default_factory=list)
    mission_claimed: bool = False


def mission_catalog() -> dict[str, Mission]:
    return {
        "same-3": Mission("same-3", "same", 3, 3),
        "different-3": Mission("different-3", "different", 3, 4),
        "two-pairs": Mission("two-pairs", "pairs", 2, 3),
        "score-and-character": Mission("score-and-character", "turn_types", 2, 2),
    }
```

Expand the catalog with character-specific comparisons while keeping every mission deterministically testable. `claim_completed_mission` checks active missions in display order, awards at most one, records its ID and points, then refills to two.

- [ ] **Step 4: Implement skills and explicit pending states**

Expose `skill_usage(state, player) -> str` and `use_skill(state, user_id, args, now) -> SkillResult`.

Use these command flows:

- Minori: `sl sk` arms the next normal character take; after `sl ta A1 B2`, Airi prompts `sl sk A1 C2`, where the first slot is returned and the second slot is taken, and only then finishes the turn.
- Haruka: `sl sk A` moves all cards in column A to the bottom of the deck, refills it, consumes the skill, and leaves the normal action available.
- Airi: `sl sk` arms the next score take; `sl ta A A1` takes the A score and A1 character together, consumes the skill, and ends the turn.
- Shizuku: `sl sk 2` performs one extra score-to-character flip, consumes the skill, and leaves the normal action available.
- Miku: `sl sk 2 rin` binds score card 2 to one extra Rin count during final scoring, consumes the skill, and leaves the normal action available.
- Rin: `sl sk A1 B2 C1` takes three different-character cards, consumes the skill, and ends the turn.

Only set `player.skill_used = True` after every argument and target has passed validation.

- [ ] **Step 5: Integrate mixed-mode turn completion**

Update `start_game` to assign unique Centers with `random.Random(state.seed ^ 0x5A17)`, initialize and shuffle Mission IDs with a separate derived seed, and expose two active Missions. Update `finish_action` to resolve one Mission before advancing the turn. Classic mode must not import or execute mixed-mode behavior.

- [ ] **Step 6: Run all engine tests**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest /tmp/airi_point_salad_tests/test_models.py /tmp/airi_point_salad_tests/test_cards_scoring.py /tmp/airi_point_salad_tests/test_game.py /tmp/airi_point_salad_tests/test_mix.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit mixed rules**

```bash
git add plugins/airi_point_salad/game.py plugins/airi_point_salad/skills.py plugins/airi_point_salad/missions.py
git commit -m "feat: add point salad mixed mode"
```

### Task 5: Parse multilingual commands

**Files:**
- Create: `plugins/airi_point_salad/commands.py`
- Test: `/tmp/airi_point_salad_tests/test_commands.py`

- [ ] **Step 1: Write the failing alias matrix**

Create `/tmp/airi_point_salad_tests/test_commands.py`:

```python
import pytest

from plugins.airi_point_salad.commands import CommandError, parse_command


@pytest.mark.parametrize("text", [
    "沙拉 创建 快速 原版",
    "salad create quick classic",
    "SL CR QK CL",
    "sl   创建 quick cl",
])
def test_create_aliases(text):
    command = parse_command(text)
    assert command.action == "create"
    assert command.args == ["quick", "classic"]


def test_take_slots():
    assert parse_command("sl ta A1 b2").args == [(0, 0), (1, 1)]
    assert parse_command("沙拉 拿 c").args == [2]


def test_rejects_unknown_action():
    with pytest.raises(CommandError):
        parse_command("sl dance")
```

- [ ] **Step 2: Run tests and verify they fail**

Run the Task 5 test file with the airidev Python.

Expected: FAIL because `commands.py` does not exist.

- [ ] **Step 3: Implement one normalization table**

Use:

```python
ALIASES = {
    "root": {"沙拉", "salad", "sl"},
    "create": {"创建", "create", "cr"},
    "quick": {"快速", "quick", "qk"},
    "standard": {"标准", "standard", "std"},
    "classic": {"原版", "classic", "cl"},
    "mix": {"混合", "mix", "mx"},
    "join": {"加入", "join", "j"},
    "leave": {"退出", "leave", "lv"},
    "start": {"开始", "start", "st"},
    "take": {"拿", "take", "ta"},
    "flip": {"翻", "flip", "fl"},
    "skill": {"技能", "skill", "sk"},
    "board": {"桌面", "board", "bd"},
    "rules": {"规则", "rules", "rl"},
    "stop": {"结束", "stop", "sp"},
}


@dataclass(frozen=True, slots=True)
class Command:
    action: str
    args: list
```

Build a reverse alias map once, normalize with `casefold()`, parse score columns `A/B/C`, character slots `A1..C2`, 1-based card indexes, and character names/IDs for skills. Every malformed command raises `CommandError` with a Chinese message and a concrete valid example.

- [ ] **Step 4: Run the alias matrix and add every action**

Add one Chinese, full-English, abbreviation, mixed-language, uppercase, and repeated-space case per action. Run Task 5 tests.

Expected: all tests pass.

- [ ] **Step 5: Commit command parsing**

```bash
git add plugins/airi_point_salad/commands.py
git commit -m "feat: add point salad command aliases"
```

### Task 6: Add transactional persistence and group service

**Files:**
- Create: `plugins/airi_point_salad/persistence.py`
- Create: `plugins/airi_point_salad/service.py`
- Test: `/tmp/airi_point_salad_tests/test_service.py`

- [ ] **Step 1: Write failing persistence and concurrency tests**

Create `/tmp/airi_point_salad_tests/test_service.py` with `tmp_path` storage and test:

```python
@pytest.mark.asyncio
async def test_only_one_concurrent_take_succeeds(service, started_state):
    service.games[started_state.group_id] = started_state
    results = await asyncio.gather(
        service.take("100", "1", ["A"]),
        service.take("100", "1", ["A"]),
        return_exceptions=True,
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1


@pytest.mark.asyncio
async def test_save_failure_rolls_back(service, started_state, monkeypatch):
    service.games["100"] = started_state
    before = started_state.to_dict()
    monkeypatch.setattr(service.store, "save", AsyncMock(side_effect=OSError("disk full")))
    with pytest.raises(OSError):
        await service.take("100", "1", ["A"])
    assert service.games["100"].to_dict() == before
```

Also test round-trip restore, `.bak` fallback, corrupt-file quarantine, lobby 15-minute expiry, game 30-minute expiry, and that `board`/`rules` do not update `updated_at`.

- [ ] **Step 2: Run tests and verify they fail**

Run Task 6 tests with the airidev Python.

Expected: FAIL because the store and service do not exist.

- [ ] **Step 3: Implement atomic JSON persistence**

Implement `GameStore(path: Path)` with:

```python
async def save(self, games: dict[str, GameState]):
    payload = {group_id: state.to_dict() for group_id, state in games.items()}
    async with self._save_lock:
        await asyncio.to_thread(self._write_atomic, payload)


def _write_atomic(self, payload):
    self.path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".games-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))
            file.flush()
            os.fsync(file.fileno())
        if self.path.exists():
            shutil.copyfile(self.path, self.backup_path)
        os.replace(temporary, self.path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise
```

Initialize `self._save_lock = asyncio.Lock()` in `GameStore.__init__`. `load` tries the primary file, then `.bak`, then renames an unreadable primary with `time.strftime("games.corrupt.%Y%m%dT%H%M%S.json")` and returns an empty dictionary while logging a Chinese error.

- [ ] **Step 4: Implement the service transaction boundary**

Define `GameService` with `games`, `locks`, `timers`, `store`, and one `_mutate` helper:

```python
async def _mutate(self, group_id, operation, prepare=None):
    lock = self.locks.setdefault(group_id, asyncio.Lock())
    async with lock:
        before_exists = group_id in self.games
        before = copy.deepcopy(self.games[group_id]) if before_exists else None
        try:
            result = operation()
            prepared = result
            if prepare is not None:
                prepared = await asyncio.to_thread(prepare, result)
            await self.store.save(self.games)
        except Exception:
            if not before_exists:
                self.games.pop(group_id, None)
            else:
                self.games[group_id] = before
            raise
        self._schedule_timeout(group_id)
        return prepared
```

Create explicit methods for `create`, `join`, `leave`, `start`, `take`, `flip`, `skill`, `stop`, `board_state`, and `rules_text`. Mutating methods accept an optional `prepare` callback so board/result rendering happens before persistence and a render failure rolls the state back. Permission checks happen inside the lock. `stop` accepts `is_admin`; starting accepts only the host.

- [ ] **Step 5: Implement timeout restoration**

`load` drops already-expired games, saves the cleaned state once, and schedules `asyncio.TimerHandle` callbacks for the remaining duration. Timeout callbacks acquire the same group lock, re-check `updated_at`, remove the game, save, and send a callback message only when a bot-facing callback has been registered.

- [ ] **Step 6: Run service tests**

Run all Task 1–6 tests.

Expected: all tests pass and no JSON files appear inside the repository.

- [ ] **Step 7: Commit persistence and service**

```bash
git add plugins/airi_point_salad/persistence.py plugins/airi_point_salad/service.py
git commit -m "feat: persist point salad games"
```

### Task 7: Render v2 cards, boards, help, and results

**Files:**
- Create: `plugins/airi_point_salad/renderer.py`
- Test: `/tmp/airi_point_salad_tests/test_renderer.py`

- [ ] **Step 1: Write failing render-contract tests**

Create `/tmp/airi_point_salad_tests/test_renderer.py`:

```python
import base64
from io import BytesIO

from PIL import Image

from plugins.airi_point_salad.models import Character
from plugins.airi_point_salad.renderer import CARD_SIZE, image_b64, render_character_front, render_score_back


def test_card_ratio_and_base64(sample_card):
    front = render_character_front(Character.MIKU)
    back = render_score_back(sample_card)
    assert front.size == CARD_SIZE == (750, 1050)
    assert back.size == CARD_SIZE
    payload = image_b64(front)
    assert payload.startswith("base64://")
    decoded = Image.open(BytesIO(base64.b64decode(payload[9:])))
    assert decoded.size == CARD_SIZE
```

Add board tests for classic/mix section presence, current-player detail, result breakdown, image width bounds, and encoded byte length below 3 MB for a six-player standard game.

- [ ] **Step 2: Run tests and verify they fail**

Run Task 7 tests with the airidev Python.

Expected: FAIL because `renderer.py` does not exist.

- [ ] **Step 3: Implement asset loading and role icons**

Use `utils.asset_cache.get_image_copy` and `get_font`. Define stable paths from `Path(__file__).parent / "assets"`. Keep per-character normalized crop boxes in one mapping. `render_character_icon(character, size)` crops the face, centers it in a colored medallion, adds a gold rim, and draws the Latin initial.

- [ ] **Step 4: Implement v2 card fronts and backs**

Use constants:

```python
CARD_SIZE = (750, 1050)
CARD_RADIUS = 28
GOLD = (205, 171, 96, 255)
INNER_GOLD = (235, 209, 143, 210)
```

`render_character_front` creates the role-specific gradient, subtle rays, two clean gold frames, scaled supplied full-body art, and a bottom nameplate. `render_score_back` creates the ivory/pastel background, faint repeating texture, two gold frames, logo header, centered rule panel, character medallions, one-line Chinese rule, and large score value. Keep the approved v2 density; do not add later floral mockup variants.

- [ ] **Step 5: Implement board and result composition**

`render_board(state, viewer_id)` composes mode/round/deck status, current turn, three market columns, mix-only Missions, compact player rows, the current player's detailed holdings, and one command hint. `render_result(state)` composes ranked players and every `ScoreBreakdown` line. Use JPEG quality reduction from 92 to 82 until encoded bytes are at most 3 MB, without lowering below 82.

- [ ] **Step 6: Run automated renderer tests and inspect real images**

Run Task 7 tests, then generate one front, one back, one classic board, one mix board, and one result image under `/tmp/airi_point_salad_preview/`. Open each with the local image viewer tool and verify text does not overlap, card ratio is 5:7, supplied art is not clipped at the face, and v2 borders remain visible at board scale.

Expected: all automated tests pass and all five previews are visually readable.

- [ ] **Step 7: Commit renderer**

```bash
git add plugins/airi_point_salad/renderer.py
git commit -m "feat: render point salad cards and boards"
```

### Task 8: Integrate NoneBot and global help

**Files:**
- Create: `plugins/airi_point_salad/__init__.py`
- Modify: `plugins/airi_help/__init__.py`
- Test: `/tmp/airi_point_salad_tests/test_plugin.py`

- [ ] **Step 1: Write the failing plugin-load and handler test**

Create `/tmp/airi_point_salad_tests/test_plugin.py` that initializes NoneBot, registers OneBot V11, loads `plugins.airi_point_salad`, asserts one matcher recognizes `sl`, `salad`, and `沙拉`, stubs `MessageSegment.image`, and drives create/join/start/take handlers with fake group events.

The assertions must verify that mutation replies contain exactly one `base64://` image, private messages return `该游戏仅支持群聊`, and parsing errors remain Chinese text without changing stored state.

- [ ] **Step 2: Run the test and verify it fails**

Run Task 8 tests with the airidev Python.

Expected: FAIL because the plugin entry point does not exist.

- [ ] **Step 3: Implement the thin matcher adapter**

Register:

```python
salad = on_regex(
    r"^\s*(?:沙拉|salad|sl)(?:\s+|$)",
    flags=re.IGNORECASE,
    priority=12,
    block=True,
)
```

Create one `GameService(GameStore(Path("data/airi_point_salad/games.json")))`. The handler extracts `group_id`, `user_id`, sender card/nickname, and `event.sender.role in {"owner", "admin"}`. It parses the command, passes the appropriate renderer as the mutating service method's `prepare` callback, and sends the returned image via `MessageSegment.image(base64_string)`. Read-only board rendering uses an immutable state snapshot. A rendering exception therefore occurs before persistence and rolls the mutation back.

Register driver startup/shutdown hooks to load and save, and a timeout callback that sends a Chinese group message through the bot selected for that group. If no bot is currently connected, retain the cleaned persisted state and only log the timeout.

- [ ] **Step 4: Add plugin metadata and Chinese help**

Add `PluginMetadata` with name `MORE MORE JUMP！得分沙拉`, a Chinese description, and usage containing the three equivalent create examples. Update `plugins/airi_help/__init__.py` entertainment section with:

```text
- MORE MORE JUMP！Point Salad:
2–6 人群聊选牌桌游 By AiriCore Dev.
* 指令：沙拉 规则 / sl rl
```

- [ ] **Step 5: Run end-to-end handler tests**

Run Task 8 tests plus every earlier temporary test.

Expected: all tests pass, images are base64, and no handler accepts unrelated messages.

- [ ] **Step 6: Commit integration**

```bash
git add plugins/airi_point_salad/__init__.py plugins/airi_help/__init__.py
git commit -m "feat: integrate point salad plugin"
```

### Task 9: Full verification, memory, and cleanup

**Files:**
- Create: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-point-salad.md`
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/MEMORY.md`
- Remove: `/tmp/airi_point_salad_tests/`
- Remove: `/tmp/airi_point_salad_preview/`

- [ ] **Step 1: Run the complete temporary test suite**

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m pytest /tmp/airi_point_salad_tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Run syntax and plugin-load verification**

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m compileall -q plugins/airi_point_salad
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -c 'import nonebot; nonebot.init(); p = nonebot.load_plugin("plugins.airi_point_salad"); assert p is not None; print("point salad plugin loaded")'
```

Expected: compilation emits no output and plugin load prints `point salad plugin loaded`.

- [ ] **Step 3: Run AiriCore full plugin loading**

Use a temporary Python driver that calls `nonebot.init()`, registers OneBot V11, loads required dependencies used by the repository, then calls `nonebot.load_plugins("plugins")` and reports every failed plugin. Keep this driver under `/tmp`.

Expected: `airi_point_salad` loads and the repository has no newly introduced plugin-load failure.

- [ ] **Step 4: Run source policy checks**

```bash
rg -n 'file://|MessageSegment\.image\([^)]*(Path|str\(|ASSET|PLUGIN_DIR)' plugins/airi_point_salad
rg -n '#|"""|\x27\x27\x27' plugins/airi_point_salad --glob '*.py'
rg -n '桃井 Airi|爱莉' plugins/airi_point_salad plugins/airi_help/__init__.py
```

Expected: no local-path image send, no code comments/docstrings, no `桃井 Airi`; `爱莉` appears only as the correct character name `桃井爱莉`.

- [ ] **Step 5: Verify working-tree scope**

```bash
git status --short
git diff --check
git diff --stat HEAD~6..HEAD
```

Expected: only intended plugin/help/memory changes from this feature are included; the pre-existing `.gitignore` edit and `plugins/airi_market/posts/airicore-v26-8-oeschinen/` remain untouched.

- [ ] **Step 6: Update project memory**

Write `airi-point-salad.md` with the final module boundaries, four modes, alias table, skill flows, persistence path, timeout behavior, base64 renderer, verification counts, and any discovered pitfalls. Add one link under `## 插件实现` in `MEMORY.md`.

- [ ] **Step 7: Synchronize directory modification time**

Find the newest real source or asset file under `plugins/airi_point_salad`, excluding `__pycache__`, `.pyc`, `.pk`, `.log`, and `.DS_Store`, then run:

```bash
latest_point_salad_file="$(find plugins/airi_point_salad -type f ! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '*.pyo' ! -name '*.pk' ! -name '*.log' ! -name '.DS_Store' -exec stat -f '%m %N' {} + | sort -nr | head -1 | cut -d' ' -f2-)"
test -n "$latest_point_salad_file"
touch -r "$latest_point_salad_file" plugins/airi_point_salad
```

Expected: `stat` reports the plugin directory mtime equal to its newest real file.

- [ ] **Step 8: Remove temporary artifacts**

Delete only these verified targets:

```text
/tmp/airi_point_salad_tests
/tmp/airi_point_salad_preview
```

Confirm both paths no longer exist. Do not delete repository tests or user files.

- [ ] **Step 9: Commit memory and final adjustments**

```bash
git add plugins/airi_point_salad plugins/airi_help/__init__.py
git commit -m "chore: finalize point salad plugin"
```

Memory files live outside the repository and are updated without staging. If no repository file changed after Task 8, skip the empty commit and report the last feature commit instead.
