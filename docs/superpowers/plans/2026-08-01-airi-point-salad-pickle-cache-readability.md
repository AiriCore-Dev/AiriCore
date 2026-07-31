# Airi Point Salad 持久化、缓存与可读性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将得分沙拉改为安全的 pickle 对局存档，接入三档渲染缓存，提升桌面与牌背可读性，并在新玩家轮次开始时用一条消息发送提醒和图片。

**Architecture:** `GameStore` 继续保存纯字典状态，只把磁盘编码从 JSON 改为 pickle，并提供旧 JSON 单次迁移。`renderer.py` 用注册到统一统计的 `ByteLRU` 缓存稳定卡面组件，完整桌面保持即时渲染。`GameService` 在群锁内比较变更前后当前玩家，适配层用结构化响应组合 `@玩家 + 图片`。

**Tech Stack:** Python 3.11、asyncio、pickle、Pillow、NoneBot OneBot V11、unittest、AiriCore `ByteLRU`

---

设计依据：`docs/superpowers/specs/2026-08-01-airi-point-salad-pickle-cache-design.md`

临时回归统一写入 `/tmp/airicore_test_airi_point_salad_upgrade.py`，验证完成后删除，不提交测试文件或生成图片。

### Task 1: 将对局存档迁移到 pickle

**Files:**
- Modify: `plugins/airi_point_salad/persistence.py:1-91`
- Modify: `plugins/airi_point_salad/service.py:27-30`
- Modify: `plugins/airi_point_salad/__init__.py:41-43`
- Test: `/tmp/airicore_test_airi_point_salad_upgrade.py`

- [ ] **Step 1: 写入 pickle 纯字典往返失败测试**

使用 `apply_patch` 新建临时测试，先验证磁盘内容可由 pickle 解码且不包含 `GameState` 实例：

```python
import asyncio
import json
import pickle
from pathlib import Path
import tempfile
import unittest

import nonebot

nonebot.init()

from plugins.airi_point_salad.game import create_game
from plugins.airi_point_salad.models import GameMode, GameSpeed, GameState
from plugins.airi_point_salad.persistence import GameStore


def sample_state(group_id="100"):
    return create_game(
        group_id,
        "1",
        "A",
        GameSpeed.QUICK,
        GameMode.CLASSIC,
        7,
        100.0,
    )


class PersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_pickle_round_trip_uses_plain_dict(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "games.pk"
            store = GameStore(path)
            await store.save({"100": sample_state()})
            with path.open("rb") as file:
                payload = pickle.load(file)
            self.assertEqual(type(payload), dict)
            self.assertEqual(type(payload["100"]), dict)
            restored = await store.load()
            self.assertEqual(restored["100"].to_dict(), sample_state().to_dict())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认 RED**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py -v`

Expected: `test_pickle_round_trip_uses_plain_dict` FAIL，现有 `.pk` 文件实际写入 JSON，`pickle.load` 无法解码。

- [ ] **Step 3: 最小实现 pickle 写入和读取**

在 `persistence.py` 中保留 JSON 仅用于迁移读取，生产存档使用以下核心实现：

```python
import pickle


class GameStore:
    def __init__(self, path: Path):
        self.path = path
        self.backup_path = path.with_suffix(path.suffix + ".bak")
        self.legacy_path = path.with_suffix(".json")
        self.legacy_backup_path = self.legacy_path.with_suffix(
            self.legacy_path.suffix + ".bak"
        )
        self._save_lock = asyncio.Lock()

    def _decode(self, payload) -> dict[str, GameState]:
        if type(payload) is not dict:
            raise TypeError("存档根节点必须是对象")
        return {
            self._group_id(group_id): GameState.from_dict(state)
            for group_id, state in payload.items()
        }

    def _read_pickle(self, path: Path) -> dict[str, GameState]:
        with path.open("rb") as file:
            return self._decode(pickle.load(file))

    def _write_atomic(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=".games-",
            suffix=self.path.suffix,
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(fd, "wb") as file:
                pickle.dump(payload, file, protocol=pickle.HIGHEST_PROTOCOL)
                file.flush()
                os.fsync(file.fileno())
            if self.path.exists():
                shutil.copyfile(self.path, self.backup_path)
            os.replace(temporary_path, self.path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
```

