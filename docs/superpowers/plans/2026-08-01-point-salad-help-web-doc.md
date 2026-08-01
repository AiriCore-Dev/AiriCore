# Airi Point Salad Help and Web Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing long Point Salad help with six stable forward-message sections and add a deployable MDX rules article with annotated images built only from existing local assets.

**Architecture:** Keep runtime help copy in `help.py` and leave forward-message transport in `__init__.py`. Put the website-only article, deterministic Pillow asset builder, and generated PNG files in `plugins/airi_point_salad/web_help/`; none of these files are imported by the Bot.

**Tech Stack:** Python 3.11, Pillow, NoneBot OneBot v11, MDX with YAML frontmatter, Ruff, unittest

---

## File Structure

- Modify `plugins/airi_point_salad/help.py`: return exactly six help sections and expose one replaceable documentation URL constant.
- Create `plugins/airi_point_salad/web_help/index.mdx`: complete web rules article using relative image paths.
- Create `plugins/airi_point_salad/web_help/build_assets.py`: deterministic Pillow composition using existing plugin assets and renderer functions.
- Create `plugins/airi_point_salad/web_help/cover.png`: article cover.
- Create `plugins/airi_point_salad/web_help/market-guide.png`: annotated market coordinate guide.
- Create `plugins/airi_point_salad/web_help/turn-flow.png`: annotated turn sequence.
- Create `plugins/airi_point_salad/web_help/scoring-guide.png`: five scoring-rule examples.
- Create `plugins/airi_point_salad/web_help/center-skills.png`: six Center skill summaries.
- Create `plugins/airi_point_salad/web_help/mixed-mode.png`: mixed-mode relationship diagram.
- Create then remove `tmp/airi_point_salad_help_tests/test_help_web_doc.py`: focused regression tests used during implementation.
- Modify `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-point-salad.md`: record the completed help and MDX bundle.
- Modify `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/MEMORY.md`: refresh the Point Salad memory index summary.

### Task 1: Lock the six-section help contract

**Files:**
- Create: `tmp/airi_point_salad_help_tests/test_help_web_doc.py`
- Modify: `plugins/airi_point_salad/help.py`

- [ ] **Step 1: Write the failing help contract test**

Create `tmp/airi_point_salad_help_tests/test_help_web_doc.py` with imports isolated from NoneBot:

```python
import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "plugins" / "airi_point_salad"


def load_module(name):
    spec = importlib.util.spec_from_file_location(
        f"plugins.airi_point_salad.{name}", PACKAGE / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


plugins = types.ModuleType("plugins")
plugins.__path__ = [str(ROOT / "plugins")]
sys.modules.setdefault("plugins", plugins)
package = types.ModuleType("plugins.airi_point_salad")
package.__path__ = [str(PACKAGE)]
sys.modules.setdefault("plugins.airi_point_salad", package)
load_module("models")
load_module("missions")
load_module("game")
load_module("skills")
help_module = load_module("help")


class HelpContractTests(unittest.TestCase):
    def test_six_sections_have_required_order_and_stable_edges(self):
        sections = help_module.help_sections()
        self.assertEqual(len(sections), 6)
        self.assertEqual(
            sections[0],
            (
                "Airi-Point-Salad",
                "MORE MORE JUMP！得分沙拉\n摸摸酱们也要玩美式桌游！",
            ),
        )
        self.assertEqual(
            [title for title, _ in sections],
            [
                "Airi-Point-Salad",
                "游戏简介",
                "指令列表",
                "桌游玩法文档",
                "注意事项",
                "版权信息",
            ],
        )
        self.assertEqual(
            sections[-1][1],
            "AiriCore 采用 MIT License\nCopyright (C) 2026 AiriCore Dev.\n\n"
            "Point Salad 原作及 MORE MORE JUMP！、世界计划相关名称、角色与美术素材的权利归各自权利人所有。"
            "本插件为非官方同人实现，与原权利方无隶属或授权关系。",
        )

    def test_intro_and_document_url_match_approved_copy(self):
        sections = dict(help_module.help_sections())
        self.assertEqual(
            sections["游戏简介"],
            "一款适合 2–6 人在群聊中游玩的选牌桌游。玩家轮流从市场取得角色牌或计分牌，"
            "通过角色组合、翻牌规划和不同计分条件积累分数，最后总分最高者获胜。",
        )
        self.assertEqual(
            help_module.RULES_DOCUMENT_URL,
            "https://example.com/airi-point-salad",
        )
        self.assertIn(help_module.RULES_DOCUMENT_URL, sections["桌游玩法文档"])

    def test_command_and_notice_sections_cover_runtime_contract(self):
        sections = dict(help_module.help_sections())
        command_text = sections["指令列表"]
        for token in (
            ",沙拉",
            ",salad",
            ",sl",
            "cr",
            "qk",
            "std",
            "cl",
            "mx",
            "j",
            "lv",
            "st",
            "sp",
            "ta A",
            "ta A1 B2",
            "fl 2",
            "sk A",
            "sk 2 rin",
            "sk A1 B2 C1",
            "bd",
            "rl",
        ):
            self.assertIn(token, command_text)
        notice_text = sections["注意事项"]
        for text in ("2–6 人", "房主", "管理员", "12 张", "18 张", "15 分钟", "30 分钟"):
            self.assertIn(text, notice_text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m unittest tmp.airi_point_salad_help_tests.test_help_web_doc -v
```

