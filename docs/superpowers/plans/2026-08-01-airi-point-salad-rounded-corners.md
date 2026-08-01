# Airi Point Salad Rounded Corners Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add smooth `24px` transparent corners to every rendered Point Salad card while caching the final rounded RGBA images.

**Architecture:** Keep the change inside `renderer.py`: a single helper builds a four-times-resolution rounded mask, downsamples it, multiplies it with the card Alpha channel, and returns the final image. Both front and back builders apply it before returning, so `_cached_image` stores final rounded cards and board composition reuses them unchanged.

**Tech Stack:** Python 3.11, Pillow, existing `ByteLRU` render cache, temporary `unittest` verification.

---

## File Structure

- Modify `plugins/airi_point_salad/renderer.py`: define the corner constants and mask helper, then apply it to character fronts and both score-back branches.
- Create temporarily `/tmp/test_airi_point_salad_rounded_corners.py`: verify Alpha geometry, anti-aliasing, risk cards, and cache hits; delete it after verification.
- Update `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-point-salad.md` and its `MEMORY.md` index entry after the code is verified.

### Task 1: Lock down card corner and cache behavior

**Files:**
- Create: `/tmp/test_airi_point_salad_rounded_corners.py`
- Test: `plugins/airi_point_salad/renderer.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from utils import cache_mode
from plugins.airi_point_salad.cards import build_rule
from plugins.airi_point_salad.models import Card, Character, RuleKind, ScoreRule
from plugins.airi_point_salad import renderer


class RoundedCornerTests(unittest.TestCase):
    def setUp(self):
        self.previous_mode = cache_mode._mode
        cache_mode._mode = "ram"
        renderer._render_cache.clear()

    def tearDown(self):
        renderer._render_cache.clear()
        cache_mode._mode = self.previous_mode

    def assert_rounded(self, image):
        self.assertEqual(image.size, (750, 1050))
        self.assertEqual(image.mode, "RGBA")
        alpha = image.getchannel("A")
        for point in ((0, 0), (749, 0), (0, 1049), (749, 1049)):
            self.assertEqual(alpha.getpixel(point), 0)
        for point in ((375, 0), (375, 1049), (0, 525), (749, 525), (375, 525)):
            self.assertEqual(alpha.getpixel(point), 255)
        self.assertTrue(
            any(
                0 < alpha.getpixel((x, y)) < 255
                for x in range(25)
                for y in range(25)
            )
        )

    def test_front_and_regular_back_have_rounded_corners(self):
        self.assert_rounded(renderer.render_character_front(Character.MINORI))
        card = Card("minori-00", Character.MINORI, build_rule(Character.MINORI, 0))
        self.assert_rounded(renderer.render_score_back(card))

    def test_risk_back_has_rounded_corners(self):
        card = Card(
            "minori-04",
            Character.MINORI,
            ScoreRule(
                RuleKind.RISK,
                [Character.MINORI, Character.RIN],
                3,
                penalty=-1,
            ),
        )
        self.assert_rounded(renderer.render_score_back(card))

    def test_cache_hit_returns_final_rounded_card(self):
        before = renderer._render_cache.stats()["hits"]
        first = renderer.render_character_front(Character.AIRI)
        second = renderer.render_character_front(Character.AIRI)
        self.assertEqual(renderer._render_cache.stats()["hits"], before + 1)
        self.assertEqual(first.getchannel("A").tobytes(), second.getchannel("A").tobytes())
        self.assertEqual(second.getchannel("A").getpixel((0, 0)), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
conda run -n airicore python -m unittest discover -s /tmp -p 'test_airi_point_salad_rounded_corners.py'
```

Expected: three failures because the current card corners have Alpha `255` instead of `0`.

### Task 2: Apply the final rounded mask before caching

**Files:**
- Modify: `plugins/airi_point_salad/renderer.py:1-25,91-127,189-273`
- Test: `/tmp/test_airi_point_salad_rounded_corners.py`

- [ ] **Step 1: Add the mask dependency and constants**

Change the Pillow import and constants to:

```python
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

CARD_SIZE = (750, 1050)
CARD_CORNER_RADIUS = 24
CARD_CORNER_SCALE = 4
```

- [ ] **Step 2: Add the shared corner helper**

Add after `gradient`:

```python
def _round_card_corners(image: Image.Image) -> Image.Image:
    width, height = image.size
    scale = CARD_CORNER_SCALE
    mask = Image.new("L", (width * scale, height * scale))
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, width * scale - 1, height * scale - 1),
        radius=CARD_CORNER_RADIUS * scale,
        fill=255,
    )
    mask = mask.resize(image.size, Image.Resampling.LANCZOS)
    image.putalpha(ImageChops.multiply(image.getchannel("A"), mask))
    return image
```

- [ ] **Step 3: Apply it to every full card builder**

Replace the return at the end of `_build_character_front` with:

```python
    return _round_card_corners(image)
```

Replace both returns in `_build_score_back`, including the risk branch, with:

```python
        return _round_card_corners(image)
```

and:

```python
    return _round_card_corners(image)
```

This placement ensures `_cached_image` receives and stores the final rounded card.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run:

```bash
conda run -n airicore python -m unittest discover -s /tmp -p 'test_airi_point_salad_rounded_corners.py'
```

Expected: `Ran 3 tests` and `OK`.

- [ ] **Step 5: Run static checks**

Run:

```bash
conda run -n airicore ruff check plugins/airi_point_salad
conda run -n airicore python -m compileall -q -f plugins/airi_point_salad
git diff --check
```

Expected: Ruff reports `All checks passed!`; compilation and diff checks produce no errors.

### Task 3: Render, inspect, document, and commit

**Files:**
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-point-salad.md`
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/MEMORY.md`
- Create temporarily: `/tmp/render_airi_point_salad_rounded_preview.py`
- Delete: `/tmp/test_airi_point_salad_rounded_corners.py`

- [ ] **Step 1: Render representative outputs**

Create `/tmp/render_airi_point_salad_rounded_preview.py`:

```python
import base64
from pathlib import Path

from plugins.airi_point_salad.cards import build_deck
from plugins.airi_point_salad.game import add_player, create_game, start_game
from plugins.airi_point_salad.models import GameMode, GameSpeed, RuleKind
from plugins.airi_point_salad.renderer import (
    render_board,
    render_character_front,
    render_score_back,
)


output = Path("/tmp/airi_point_salad_rounded_preview")
output.mkdir(exist_ok=True)
cards = build_deck(4, GameSpeed.STANDARD, 20260801)
regular = next(card for card in cards if card.rule.kind is RuleKind.COMPARE)
risk = next(card for card in cards if card.rule.kind is RuleKind.RISK)
render_character_front(regular.character).save(output / "front.png")
render_score_back(regular).save(output / "compare.png")
render_score_back(risk).save(output / "risk.png")
state = create_game("preview", "1", "玩家一", GameSpeed.STANDARD, GameMode.MIX, 20260801, 1.0)
for index in range(2, 5):
    add_player(state, str(index), f"玩家{index}", float(index))
start_game(state, "1", 10.0)
board = base64.b64decode(render_board(state, "1").removeprefix("base64://"))
(output / "board.jpg").write_bytes(board)
for path in output.glob("*.png"):
    from PIL import Image

    with Image.open(path) as image:
        assert image.size == (750, 1050)
        assert image.mode == "RGBA"
print(output)
```

Run:

```bash
env PYTHONPATH=/Users/liko/Documents/GitHub/AiriCore conda run -n airicore python /tmp/render_airi_point_salad_rounded_preview.py
file /tmp/airi_point_salad_rounded_preview/*
```

Expected: three `750×1050 RGBA` PNG cards and one decodable `2160px`-wide JPEG board. Visually inspect that the curve is slight and smooth.

- [ ] **Step 2: Verify the full plugin set**

Run:

```bash
conda run -n airicore python -c 'import nonebot; nonebot.init(); loaded = nonebot.load_plugins("plugins"); failed = [item for item in loaded if item is None]; print(f"插件加载完成：{len(loaded)}，失败：{len(failed)}")'
```

Expected: `插件加载完成：33，失败：0`.

- [ ] **Step 3: Update project memory**

Append this record to `airi-point-salad.md`:

```markdown
2026-08-01 卡牌圆角升级：角色牌正面和所有计分牌背面统一应用 `24px` 四倍超采样 Alpha 圆角蒙版；风险牌专用分支同样经过最终处理。`ram` 与 `balanced` 缓存保存圆角后的最终 RGBA 卡面，命中时不重复裁切；桌面直接缩放合成圆角卡面。聚焦测试、真实正面/比较/风险/桌面渲染、Ruff、编译和 33/33 插件加载通过。
```

将 `MEMORY.md` 的 `airi point salad` 索引描述更新为包含“24px 抗锯齿圆角与最终卡面缓存”。

- [ ] **Step 4: Clean temporary artifacts**

Delete only `/tmp/test_airi_point_salad_rounded_corners.py`, `/tmp/render_airi_point_salad_rounded_preview.py`, `/tmp/airi_point_salad_rounded_preview`, and generated `plugins/airi_point_salad/__pycache__` files. Confirm `/Users/liko/Downloads/airi_point_salad_preview_20260801` still contains 12 files.

- [ ] **Step 5: Commit only task files on main**

Run:

```bash
git add plugins/airi_point_salad/renderer.py docs/superpowers/plans/2026-08-01-airi-point-salad-rounded-corners.md
git commit --only plugins/airi_point_salad/renderer.py docs/superpowers/plans/2026-08-01-airi-point-salad-rounded-corners.md -m "feat: round point salad card corners"
```

Expected: a new commit on `main`; existing `.gitignore`, `plugins/airi_help/__init__.py`, and `plugins/airi_status/drawer.py` changes remain outside the commit, and no temporary branch remains.