将 `GameService` 默认路径和 `__init__.py` 显式路径都改为：

```python
GameStore(Path("data/airi_point_salad/games.pk"))
```

- [ ] **Step 4: 运行测试并确认 GREEN**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py -v`

Expected: `test_pickle_round_trip_uses_plain_dict` PASS。

- [ ] **Step 5: 添加旧 JSON 迁移、备份恢复和坏档隔离失败测试**

在 `PersistenceTests` 中加入：

```python
    async def test_migrates_legacy_json_without_deleting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "games.json"
            with legacy.open("w", encoding="utf-8") as file:
                json.dump({"100": sample_state().to_dict()}, file)
            restored = await GameStore(root / "games.pk").load()
            self.assertEqual(restored["100"].to_dict(), sample_state().to_dict())
            self.assertTrue((root / "games.pk").exists())
            self.assertTrue(legacy.exists())

    async def test_pickle_backup_recovers_corrupt_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "games.pk"
            store = GameStore(path)
            first = sample_state()
            second = sample_state()
            second.updated_at = 200.0
            await store.save({"100": first})
            await store.save({"100": second})
            path.write_bytes(b"broken")
            restored = await store.load()
            self.assertEqual(restored["100"].updated_at, 100.0)

    async def test_corrupt_pickle_primary_is_quarantined(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "games.pk"
            backup = root / "games.pk.bak"
            path.write_bytes(b"broken-primary")
            backup.write_bytes(b"broken-backup")
            restored = await GameStore(path).load()
            self.assertEqual(restored, {})
            self.assertFalse(path.exists())
            self.assertEqual(len(list(root.glob("games.corrupt.*.pk"))), 1)

    async def test_legacy_backup_is_used_when_legacy_primary_is_corrupt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "games.json").write_text("broken", encoding="utf-8")
            with (root / "games.json.bak").open("w", encoding="utf-8") as file:
                json.dump({"100": sample_state().to_dict()}, file)
            restored = await GameStore(root / "games.pk").load()
            self.assertIn("100", restored)
            self.assertTrue((root / "games.pk").exists())
```

- [ ] **Step 6: 运行新增测试并确认 RED**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py -v`

Expected: 迁移和动态 `.pk` 隔离测试 FAIL，因为加载流程尚未处理新旧主备组合。

- [ ] **Step 7: 实现主备加载、JSON 迁移与动态隔离**

在 `GameStore` 中加入并从 `load` 调用：

```python
    async def load(self) -> dict[str, GameState]:
        if self.path.exists() or self.backup_path.exists():
            games = await self._load_pair(
                self.path,
                self.backup_path,
                self._read_pickle,
            )
            return games if games is not None else {}
        if self.legacy_path.exists() or self.legacy_backup_path.exists():
            games = await self._load_pair(
                self.legacy_path,
                self.legacy_backup_path,
                self._read_json,
            )
            if games is not None:
                await self.save(games)
                logger.info("得分沙拉旧 JSON 存档已迁移为 pickle")
                return games
        return {}

    async def _load_pair(self, primary, backup, reader):
        if primary.exists():
            try:
                return await asyncio.to_thread(reader, primary)
            except Exception as primary_error:
                logger.error(f"得分沙拉主存档读取失败：{primary_error}")
        if backup.exists():
            try:
                games = await asyncio.to_thread(reader, backup)
                logger.warning("得分沙拉已从备份存档恢复")
                return games
            except Exception as backup_error:
                logger.error(f"得分沙拉备份存档读取失败：{backup_error}")
        if primary.exists():
            await self._quarantine(primary)
        return None

    async def _quarantine(self, path: Path) -> None:
        stamp = time.strftime("%Y%m%dT%H%M%S")
        quarantine = path.with_name(f"games.corrupt.{stamp}{path.suffix}")
        try:
            await asyncio.to_thread(os.replace, path, quarantine)
            logger.error(f"得分沙拉坏档已隔离为 {quarantine.name}")
        except OSError as error:
            logger.error(f"得分沙拉坏档隔离失败：{error}")

    def _read_json(self, path: Path) -> dict[str, GameState]:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file, parse_constant=self._reject_constant)
        return self._decode(payload)
```