Expected: three failures because `help_sections()` still returns eleven nodes and `RULES_DOCUMENT_URL` does not exist.

- [ ] **Step 3: Implement the six help sections**

Replace `plugins/airi_point_salad/help.py` with a compact data builder. Preserve the first and last tuples exactly, define `RULES_DOCUMENT_URL = "https://example.com/airi-point-salad"`, use the approved introduction verbatim, and build the command section from exact lines including these Center forms:

```python
from .models import Character
from .skills import skill_usage


RULES_DOCUMENT_URL = "https://example.com/airi-point-salad"


def help_sections() -> tuple[tuple[str, str], ...]:
    skill_lines = "\n".join(
        f"{character.short_name}：{skill_usage(character)}"
        for character in Character
    )
    commands = "\n".join(
        (
            "根命令：,沙拉 / ,salad / ,sl",
            "创建：,sl cr qk cl",
            "速度：快速/quick/qk；标准/standard/std",
            "模式：原版/classic/cl；混合/mix/mx",
            "加入/退出：,sl j / ,sl lv",
            "开始/结束：,sl st / ,sl sp",
            "拿计分牌：,sl ta A",
            "拿角色牌：,sl ta A1 B2",
            "翻牌：,sl fl 2",
            f"Center 技能：\n{skill_lines}",
            "查看桌面：,sl bd",
            "查看帮助：,sl rl",
            "中文、英文全称和缩写可混用；英文不区分大小写。",
        )
    )
```

Return exactly the six approved tuples. The document node must interpolate `RULES_DOCUMENT_URL`. The notice node must state player count, permissions, quick/standard card counts, flip/take limits, mixed-mode limits, timeout durations, and the non-refresh behavior of board/help views.

- [ ] **Step 4: Run the focused test and confirm GREEN**

Run the same unittest command.

Expected: `Ran 3 tests` and `OK`.

- [ ] **Step 5: Commit only the runtime help change**

```bash
git add plugins/airi_point_salad/help.py
git commit -m "feat: restructure point salad help"
```

Expected: the commit contains `plugins/airi_point_salad/help.py` only and does not include unrelated dirty files.

### Task 2: Build deterministic annotated web images

**Files:**
- Create: `plugins/airi_point_salad/web_help/build_assets.py`
- Create: `plugins/airi_point_salad/web_help/cover.png`
- Create: `plugins/airi_point_salad/web_help/market-guide.png`
- Create: `plugins/airi_point_salad/web_help/turn-flow.png`
- Create: `plugins/airi_point_salad/web_help/scoring-guide.png`
- Create: `plugins/airi_point_salad/web_help/center-skills.png`
- Create: `plugins/airi_point_salad/web_help/mixed-mode.png`
- Modify: `tmp/airi_point_salad_help_tests/test_help_web_doc.py`

- [ ] **Step 1: Add failing asset contract tests**

Append a `WebAssetTests` class that asserts the six output filenames exist, every file opens as PNG, every image is at least 1200 pixels wide, and representative annotation pixels are opaque. Also parse `build_assets.py` text and assert it imports `PIL`, `renderer`, and `art_assets`, while containing none of `openai`, `image_gen`, or an HTTP URL.