- [ ] **Step 8: 运行持久化测试并确认 GREEN**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py -v`

Expected: 5 tests PASS。

- [ ] **Step 9: 提交持久化修改**

```bash
git add plugins/airi_point_salad/persistence.py plugins/airi_point_salad/service.py plugins/airi_point_salad/__init__.py
git commit -m "fix: migrate point salad storage to pickle"
```

### Task 2: 接入三档渲染缓存

**Files:**
- Modify: `plugins/airi_point_salad/renderer.py:1-147`
- Test: `/tmp/airicore_test_airi_point_salad_upgrade.py`

- [ ] **Step 1: 添加 ram 缓存命中失败测试**

在临时测试中加入导入和测试类：

```python
from utils import cache_mode
from utils.cache_mode import get_cache_stats
from plugins.airi_point_salad.models import Card, Character, RuleKind, ScoreRule
from plugins.airi_point_salad import renderer


class RenderCacheTests(unittest.TestCase):
    def setUp(self):
        self.previous_mode = cache_mode._mode

    def tearDown(self):
        cache_mode._mode = self.previous_mode
        cache = getattr(renderer, "_render_cache", None)
        if cache is not None:
            cache.clear()

    def test_ram_mode_reuses_rendered_character_front(self):
        cache_mode._mode = "ram"
        before = get_cache_stats().get("point_salad.rendered", {}).get("hits", 0)
        first = renderer.render_character_front(Character.AIRI)
        second = renderer.render_character_front(Character.AIRI)
        after = get_cache_stats().get("point_salad.rendered", {}).get("hits", 0)
        self.assertGreater(after, before)
        self.assertIsNot(first, second)
        first.putpixel((0, 0), (255, 0, 0, 255))
        self.assertNotEqual(first.getpixel((0, 0)), second.getpixel((0, 0)))
```

- [ ] **Step 2: 运行测试并确认 RED**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py RenderCacheTests.test_ram_mode_reuses_rendered_character_front -v`

Expected: FAIL，统一缓存统计中没有 `point_salad.rendered`，命中数不增长。

- [ ] **Step 3: 实现最小 ram 卡面缓存**

在 `renderer.py` 增加：

```python
from utils.cache_mode import (
    get_cache_budget_bytes,
    is_balanced,
    is_disk,
    is_ram,
    register_cache,
)
from utils.cache_policy import ByteLRU, value_bytes


_render_cache = ByteLRU(
    get_cache_budget_bytes("images"),
    owner="point_salad.rendered",
)
register_cache("point_salad.rendered", _render_cache)


def _configure_render_cache():
    _render_cache.max_bytes = 0 if is_ram() else get_cache_budget_bytes("images")
    _render_cache.probationary = is_balanced()


def _cached_image(key, build):
    if is_disk():
        _render_cache.clear()
        return build()
    _configure_render_cache()
    cached = _render_cache.get(key)
    if cached is not None:
        return cached.copy()
    image = build()
    _render_cache.put(key, image, value_bytes(image))
    return image.copy()
```

先只把现有角色面函数体移入 `_build_character_front`，公开函数通过嵌套 `build` 调用 `_cached_image`。角色面入口为：

```python
def render_character_front(character: Character) -> Image.Image:
    def build():
        return _build_character_front(character)

    return _cached_image(("character_front", character.value), build)
```

- [ ] **Step 4: 运行 ram 测试并确认 GREEN**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py RenderCacheTests.test_ram_mode_reuses_rendered_character_front -v`

Expected: PASS。

- [ ] **Step 5: 添加 balanced、disk 和规则签名失败测试**

在 `RenderCacheTests` 中加入：

```python
    def test_balanced_uses_probation_then_hits(self):
        cache_mode._mode = "balanced"
        renderer._render_cache.clear()
        start = renderer._render_cache.stats()
        renderer.render_character_front(Character.HARUKA)
        renderer.render_character_front(Character.HARUKA)
        middle = renderer._render_cache.stats()
        renderer.render_character_front(Character.HARUKA)
        end = renderer._render_cache.stats()
        self.assertGreater(middle["skips"], start["skips"])
        self.assertGreater(middle["admissions"], start["admissions"])
        self.assertGreater(end["hits"], middle["hits"])

    def test_disk_mode_clears_and_bypasses_render_cache(self):
        cache_mode._mode = "ram"
        renderer.render_character_front(Character.MINORI)
        self.assertGreater(renderer._render_cache.stats()["items"], 0)
        cache_mode._mode = "disk"
        renderer.render_character_front(Character.MINORI)
        renderer.render_character_front(Character.MINORI)
        self.assertEqual(renderer._render_cache.stats()["items"], 0)

    def test_score_back_reuses_complete_rule_key(self):
        cache_mode._mode = "ram"
        first = Card(
            "same-id",
            Character.AIRI,
            ScoreRule(RuleKind.EACH, [Character.AIRI], 2),
        )
        second = Card(
            "same-id",
            Character.AIRI,
            ScoreRule(RuleKind.EACH, [Character.AIRI], 9),
        )
        before = renderer._render_cache.stats()["hits"]
        first_image = renderer.render_score_back(first)
        renderer.render_score_back(first)
        second_image = renderer.render_score_back(second)
        after = renderer._render_cache.stats()["hits"]
        self.assertGreater(after, before)
        self.assertNotEqual(first_image.tobytes(), second_image.tobytes())
```

- [ ] **Step 6: 运行新增测试并确认 RED**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py RenderCacheTests -v`

Expected: `test_score_back_reuses_complete_rule_key` FAIL，因为计分牌尚未进入缓存；balanced 和 disk 的角色面行为继续接受验证。

- [ ] **Step 7: 完成三种组件的模式感知缓存键**

使用以下入口和计分规则键：

```python
def render_character_icon(character: Character, size: int = 100) -> Image.Image:
    def build():
        return _build_character_icon(character, size)

    return _cached_image(("character_icon", character.value, size), build)


def _score_cache_key(card: Card):
    rule = card.rule
    return (
        "score_back",
        card.card_id,
        rule.kind.value,
        tuple(character.value for character in rule.characters),
        rule.points,
        rule.penalty,
        rule.relation,
    )


def render_score_back(card: Card) -> Image.Image:
    def build():
        return _build_score_back(card)

    return _cached_image(_score_cache_key(card), build)
```

- [ ] **Step 8: 运行全部缓存测试并确认 GREEN**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py RenderCacheTests -v`

Expected: 4 tests PASS，返回图片互不共享，三种模式统计符合预期。

- [ ] **Step 9: 提交缓存修改**

```bash
git add plugins/airi_point_salad/renderer.py
git commit -m "feat: cache point salad rendered cards"
```

### Task 3: 放大牌背和单图桌面

**Files:**
- Modify: `plugins/airi_point_salad/renderer.py:23-25,131-147,176-250,282-297`
- Test: `/tmp/airicore_test_airi_point_salad_upgrade.py`
- Generate: `/tmp/airi_point_salad_board.jpg`
- Generate: `/tmp/airi_point_salad_cards.png`

- [ ] **Step 1: 添加视觉尺寸和最坏桌面失败测试**

在临时测试中加入：

```python
import base64
from io import BytesIO

from PIL import Image

from plugins.airi_point_salad.game import add_player, start_game


def decode_image(data):
    raw = base64.b64decode(data.removeprefix("base64://"))
    return raw, Image.open(BytesIO(raw)).copy()


def worst_board_state():
    state = sample_state()
    state.mode = GameMode.MIX
    for index in range(2, 7):
        add_player(state, str(index), chr(64 + index), 100.0 + index)
    start_game(state, "1", 200.0)
    state.players[0].score_cards = list(state.cards)[:18]
    return state