```python
from PIL import Image


class WebAssetTests(unittest.TestCase):
    def test_web_assets_are_local_annotated_png_files(self):
        output_dir = PACKAGE / "web_help"
        names = (
            "cover.png",
            "market-guide.png",
            "turn-flow.png",
            "scoring-guide.png",
            "center-skills.png",
            "mixed-mode.png",
        )
        for name in names:
            with Image.open(output_dir / name) as image:
                self.assertEqual(image.format, "PNG")
                self.assertGreaterEqual(image.width, 1200)
                self.assertEqual(image.mode, "RGB")
        source = (output_dir / "build_assets.py").read_text(encoding="utf-8")
        self.assertIn("from PIL import", source)
        self.assertIn("from plugins.airi_point_salad import art_assets", source)
        self.assertIn("from plugins.airi_point_salad import renderer", source)
        self.assertNotIn("openai", source.lower())
        self.assertNotIn("image_gen", source.lower())
        self.assertNotIn("http://", source.lower())
        self.assertNotIn("https://", source.lower())
```

- [ ] **Step 2: Run only the new asset test and confirm RED**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m unittest tmp.airi_point_salad_help_tests.test_help_web_doc.WebAssetTests -v
```

Expected: failure because `web_help/` outputs do not exist.

- [ ] **Step 3: Implement the reusable drawing primitives**

Create `build_assets.py` without comments or docstrings. Define `OUTPUT_DIR`, `ASSET_DIR`, `FONT_PATH`, palette constants, and focused helpers:

```python
from pathlib import Path
import math

import nonebot
from PIL import Image, ImageDraw

nonebot.init()

from plugins.airi_point_salad import art_assets
from plugins.airi_point_salad import renderer
from plugins.airi_point_salad.cards import build_deck
from plugins.airi_point_salad.models import Character, GameSpeed, RuleKind


OUTPUT_DIR = Path(__file__).resolve().parent
ASSET_DIR = OUTPUT_DIR.parent / "assets"
FONT_PATH = ASSET_DIR / "font.ttf"
NAVY = (28, 43, 84)
PINK = (242, 113, 158)
GOLD = (244, 190, 66)
MINT = (225, 249, 241)
WHITE = (255, 255, 255)


def font(size):
    return renderer.font(size)


def canvas(size, top=(247, 252, 255), bottom=(255, 239, 247)):
    return renderer.gradient(size, top, bottom).convert("RGBA")


def rounded_box(draw, box, fill, outline=NAVY, width=4, radius=30):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def label(draw, xy, text, size=42, fill=NAVY, anchor="mm"):
    draw.text(xy, text, font=font(size), fill=fill, anchor=anchor)


def arrow(draw, start, end, fill=PINK, width=14):
    draw.line((start, end), fill=fill, width=width)
    x1, y1 = start
    x2, y2 = end
    angle = math.atan2(y2 - y1, x2 - x1)
    length = 32
    spread = 0.55
    points = [
        end,
        (
            x2 - length * math.cos(angle - spread),
            y2 - length * math.sin(angle - spread),
        ),
        (
            x2 - length * math.cos(angle + spread),
            y2 - length * math.sin(angle + spread),
        ),
    ]
    draw.polygon(points, fill=fill)


def paste_contained(target, source, box):
    x1, y1, x2, y2 = box
    image = source.copy().convert("RGBA")
    image.thumbnail((x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
    x = x1 + (x2 - x1 - image.width) // 2
    y = y1 + (y2 - y1 - image.height) // 2
    target.alpha_composite(image, (x, y))


def save(image, name):
    image.convert("RGB").save(OUTPUT_DIR / name, "PNG", optimize=True)
```

- [ ] **Step 4: Implement each composition with existing assets**

Add six builder functions and a `main()` call:

- `build_cover()`: generated title centered above all six Q版 characters.
- `build_market_guide()`: render three score backs and six character fronts from a deterministic two-player quick deck; lay them in columns A/B/C; circle each slot; label A, B, C and A1–C2; draw one arrow to a score card and two arrows to different character positions.
- `build_turn_flow()`: four rounded steps labeled `轮到你`, `可选：翻 1 张`, `必须：拿牌`, `补满市场并换人`, joined by arrows; use one front and one score back as visual anchors.
- `build_scoring_guide()`: choose one deterministic card for each `RuleKind`, render its score back, and place a short label below each card: `每个`, `双人组`, `三人组`, `数量比较`, `加分与扣分`.
- `build_center_skills()`: place all six local Q版 images in a 3x2 grid with `character.short_name`, `skill_usage(character)`, and a one-line effect summary.
- `build_mixed_mode()`: connect `Center 一次性技能`, `公开 Live Mission`, and `基础选牌计分` to `混合模式总分`, with local Q版 character art and circled Mission cards.

The final script entrypoint must be:

```python
def main():
    build_cover()
    build_market_guide()
    build_turn_flow()
    build_scoring_guide()
    build_center_skills()
    build_mixed_mode()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Generate the six PNG files**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python plugins/airi_point_salad/web_help/build_assets.py
```

Expected: exit code 0 and six RGB PNG files appear in `plugins/airi_point_salad/web_help/`.

- [ ] **Step 6: Run the asset test and confirm GREEN**

Run the `WebAssetTests` unittest command again.

Expected: all asset tests pass.

- [ ] **Step 7: Visually inspect every generated image**

Create a contact sheet in `tmp/airi_point_salad_help_tests/contact-sheet.png`, inspect it with the local image viewer, and regenerate after any fix. Confirm no clipped labels, overlaps, illegible text, missing characters, broken arrows, or transparent checkerboards. Remove the contact sheet after inspection.

- [ ] **Step 8: Commit the deterministic builder and final PNG files**

```bash
git add plugins/airi_point_salad/web_help/build_assets.py plugins/airi_point_salad/web_help/*.png
git commit -m "feat: add point salad web guide visuals"
```

Expected: the commit contains the builder and six PNG files only.

### Task 3: Write the deployable MDX rules article

**Files:**
- Create: `plugins/airi_point_salad/web_help/index.mdx`
- Modify: `tmp/airi_point_salad_help_tests/test_help_web_doc.py`

- [ ] **Step 1: Add a failing MDX contract test**

Append `MdxArticleTests` that parses the frontmatter boundaries, asserts the required keys and values, extracts Markdown image paths with a regular expression, confirms every image exists, and checks required rules vocabulary:

```python
import re


class MdxArticleTests(unittest.TestCase):
    def test_mdx_frontmatter_sections_and_images(self):
        article_path = PACKAGE / "web_help" / "index.mdx"
        text = article_path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        frontmatter, body = text[4:].split("\n---\n", 1)
        for line in (
            "title: MORE MORE JUMP！得分沙拉完整玩法",
            "published: 2026-08-01",
            "pinned: false",
            "category: AiriCore",
            "draft: false",
            "image: cover.png",
        ):
            self.assertIn(line, frontmatter)
        for heading in (
            "## 游戏目标",
            "## 开始之前",
            "## 市场与卡牌",
            "## 每回合怎么行动",
            "## 五类计分牌",
            "## 原版与混合模式",
            "## 六名 Center 技能",
            "## Live Mission",
            "## 游戏结束与排名",
            "## 完整指令表",
            "## 常见问题",
            "## 版权信息",
        ):
            self.assertIn(heading, body)
        image_paths = re.findall(r"!\[[^]]*\]\(([^)]+)\)", body)
        self.assertEqual(
            set(image_paths),
            {
                "market-guide.png",
                "turn-flow.png",
                "scoring-guide.png",
                "center-skills.png",
                "mixed-mode.png",
            },
        )
        for image_path in image_paths:
            self.assertTrue((article_path.parent / image_path).is_file())
```

- [ ] **Step 2: Run only the MDX test and confirm RED**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m unittest tmp.airi_point_salad_help_tests.test_help_web_doc.MdxArticleTests -v
```

Expected: failure because `index.mdx` does not exist.

- [ ] **Step 3: Write exact frontmatter and article structure**

Create `index.mdx` starting with:

```mdx
---
title: MORE MORE JUMP！得分沙拉完整玩法
published: 2026-08-01
pinned: false
description: AiriCore 群聊选牌桌游的完整规则、指令、Center 技能与图解
tags: [AiriCore, Point Salad, 桌游, MORE MORE JUMP]
category: AiriCore
draft: false
image: cover.png
---
```

Write all twelve tested sections. Use the current implementation as the source of truth:

- 2–6 players; quick uses 12 cards per player and standard uses 18.
- Each card has a character front and score-rule back.
- A turn may flip at most one owned score card before taking cards.
- A normal take is either one score card from A/B/C or two character cards from distinct A1–C2 slots; if fewer than two character cards remain, take all remaining character cards.
- Explain EACH, PAIR, SET, COMPARE, and RISK, including that one character card can satisfy multiple score cards and risk totals may be negative.
- Explain classic versus mixed mode.
- Copy all six `skill_usage()` command forms and explain Minori's three-stage transaction, Airi's no-flip restriction, and which skills finish the turn.
- Explain that up to two public Live Missions are visible, at most one is claimed per turn, and a replacement is revealed.
- Explain automatic finish when deck and market empty; ties compare character-card count, then completed Mission count.
- Include a complete room-to-finish command sequence.
- Include timeouts, permissions, comma-prefix requirement, and non-refreshing board/help views.
- End with the exact current copyright content.

Place the five relative image references immediately after the section they explain.

- [ ] **Step 4: Run the MDX test and confirm GREEN**

Run the `MdxArticleTests` command again.

Expected: the MDX contract passes.

- [ ] **Step 5: Read the complete article once for editorial QA**

Check for contradictions against `commands.py`, `game.py`, `skills.py`, `missions.py`, and `scoring.py`. Confirm every command starts with an English comma and all user-visible Bot names use `Airi`.

- [ ] **Step 6: Commit the MDX article**

```bash
git add plugins/airi_point_salad/web_help/index.mdx
git commit -m "docs: add point salad web rules"
```

Expected: the commit contains the MDX article only.

### Task 4: Full verification and memory update

**Files:**
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-point-salad.md`
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/MEMORY.md`
- Remove: `tmp/airi_point_salad_help_tests/test_help_web_doc.py`

- [ ] **Step 1: Run all focused regressions**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m unittest tmp.airi_point_salad_help_tests.test_help_web_doc -v
```

Expected: all help, image, and MDX tests pass.

- [ ] **Step 2: Run Ruff on changed Python files**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/ruff check plugins/airi_point_salad/help.py plugins/airi_point_salad/web_help/build_assets.py
```

Expected: `All checks passed!`.

- [ ] **Step 3: Run syntax and bytecode verification**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -c 'import ast; from pathlib import Path; files=(Path("plugins/airi_point_salad/help.py"), Path("plugins/airi_point_salad/web_help/build_assets.py")); [ast.parse(path.read_text(encoding="utf-8"), filename=str(path)) for path in files]'
PYTHONPYCACHEPREFIX=/tmp/airi_point_salad_help_pyc /opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -m compileall -q plugins/airi_point_salad
```

Expected: all commands exit 0.

- [ ] **Step 4: Load all project plugins**

Run:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -c 'import nonebot; from nonebot.adapters.onebot.v11 import Adapter; nonebot.init(); driver=nonebot.get_driver(); driver.register_adapter(Adapter); loaded=nonebot.load_plugins("plugins"); names={plugin.name for plugin in loaded}; assert len(loaded) == 33, len(loaded); assert "airi_point_salad" in names; print(f"{len(loaded)}/33")'
```

Expected: every project plugin loads and `airi_point_salad` reports no import conflict.

- [ ] **Step 5: Check diff hygiene and generated file integrity**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; unrelated dirty files remain untouched; all intended help and web-doc files are tracked.

- [ ] **Step 6: Remove temporary validation artifacts**

Delete `tmp/airi_point_salad_help_tests/` after recording the passing results. Confirm no temporary contact sheet, test file, bytecode, or generated scratch file remains.

- [ ] **Step 7: Synchronize plugin directory mtimes**

Run this exact script twice:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -c 'from pathlib import Path; import os; root=Path("plugins"); skipped={".git", ".claude", ".codex", ".agents", "__pycache__"}; changed=0; directories=sorted((path for path in root.rglob("*") if path.is_dir() and not any(part in skipped for part in path.parts)), key=lambda path: len(path.parts), reverse=True); directories.append(root); exec("for directory in directories:\n files=[path for path in directory.iterdir() if path.is_file() and path.suffix not in {\".pyc\", \".pk\", \".log\"}]\n children=[path for path in directory.iterdir() if path.is_dir() and path.name not in skipped]\n sources=files+children\n if not sources: continue\n newest=max(path.stat().st_mtime_ns for path in sources)\n current=directory.stat().st_mtime_ns\n if current != newest:\n  os.utime(directory, ns=(directory.stat().st_atime_ns, newest)); changed += 1")
print(changed)'
```

Expected: the first pass updates `plugins/airi_point_salad` and ancestors as needed; the second pass reports zero changed directories.

- [ ] **Step 8: Update project memory**

Append a dated entry to `airi-point-salad.md` recording the six-node help layout, exact placeholder URL, deployable MDX bundle, six annotated local-asset PNG files, absence of image generation, and verification results. Update the Point Salad line in `MEMORY.md` to mention the web guide.

- [ ] **Step 9: Confirm the memory index references the updated module entry**

Run:

```bash
rg -n "web guide|网页玩法|MDX" /Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/MEMORY.md /Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-point-salad.md
```

Expected: both the detailed memory and its index mention the six-section help and MDX web guide.