class ReadabilityTests(unittest.TestCase):
    def test_card_back_readability_constants(self):
        self.assertEqual(getattr(renderer, "SCORE_ICON_SIZE", None), 204)
        self.assertEqual(getattr(renderer, "SCORE_RULE_FONT_SIZE", None), 72)
        self.assertEqual(getattr(renderer, "SCORE_VALUE_FONT_SIZE", None), 120)

    def test_worst_board_is_2160_wide_and_under_three_mb(self):
        raw, image = decode_image(renderer.render_board(worst_board_state(), "1"))
        self.assertEqual(image.width, 2160)
        self.assertGreaterEqual(image.height, 4000)
        self.assertLessEqual(len(raw), 3 * 1024 * 1024)
```

- [ ] **Step 2: 运行测试并确认 RED**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py ReadabilityTests -v`

Expected: 2 tests FAIL，当前没有目标常量且桌面宽度为 1350。

- [ ] **Step 3: 放大牌背内部元素**

在 `renderer.py` 定义并用于 `_build_score_back`：

```python
SCORE_ICON_SIZE = 204
SCORE_RULE_FONT_SIZE = 72
SCORE_VALUE_FONT_SIZE = 120


def _build_score_back(card: Card) -> Image.Image:
    image = get_image_copy(BACK_BASE_PATH).convert("RGBA")
    title = get_image_copy(TITLE_PATH).convert("RGBA")
    title.thumbnail((500, 210), Image.Resampling.LANCZOS)
    image.alpha_composite(title, ((CARD_SIZE[0] - title.width) // 2, 28))
    draw = ImageDraw.Draw(image)
    icons = [
        render_character_icon(character, SCORE_ICON_SIZE)
        for character in card.rule.characters
    ]
    gap = 12
    total_width = len(icons) * SCORE_ICON_SIZE + max(0, len(icons) - 1) * gap
    icon_x = (CARD_SIZE[0] - total_width) // 2
    for icon in icons:
        image.alpha_composite(icon, (icon_x, 285))
        icon_x += SCORE_ICON_SIZE + gap
    text, score = rule_text(card)
    draw.multiline_text(
        (375, 600),
        text,
        font=font(SCORE_RULE_FONT_SIZE),
        anchor="mm",
        align="center",
        fill=(65, 51, 68),
        spacing=12,
    )
    draw.text(
        (375, 810),
        score,
        font=font(SCORE_VALUE_FONT_SIZE),
        anchor="mm",
        fill=(181, 87, 137),
    )
    draw.text(
        (375, 985),
        card.card_id.upper(),
        font=font(32),
        anchor="mm",
        fill=(117, 98, 119),
    )
    return image
```

- [ ] **Step 4: 重排 2160px 桌面**

在 `render_board` 中采用这些固定布局值，并保持所有现有信息：

```python
BOARD_WIDTH = 2160
MARKET_SCORE_SIZE = (432, 605)
MARKET_CHARACTER_SIZE = (252, 353)
MARKET_X = (120, 864, 1608)
MARKET_SCORE_Y = 520
MARKET_CHARACTER_Y = 1170
MARKET_CHARACTER_STEP = 390
SECTION_Y = 2030
PLAYER_ROW_HEIGHT = 116
DETAIL_LINE_HEIGHT = 52
```

动态高度和区块起点必须按以下公式计算：

```python
mission_height = 280 if state.mode is GameMode.MIX else 0
player_header_y = SECTION_Y + mission_height
player_rows_y = player_header_y + 80
detail_y = player_rows_y + len(state.players) * PLAYER_ROW_HEIGHT + 80
detail_lines = max(1, len(current.score_cards))
height = max(
    3100 if state.mode is GameMode.MIX else 2800,
    detail_y + detail_lines * DETAIL_LINE_HEIGHT + 230,
)
```

绘制尺寸使用以下确定值：页眉标题最大 `520×230`，模式 `58px`，回合 `46px`，当前玩家 `52px`，Center `36px`，列标 `60px`，槽位编号 `42px`，Mission 标题 `48px`、正文 `36px`、分值 `42px`，玩家标题 `48px`、姓名 `38px`、摘要 `34px`，持牌标题 `42px`、明细 `32px`、角色统计 `34px`、底部指令 `32px`。三列分别以 `MARKET_X` 为计分牌左边界，角色牌在列内居中。

把 JPEG 自适应下限扩到 40，保持分辨率不降级：

```python
    quality = 92
    data = b""
    while quality >= 40:
        buffer = BytesIO()
        flattened.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()
        if len(data) <= 3 * 1024 * 1024:
            break
        quality -= 2
```

- [ ] **Step 5: 运行尺寸与体积测试并确认 GREEN**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py ReadabilityTests -v`

Expected: 2 tests PASS，最坏桌面宽 2160、动态高度不低于 4000、JPEG 不超过 3 MB。

- [ ] **Step 6: 生成真实预览并进行视觉检查**

在 `ReadabilityTests` 增加以下预览生成测试：

```python
    def test_write_visual_previews(self):
        state = worst_board_state()
        board_raw, _ = decode_image(renderer.render_board(state, "1"))
        Path("/tmp/airi_point_salad_board.jpg").write_bytes(board_raw)
        by_kind = {}
        for card in state.cards.values():
            by_kind.setdefault(card.rule.kind, card)
        sheet = Image.new("RGBA", (CARD_SIZE[0] * 5, CARD_SIZE[1]))
        for index, kind in enumerate(RuleKind):
            sheet.alpha_composite(
                renderer.render_score_back(by_kind[kind]),
                (index * CARD_SIZE[0], 0),
            )
        sheet.save("/tmp/airi_point_salad_cards.png")
        self.assertTrue(Path("/tmp/airi_point_salad_board.jpg").exists())
        self.assertTrue(Path("/tmp/airi_point_salad_cards.png").exists())
```

同时把 `CARD_SIZE` 加入测试导入：`from plugins.airi_point_salad.renderer import CARD_SIZE`。运行后使用 `view_image` 检查：三列不重叠、A1–C2 清晰、三角色图标完整、两行风险规则不覆盖分值、玩家区和 18 条持牌明细完整。

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py ReadabilityTests -v`

Expected: 3 tests PASS；两张预览人工检查无裁切和重叠。

- [ ] **Step 7: 提交可读性修改**

```bash
git add plugins/airi_point_salad/renderer.py
git commit -m "feat: improve point salad board readability"
```

### Task 4: 仅在新轮次开始时发送单条提醒图片

**Files:**
- Modify: `plugins/airi_point_salad/service.py:176-208`
- Modify: `plugins/airi_point_salad/__init__.py:1-136`
- Test: `/tmp/airicore_test_airi_point_salad_upgrade.py`

- [ ] **Step 1: 添加轮次边界失败测试**

在临时测试中加入：

```python
from plugins.airi_point_salad.service import GameService


class MemoryStore:
    async def load(self):
        return {}

    async def save(self, games):
        self.games = games


class FailingStore(MemoryStore):
    async def save(self, games):
        raise OSError("save failed")


class TurnReminderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = GameService(MemoryStore())
        await self.service.create(
            "100",
            "1",
            "A",
            GameSpeed.QUICK,
            GameMode.CLASSIC,
            seed=7,
        )
        await self.service.join("100", "2", "B")

    async def asyncTearDown(self):
        self.service.close()

    async def test_start_and_turn_advance_report_new_player_only(self):
        seen = []

        def prepare(state, *metadata):
            seen.append(metadata[0] if metadata else None)
            return "image"

        await self.service.start("100", "1", prepare=prepare)
        self.assertEqual(seen[-1], "1")
        score_id = self.service.games["100"].score_market[0]
        self.service.games["100"].players[0].score_cards.append(score_id)
        await self.service.flip("100", "1", 0, prepare=prepare)
        self.assertIsNone(seen[-1])
        await self.service.take("100", "1", [(0, 0), (0, 1)], prepare=prepare)
        self.assertEqual(seen[-1], "2")

    async def test_finishing_game_has_no_next_player_notice(self):
        seen = []

        def prepare(state, *metadata):
            seen.append(metadata[0] if metadata else None)
            return "image"

        await self.service.start("100", "1")
        state = self.service.games["100"]
        state.deck = []
        state.score_market = [state.score_market[0], None, None]
        state.character_market = [[None, None] for _ in range(3)]
        await self.service.take("100", "1", [0], prepare=prepare)
        self.assertIsNone(seen[-1])

    async def test_save_failure_returns_no_prepared_notice(self):
        await self.service.start("100", "1")
        self.service.store = FailingStore()
        with self.assertRaises(OSError):
            await self.service.take(
                "100",
                "1",
                [(0, 0), (0, 1)],
                prepare=lambda state, *metadata: metadata[0],
            )
        state = self.service.games["100"]
        self.assertEqual(state.players[state.current_player].user_id, "1")
```

- [ ] **Step 2: 运行服务测试并确认 RED**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py TurnReminderTests -v`

Expected: FAIL，现有 `prepare` 只收到状态，捕获的提醒 ID 为 `None`。

- [ ] **Step 3: 在事务内计算新轮次玩家**

在 `GameService` 中加入：

```python
    @staticmethod
    def _turn_user_id(state: GameState | None) -> str | None:
        if state is None or state.phase is not Phase.PLAYING:
            return None
        return state.players[state.current_player].user_id
```

在 `_mutate` 中渲染前计算差异并作为第二个参数传给 `prepare`：

```python
            before_turn_user_id = self._turn_user_id(before)
            try:
                result = operation()
                after_turn_user_id = self._turn_user_id(result)
                turn_user_id = (
                    after_turn_user_id
                    if after_turn_user_id != before_turn_user_id
                    else None
                )
                prepared = result
                if prepare is not None:
                    prepared = await asyncio.to_thread(
                        prepare,
                        copy.deepcopy(result),
                        turn_user_id,
                    )
                await self.store.save(self.games)
```

- [ ] **Step 4: 运行服务测试并确认 GREEN**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py TurnReminderTests -v`

Expected: 3 tests PASS；首回合为 `1`，翻牌为 `None`，完成行动后为 `2`，结算和保存失败都不产生可发送提醒。

- [ ] **Step 5: 添加单条 OneBot 消息失败测试**

在临时测试中延迟导入插件模块并加入：

```python
import plugins.airi_point_salad as point_salad


class MessageCompositionTests(unittest.TestCase):
    def test_turn_notice_is_one_message_with_at_then_image(self):
        response = point_salad.CommandResponse("base64://AA==", "2")
        message = point_salad.response_message(response)
        self.assertEqual([segment.type for segment in message], ["at", "image"])

    def test_board_refresh_image_has_no_at_segment(self):
        response = point_salad.CommandResponse("base64://AA==")
        message = point_salad.response_message(response)
        self.assertEqual(message.type, "image")
```

- [ ] **Step 6: 运行消息测试并确认 RED**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py MessageCompositionTests -v`

Expected: FAIL，`CommandResponse` 和 `response_message` 尚不存在。

- [ ] **Step 7: 实现结构化响应和单消息组合**

在 `__init__.py` 加入：

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandResponse:
    body: str
    turn_user_id: str | None = None


def response_message(response: CommandResponse):
    if not response.body.startswith("base64://"):
        return response.body
    image = MessageSegment.image(response.body)
    if response.turn_user_id is None:
        return image
    return MessageSegment.at(response.turn_user_id) + image
```

把 `execute_command` 的 `prepare` 和非变更分支统一包装：

```python
    def prepare(state, turn_user_id):
        return CommandResponse(render_state(state, user_id), turn_user_id)

    if command.action == "board":
        state = await service.board_state(group_id)
        body = await asyncio.to_thread(render_state, state, user_id)
        return CommandResponse(body)
    if command.action == "rules":
        return CommandResponse(await service.rules_text(group_id))
```

异常分支改为 `CommandResponse(str(error))`，处理器结尾统一执行：

```python
    await salad.finish(response_message(response))
```

- [ ] **Step 8: 运行轮次与消息测试并确认 GREEN**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py TurnReminderTests MessageCompositionTests -v`

Expected: 5 tests PASS，提醒由一个包含 `at`、`image` 两段的消息发送，主动桌面图片没有 `at`。

- [ ] **Step 9: 提交轮次提醒修改**

```bash
git add plugins/airi_point_salad/service.py plugins/airi_point_salad/__init__.py
git commit -m "feat: mention players at point salad turn start"
```

### Task 5: 全量验证、清理和项目记忆

**Files:**
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-point-salad.md`
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/MEMORY.md` only if the index description needs the new persistence/cache/readability summary
- Delete: `/tmp/airicore_test_airi_point_salad_upgrade.py`
- Delete: `/tmp/airi_point_salad_board.jpg`
- Delete: `/tmp/airi_point_salad_cards.png`

- [ ] **Step 1: 运行完整临时回归**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airicore_test_airi_point_salad_upgrade.py -v`

Expected: 全部测试 PASS，无异常或资源警告。

- [ ] **Step 2: 运行 Ruff、AST 和隔离编译**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m ruff check plugins/airi_point_salad`

Expected: `All checks passed!`

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -c 'import ast, pathlib; files=list(pathlib.Path("plugins/airi_point_salad").rglob("*.py")); [ast.parse(path.read_text(encoding="utf-8"), filename=str(path)) for path in files]; print(f"AST {len(files)}/{len(files)}")'`

Expected: `AST 12/12`，若文件数变化则分子分母一致。

Run: `PYTHONPYCACHEPREFIX=/tmp/airicore_point_salad_pycache /opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m compileall -q plugins/airi_point_salad`

Expected: exit 0。

- [ ] **Step 3: 运行真实插件加载验证**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -c 'import nonebot; nonebot.init(); loaded=nonebot.load_plugins("plugins"); failed=[item for item in loaded if item is None]; print(f"loaded={len(loaded)} failed={len(failed)}")'`

Expected: 项目插件全部加载，`failed=0`。

- [ ] **Step 4: 检查目标差异和用户改动隔离**

Run: `git show --check --oneline HEAD~4..HEAD`

Expected: exit 0。

Run: `git status --short`

Expected: 只看到任务开始前用户已有的 `.gitignore`、`plugins/airi_help/__init__.py`、`plugins/airi_status/drawer.py` 修改；不得把这些用户修改纳入本任务提交。

- [ ] **Step 5: 更新项目记忆**

在 `airi-point-salad.md` 追加 2026-08-01 条目，记录：`games.pk` 保存纯字典、旧 JSON 自动迁移、主备与坏档语义；`point_salad.rendered` 的 ram/balanced/disk 行为；2160px 桌面与 204/72/120 牌背规格；只在新轮次开始时发送单条 `@玩家 + 图片`；完整验证结果。若 `MEMORY.md` 的索引摘要不能覆盖这些信息，同步更新该索引行。

- [ ] **Step 6: 同步插件目录时间并验证幂等**

本计划最后修改的插件文件是 `__init__.py`，以它为参考执行：

```bash
touch -r plugins/airi_point_salad/__init__.py plugins/airi_point_salad
```

确认 `plugins/airi_point_salad` 目录时间与最新任务源码一致，不修改任何文件内容。

- [ ] **Step 7: 删除临时测试和预览产物**

删除以下明确目标：

```text
/tmp/airicore_test_airi_point_salad_upgrade.py
/tmp/airi_point_salad_board.jpg
/tmp/airi_point_salad_cards.png
/tmp/airicore_point_salad_pycache
```

再次确认仓库中没有本任务新建的 `test_*`、`verify_*` 或预览图片。

- [ ] **Step 8: 清理后执行最终新鲜验证**

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m ruff check plugins/airi_point_salad`

Expected: `All checks passed!`

Run: `/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -c 'import nonebot; nonebot.init(); loaded=nonebot.load_plugins("plugins"); print(f"loaded={len(loaded)}")'`

Expected: `loaded=33`，并且日志中没有插件加载失败。

Run: `git show --check --oneline HEAD~4..HEAD`

Expected: exit 0。

Run: `git status --short`

Expected: 只保留任务开始前的用户修改；只有这些新鲜结果与 Step 1 的完整测试结果同时通过后才能报告完成。
