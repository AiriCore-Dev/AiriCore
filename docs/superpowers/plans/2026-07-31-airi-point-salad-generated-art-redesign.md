# airi_point_salad Generated Artwork Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every directly reused character and Logo image in `airi_point_salad` with a coherent generated new-art-nouveau tarot asset family, including redesigned costumes, distinct elegant poses, partial-body chibi badges, generated card bases, a generated nameplate, and a generated title.

**Architecture:** Preserve the game and message layers. Add a focused `art_assets.py` loader for generated paths, palette tinting, and reference-free runtime access; keep `renderer.py` responsible only for compositing generated layers and exact text/borders. Generate a shared visual anchor first, then generate each asset with fixed prompt language and that anchor so same-type outputs remain coherent.

**Tech Stack:** Built-in image generation, Pillow, `utils.asset_cache`, Python `unittest`, NoneBot OneBot V11

---

## File map

- Create `plugins/airi_point_salad/art_assets.py`: generated asset paths, loading, front-base tinting, portrait and chibi lookup.
- Create `plugins/airi_point_salad/assets/generated/`: all runtime visual assets.
- Create `plugins/airi_point_salad/assets/references/`: original user-supplied references, never imported by runtime code.
- Modify `plugins/airi_point_salad/renderer.py`: replace direct source cropping and Logo use with generated layer compositing.
- Test with `/tmp/airi_point_salad_art_tests/`: temporary asset-contract, renderer, and integration tests removed after verification.
- Update `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-point-salad.md`: record the generated-art architecture and final verification.

### Task 1: Establish the generated-asset contract

**Files:**
- Create: `/tmp/airi_point_salad_art_tests/test_art_assets.py`
- Create: `plugins/airi_point_salad/art_assets.py`

- [ ] **Step 1: Write the failing asset-contract test**

Create the temporary test with `apply_patch`:

```python
import unittest

from plugins.airi_point_salad.art_assets import BACK_BASE_PATH, FRONT_BASE_PATH, NAMEPLATE_PATH, TITLE_PATH, chibi_path, portrait_path
from plugins.airi_point_salad.models import Character


class ArtAssetTests(unittest.TestCase):
    def test_generated_asset_contract(self):
        for path in (TITLE_PATH, FRONT_BASE_PATH, BACK_BASE_PATH, NAMEPLATE_PATH):
            self.assertTrue(path.is_file(), path)
        for character in Character:
            self.assertTrue(portrait_path(character).is_file())
            self.assertTrue(chibi_path(character).is_file())
        self.assertNotIn("references", str(TITLE_PATH))
        self.assertNotIn("references", str(portrait_path(Character.AIRI)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify the red state**

Run:

```bash
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airi_point_salad_art_tests/test_art_assets.py
```

Expected: import failure because `art_assets.py` does not exist.

- [ ] **Step 3: Add the path-only asset module**

Create `art_assets.py` with `apply_patch`:

```python
from pathlib import Path

from .models import Character


ASSET_DIR = Path(__file__).parent / "assets"
GENERATED_DIR = ASSET_DIR / "generated"
TITLE_PATH = GENERATED_DIR / "title.png"
FRONT_BASE_PATH = GENERATED_DIR / "front_base.png"
BACK_BASE_PATH = GENERATED_DIR / "back_base.png"
NAMEPLATE_PATH = GENERATED_DIR / "nameplate.png"


def portrait_path(character: Character) -> Path:
    return GENERATED_DIR / "portraits" / f"{character.value}.png"


def chibi_path(character: Character) -> Path:
    return GENERATED_DIR / "chibi" / f"{character.value}.png"
```

- [ ] **Step 4: Re-run the test**

Expected: imports succeed and file assertions fail, proving the contract is active before generation.

### Task 2: Generate the shared visual anchor and common layers

**Files:**
- Create: `plugins/airi_point_salad/assets/generated/title.png`
- Create: `plugins/airi_point_salad/assets/generated/front_base.png`
- Create: `plugins/airi_point_salad/assets/generated/back_base.png`
- Create: `plugins/airi_point_salad/assets/generated/nameplate.png`
- Move: `plugins/airi_point_salad/assets/characters/*.png` → `plugins/airi_point_salad/assets/references/characters/*.png`
- Move: `plugins/airi_point_salad/assets/logo.png` → `plugins/airi_point_salad/assets/references/logo.png`

- [ ] **Step 1: Inspect all seven references in the conversation**

Use `view_image` with original detail for each current character image and `logo.png`. Label the six character images as identity, hair, face, and palette references; label the Logo as palette and energy reference only. Do not describe any input as an edit target.

- [ ] **Step 2: Generate one temporary visual anchor**

Issue one built-in image-generation call at 2048 × 2048 using all references and this prompt:

```text
Use case: stylized-concept
Asset type: visual style bible for a collectible card game
Primary request: create a polished new-art-nouveau tarot idol style board showing only materials, ornamental motifs, palette swatches, jewel details, translucent fabric studies, gold linework, circular halos, stage starlight, iris flowers, lilies, wheat, feathers, clover and music ribbons; no finished character card and no copied logo
Input images: Images 1–6 are character identity and palette references only; Image 7 is palette and upbeat idol-energy reference only
Style/medium: refined Japanese 2D illustration, elegant collectible tarot art, crisp anime linework, delicate painted shading
Color palette: ivory, deep navy, antique gold, pale cyan, pale pink, plus the six reference character colors
Constraints: one coherent visual language, premium detail, graceful, bright, no text, no logo, no watermark
Avoid: gothic darkness, photorealism, 3D render, sticker collage, thick comic outlines, copied costumes, copied poses
```

Inspect it for coherent linework, gold treatment, fabric and palette. Save the selected result under `/tmp/airi_point_salad_generation/style_anchor.png`; rejected variants remain temporary.

- [ ] **Step 3: Generate the front card base**

Use the style anchor as the only visual input and generate a 1024 × 1536 portrait asset:

```text
Use case: stylized-concept
Asset type: reusable 5:7 front card base layer
Primary request: create an empty new-art-nouveau tarot card interior for a bright idol collectible card; richly illustrated ivory paper, deep navy accents, antique-gold botanical curves close to the edges, subtle circular halo, faint stage starlight and a spacious luminous center for a character overlay
Input images: Image 1 is the mandatory style anchor
Composition/framing: exact centered vertical symmetry, ornament confined to edge zones, lower nameplate area left empty, generous portrait-safe center
Constraints: no person, no nameplate, no outer safety border, no text, no letters, no logo, no watermark
Avoid: dense vines crossing the portrait area, dark gothic mood, stickers, asymmetrical frame drift
```

Crop or resize the accepted output to 750 × 1050 with Pillow and save it as `assets/generated/front_base.png`.

- [ ] **Step 4: Generate the back card base**

Use the style anchor and generate a 1024 × 1536 portrait asset:

```text
Use case: stylized-concept
Asset type: reusable 5:7 score-card back base layer
Primary request: create an empty premium new-art-nouveau tarot card back for a bright idol game; ivory, pale cyan, pale pink and antique gold; decorative edge curves and subtle dotted texture; reserve a clean title zone at top, a wide icon zone in the upper middle, a large rule panel in the center and a score zone below
Input images: Image 1 is the mandatory style anchor
Composition/framing: exact vertical symmetry, high readability, large calm negative-space panels
Constraints: no character, no icon, no title, no words, no numbers, no logo, no watermark
Avoid: dense center ornament, low contrast panels, gothic darkness, sticker collage
```

Crop or resize to 750 × 1050 and save as `assets/generated/back_base.png`.

- [ ] **Step 5: Generate the blank nameplate**

Generate a 1536 × 512 landscape asset with the style anchor:

```text
Use case: stylized-concept
Asset type: reusable blank character-name plaque
Primary request: an elegant blank new-art-nouveau tarot nameplate, deep navy enamel center, fine antique-gold double edge, tiny symmetrical iris and star flourishes only at the far corners, ivory highlights
Input images: Image 1 is the mandatory style anchor
Composition/framing: wide horizontal plaque, perfectly centered, large uninterrupted blank center
Constraints: no letters, no words, no monogram, no character, no watermark
Avoid: protruding ornaments, heavy frame, illegible central texture
```

Crop to the plaque bounds, resize to 1212 × 210, and save as `assets/generated/nameplate.png`.

- [ ] **Step 6: Generate the title graphic**

Generate a 1536 × 1024 landscape title with the style anchor and the original Logo as palette-only input:

```text
Use case: logo-brand
Asset type: game title graphic for card backs and board header
Primary request: create a polished two-line title image with the exact first line "MORE MORE JUMP！" and exact second line "POINT SALAD"; bright idol colors, antique-gold new-art-nouveau flourishes, compact collectible-card branding
Input images: Image 1 is the mandatory style anchor; Image 2 is palette and upbeat energy reference only, do not copy its lettering or silhouette
Composition/framing: centered two-line wordmark on a clean deep-navy plaque, generous padding, strong readability at small size
Text (verbatim): "MORE MORE JUMP！\nPOINT SALAD"
Constraints: exact spelling and punctuation, no additional words, no character, no watermark
Avoid: copied official logo, misspelled text, duplicated letters, warped punctuation, busy background
```

Inspect every character. Regenerate with only the correction “preserve layout; fix text exactly to …” until accurate. Save the accepted output as `assets/generated/title.png`.

- [ ] **Step 7: Move original references out of runtime asset paths**

Use `git mv` for the six character files and Logo. Do not delete the originals. Remove the untracked `.DS_Store` from `assets/` during cleanup, not as a runtime asset.

- [ ] **Step 8: Commit the shared generated layers**

```bash
git add plugins/airi_point_salad/art_assets.py plugins/airi_point_salad/assets/generated plugins/airi_point_salad/assets/references
git commit -m "feat: add generated point salad visual layers"
```

### Task 3: Generate six redesigned elegant portraits

**Files:**
- Create: `plugins/airi_point_salad/assets/generated/portraits/{minori,haruka,airi,shizuku,miku,rin}.png`

- [ ] **Step 1: Generate each portrait separately with a fixed shared prompt**

For every call, use the matching original reference as Image 1 and `style_anchor.png` as Image 2. Generate at 1024 × 1536. Keep this shared prompt identical:

```text
Use case: stylized-concept
Asset type: transparent-layer-ready character portrait for a 5:7 tarot card
Input images: Image 1 is identity, face, hair and palette reference only; Image 2 is the mandatory visual style anchor
Style/medium: refined Japanese 2D illustration, crisp elegant anime linework, delicate painted shading, premium new-art-nouveau tarot idol art
Composition/framing: vertical half-body or three-quarter-body silhouette, centered with generous edge padding, complete hands visible, distinct graceful gesture, no cropping through face or hands
Lighting/mood: luminous soft stage light from upper left, poised, hopeful, elegant
Materials/textures: ivory tailoring, deep-navy structure, antique-gold trim, translucent chiffon, fine gemstones
Constraints: preserve recognizable hair, face, eyes and core palette from Image 1; redesign costume and pose completely; no text, no logo, no card border, no nameplate, no watermark; perfectly flat chroma-key background with no shadow, gradient, texture or reflection
Avoid: copied original outfit, copied original pose, casual clothes, revealing outfit, comedy pose, deformed hands, extra fingers, 3D render, photorealism, gothic darkness
```

Use these exact character-specific requests and key colors:

| File | Primary request | Chroma key |
|---|---|---|
| `minori.png` | 花里实乃理 in a newly designed ivory, navy and tender-green idol ceremonial dress with clover and wheat motifs, light short cape, welcoming forward-reaching gesture, warm graceful smile | `#ff00ff` |
| `haruka.png` | 桐谷遥 in a newly designed ivory, navy and deep-blue streamlined idol ceremonial dress with feather and water-wave motifs, long flowing panels, calm elegant side-facing pose | `#00ff00` |
| `airi.png` | 桃井爱莉 in a newly designed ivory, navy and pink petal-layered idol ceremonial dress with iris and heart-gem motifs, confident elegant turning pose, refined lively expression | `#00ff00` |
| `shizuku.png` | 日野森雫 in a newly designed ivory, navy and silver-blue draped idol ceremonial dress with lily and dewdrop motifs, long translucent veil, expansive over-the-shoulder pose | `#00ff00` |
| `miku.png` | 初音未来 in a newly designed ivory, navy and teal asymmetric idol ceremonial dress with starburst and musical-ribbon motifs, floating guiding gesture, ethereal elegance | `#ff00ff` |
| `rin.png` | 镜音铃 in a newly designed ivory, navy and golden-yellow idol ceremonial dress with sun and wheat motifs, short cape and radiant skirt structure, lively but restrained rising pose | `#ff00ff` |

Each prompt must repeat the chosen key requirement: the full background is one uniform key color, the color is absent from the subject, and there is no cast shadow.

- [ ] **Step 2: Inspect portraits as one contact sheet**

Create a temporary 3 × 2 contact sheet with Pillow. Reject any portrait with copied clothing, repeated pose, inconsistent eye rendering, mismatched line weight, broken hands, missing motif, muddy edges or loss of identity. Regenerate only the failing portrait with one targeted correction.

- [ ] **Step 3: Remove chroma backgrounds**

For each accepted source, run the installed helper:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /Users/liko/.codex/skills/.system/imagegen/scripts/remove_chroma_key.py --input /tmp/airi_point_salad_generation/source/minori.png --out plugins/airi_point_salad/assets/generated/portraits/minori.png --auto-key border --soft-matte --transparent-threshold 12 --opaque-threshold 220 --despill
```

Repeat with the exact matching source and output filename for all six portraits. Validate RGBA mode, transparent corners, non-empty alpha bounds, complete hands, clean hair edges and no key-color fringe. Retry once with `--edge-contract 1` only for a visible fringe. If hair or translucent fabric still fails, stop and ask before any CLI/model fallback.

- [ ] **Step 4: Commit the portrait family**

```bash
git add plugins/airi_point_salad/assets/generated/portraits
git commit -m "feat: add redesigned point salad portraits"
```

### Task 4: Generate six partial-body chibi badges

**Files:**
- Create: `plugins/airi_point_salad/assets/generated/chibi/{minori,haruka,airi,shizuku,miku,rin}.png`

- [ ] **Step 1: Generate a temporary chibi style anchor**

Use the portrait contact sheet and the main visual anchor:

```text
Use case: stylized-concept
Asset type: chibi badge style bible
Primary request: a coherent sample sheet for premium mini chibi idol badges; large expressive eyes, compact head-and-shoulders or half-body framing, clean rounded anime linework, simplified versions of the new-art-nouveau tarot idol outfits, tiny gold and gemstone details, elegant rather than childish
Input images: Image 1 is the accepted portrait family; Image 2 is the mandatory visual style anchor
Composition/framing: consistent camera distance and proportions, circular badge-safe silhouettes
Constraints: no text, no logo, no watermark, no full distant bodies, no sticker captions
Avoid: mixed rendering styles, thick black outlines, exaggerated comedy faces, scale drift
```

Save the accepted temporary result as `/tmp/airi_point_salad_generation/chibi_anchor.png`.

- [ ] **Step 2: Generate six individual chibi images**

For each call, provide the matching accepted portrait as Image 1 and `chibi_anchor.png` as Image 2. Generate 1024 × 1024 with this fixed prompt:

```text
Use case: stylized-concept
Asset type: circular game badge source
Primary request: create one elegant mini chibi portrait of the referenced character, showing head-and-shoulders, bust or half body; preserve the redesigned tarot idol outfit, hair, face, palette and signature motif from Image 1
Input images: Image 1 is the exact character and costume reference; Image 2 is the mandatory chibi style anchor
Style/medium: polished Japanese 2D chibi illustration, clean rounded linework, soft cel shading, tiny antique-gold highlights
Composition/framing: centered circular-badge-safe composition, consistent scale, hands may enter frame for one graceful gesture
Scene/backdrop: simple pale ivory circular glow over a flat character-color field
Constraints: one character only, no text, no letters, no logo, no watermark
Avoid: full distant body, extreme close-up, comedy distortion, thick black outline, different costume, busy props
```

Use these exact identity and gesture deltas while keeping the fixed prompt unchanged:

| File | Character delta |
|---|---|
| `minori.png` | 花里实乃理, clover hair ornament, warm smile, one hand gently reaching forward |
| `haruka.png` | 桐谷遥, feather-and-wave ornament, calm smile, one hand near the chest |
| `airi.png` | 桃井爱莉, iris and heart-gem ornament, confident smile, one hand framing the face |
| `shizuku.png` | 日野森雫, lily and dewdrop ornament, serene smile, one hand lifting a veil edge |
| `miku.png` | 初音未来, star and music-ribbon ornament, ethereal smile, one guiding hand raised |
| `rin.png` | 镜音铃, sun and wheat ornament, bright composed smile, one hand making a small upward flourish |

Inspect a 3 × 2 contact sheet for identical scale, linework, shading and background treatment; regenerate only mismatched items.

- [ ] **Step 3: Normalize the chibi files**

Use Pillow `ImageOps.fit` to normalize every accepted image to 1024 × 1024 RGB or RGBA without stretching. Save each under `assets/generated/chibi/` with its ASCII character filename.

- [ ] **Step 4: Commit the chibi family**

```bash
git add plugins/airi_point_salad/assets/generated/chibi
git commit -m "feat: add generated point salad chibi badges"
```

### Task 5: Implement generated-layer loading

**Files:**
- Modify: `plugins/airi_point_salad/art_assets.py`
- Test: `/tmp/airi_point_salad_art_tests/test_art_assets.py`

- [ ] **Step 1: Extend the failing test**

Add:

```python
from PIL import Image

from plugins.airi_point_salad.art_assets import load_back_base, load_chibi, load_front_base, load_nameplate, load_portrait, load_title


def test_generated_images_load_with_expected_modes(self):
    for character in Character:
        portrait = load_portrait(character)
        chibi = load_chibi(character)
        assert portrait.mode == "RGBA"
        assert portrait.getchannel("A").getextrema()[0] == 0
        assert chibi.width == chibi.height
    assert load_front_base(Character.AIRI).size == (750, 1050)
    assert load_back_base().size == (750, 1050)
    assert load_nameplate().mode == "RGBA"
    assert load_title().mode == "RGBA"
```

- [ ] **Step 2: Run the test and verify missing loaders fail**

Expected: import failure for the new loader names.

- [ ] **Step 3: Implement the loaders**

Add this exact interface to `art_assets.py`:

```python
from PIL import Image

from utils.asset_cache import get_image_copy


CHARACTER_TINTS = {
    Character.MINORI: (90, 190, 130),
    Character.HARUKA: (62, 140, 204),
    Character.AIRI: (226, 92, 157),
    Character.SHIZUKU: (105, 157, 181),
    Character.MIKU: (50, 178, 171),
    Character.RIN: (229, 172, 49),
}


def _load(path: Path) -> Image.Image:
    return get_image_copy(path).convert("RGBA")


def load_front_base(character: Character) -> Image.Image:
    base = _load(FRONT_BASE_PATH).resize((750, 1050), Image.Resampling.LANCZOS)
    tint = Image.new("RGBA", base.size, CHARACTER_TINTS[character] + (24,))
    return Image.alpha_composite(base, tint)


def load_back_base() -> Image.Image:
    return _load(BACK_BASE_PATH).resize((750, 1050), Image.Resampling.LANCZOS)


def load_nameplate() -> Image.Image:
    return _load(NAMEPLATE_PATH)


def load_title() -> Image.Image:
    return _load(TITLE_PATH)


def load_portrait(character: Character) -> Image.Image:
    return _load(portrait_path(character))


def load_chibi(character: Character) -> Image.Image:
    return _load(chibi_path(character))
```

- [ ] **Step 4: Run the asset tests**

Expected: all asset-contract and loader tests pass.

### Task 6: Replace renderer composition without changing game output contracts

**Files:**
- Modify: `plugins/airi_point_salad/renderer.py`
- Test: `/tmp/airi_point_salad_art_tests/test_renderer_generated.py`

- [ ] **Step 1: Write the failing renderer-source test**

```python
import inspect
import unittest

from plugins.airi_point_salad import renderer
from plugins.airi_point_salad.models import Character


class GeneratedRendererTests(unittest.TestCase):
    def test_renderer_has_no_runtime_reference_asset_paths(self):
        source = inspect.getsource(renderer)
        self.assertNotIn('"characters"', source)
        self.assertNotIn('"logo.png"', source)
        self.assertNotIn("character_source", source)

    def test_generated_front_and_icon_render(self):
        front = renderer.render_character_front(Character.AIRI)
        icon = renderer.render_character_icon(Character.AIRI, 130)
        self.assertEqual(front.size, (750, 1050))
        self.assertEqual(icon.size, (130, 130))
        self.assertEqual(front.mode, "RGBA")
        self.assertEqual(icon.mode, "RGBA")


if __name__ == "__main__":
    unittest.main()
```

Run it and verify the source assertion fails against the current direct-reuse renderer.

- [ ] **Step 2: Replace character-front composition**

Import `load_back_base`, `load_chibi`, `load_front_base`, `load_nameplate`, `load_portrait`, and `load_title` from `art_assets.py`. Remove `character_source`, `LOGO_PATH`, `ImageFilter`, and the old source-shadow/crop logic.

Implement this layer order:

```python
def render_character_front(character: Character) -> Image.Image:
    image = load_front_base(character)
    portrait = load_portrait(character)
    portrait.thumbnail((690, 890), Image.Resampling.LANCZOS)
    x = (CARD_SIZE[0] - portrait.width) // 2
    y = max(38, 885 - portrait.height)
    image.alpha_composite(portrait, (x, y))
    plate = load_nameplate()
    plate = plate.resize((606, 105), Image.Resampling.LANCZOS)
    image.alpha_composite(plate, (72, 895))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((12, 12, 737, 1037), CARD_RADIUS, outline=GOLD, width=6)
    draw.rounded_rectangle((25, 25, 724, 1024), 22, outline=INNER_GOLD, width=3)
    draw.text((375, 923), character.display_name, font=font(46), anchor="mm", fill=(255, 255, 255))
    draw.text((375, 971), character.value.upper(), font=font(21), anchor="mm", fill=(238, 228, 238))
    return image
```

The portrait alpha bounds must remain inside x=30–720 and y=25–895 before the nameplate is applied. If a generated portrait cannot meet those bounds without cutting the face or hands, regenerate that portrait with more edge padding rather than changing the shared compositor.

- [ ] **Step 3: Replace Q-version icon composition**

Implement:

```python
def render_character_icon(character: Character, size: int = 100) -> Image.Image:
    source = ImageOps.fit(load_chibi(character), (size, size), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size))
    ImageDraw.Draw(mask).ellipse((3, 3, size - 4, size - 4), fill=255)
    icon = Image.new("RGBA", (size, size))
    icon.paste(source, mask=mask)
    draw = ImageDraw.Draw(icon)
    draw.ellipse((3, 3, size - 4, size - 4), outline=GOLD, width=max(2, size // 24))
    return icon
```

Remove `CHARACTER_INITIALS`; the generated Q images provide the visual identity.

- [ ] **Step 4: Replace score-back and board title layers**

Start `render_score_back` from `load_back_base()` rather than a generated Pillow gradient. Resize `load_title()` to fit within 350 × 130 and composite it at the existing title location. Preserve exact rule, score and card-ID text from program code. In `render_board`, use the same generated title instead of `logo.png`.

- [ ] **Step 5: Run renderer and existing focused tests**

Run:

```bash
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airi_point_salad_art_tests/test_art_assets.py
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python /tmp/airi_point_salad_art_tests/test_renderer_generated.py
```

Expected: all pass and no runtime path contains `references`.

- [ ] **Step 6: Commit renderer integration**

```bash
git add plugins/airi_point_salad/art_assets.py plugins/airi_point_salad/renderer.py
git commit -m "feat: render point salad with generated artwork"
```

### Task 7: Visual and full-system verification

**Files:**
- Create temporarily: `/tmp/airi_point_salad_art_preview/`

- [ ] **Step 1: Render the complete visual set**

Render six character fronts, representative EACH/PAIR/SET/COMPARE/RISK backs, a six-player standard mixed board with current-player details, and a six-player result. Save preview-only files under `/tmp/airi_point_salad_art_preview/`.

- [ ] **Step 2: Inspect every preview at original detail**

Use `view_image`. Verify portrait edges, identity, outfit uniqueness, pose uniqueness, elegance, nameplate fit, generated title spelling, Q-badge readability, text contrast, 5:7 ratio, generated layer coherence and absence of reference art. If one item fails, change only that generated asset or its layer geometry, then repeat the affected preview.

- [ ] **Step 3: Run temporary regression tests**

Create `/tmp/airi_point_salad_art_tests/test_art_regression.py` with:

```python
import base64
from collections import Counter
import unittest

from plugins.airi_point_salad.cards import build_deck
from plugins.airi_point_salad.commands import parse_command
from plugins.airi_point_salad.game import add_player, available_character_slots, create_game, start_game, take_characters, take_score
from plugins.airi_point_salad.models import Character, GameMode, GameSpeed, Phase
from plugins.airi_point_salad.renderer import CARD_SIZE, render_board, render_character_front
from plugins.airi_point_salad.scoring import rank_players


class ArtRegressionTests(unittest.TestCase):
    def test_deck_contract_is_unchanged(self):
        for player_count in range(2, 7):
            for speed, per_player in ((GameSpeed.QUICK, 12), (GameSpeed.STANDARD, 18)):
                deck = build_deck(player_count, speed, 42)
                counts = Counter(card.character for card in deck)
                self.assertEqual(len(deck), player_count * per_player)
                self.assertEqual(len(set(counts.values())), 1)

    def test_command_contract_is_unchanged(self):
        samples = {
            "沙拉 创建 快速 原版": "create",
            "salad create standard mix": "create",
            "sl ta A": "take",
            "sl ta A1 B2": "take",
            "sl fl 2": "flip",
            "sl sk": "skill",
            "sl bd": "board",
            "sl rl": "rules",
        }
        for text, action in samples.items():
            self.assertEqual(parse_command(text).action, action)

    def test_all_game_combinations_finish(self):
        for player_count in range(2, 7):
            for speed in GameSpeed:
                for mode in GameMode:
                    state = create_game("100", "1", "P1", speed, mode, 42, 1)
                    for index in range(2, player_count + 1):
                        add_player(state, str(index), f"P{index}", index)
                    start_game(state, "1", 10)
                    steps = 0
                    while state.phase is Phase.PLAYING:
                        user_id = state.players[state.current_player].user_id
                        column = next((i for i, card_id in enumerate(state.score_market) if card_id), None)
                        if column is not None:
                            take_score(state, user_id, column, 20 + steps)
                        else:
                            slots = available_character_slots(state)
                            take_characters(state, user_id, slots[:min(2, len(slots))], 20 + steps)
                        steps += 1
                        self.assertLess(steps, 200)
                    self.assertEqual(len(rank_players(state)), player_count)

    def test_generated_render_contract(self):
        for character in Character:
            self.assertEqual(render_character_front(character).size, CARD_SIZE)
        state = create_game("100", "1", "P1", GameSpeed.STANDARD, GameMode.MIX, 42, 1)
        for index in range(2, 7):
            add_player(state, str(index), f"P{index}", index)
        start_game(state, "1", 10)
        payload = render_board(state, "1")
        self.assertTrue(payload.startswith("base64://"))
        self.assertLess(len(base64.b64decode(payload[9:])), 3 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
```

Run this file together with `test_art_assets.py` and `test_renderer_generated.py`. Expected: all pass.

- [ ] **Step 4: Run repository verification**

Run isolated compile output, AST parsing, 6-player worst-board byte count, direct plugin load and full project plugin load. Expected: `airi_point_salad` loads, all project plugins load, all Python parses, and the worst board remains below 3 MB.

- [ ] **Step 5: Run source-policy checks**

```bash
rg -n 'assets/references|assets/characters|logo\.png' plugins/airi_point_salad --glob '*.py'
rg -n 'file://|MessageSegment\.image\([^)]*(Path|str\(|ASSET|PLUGIN_DIR)' plugins/airi_point_salad
rg -n '^\s*#|"""|\x27\x27\x27' plugins/airi_point_salad --glob '*.py'
rg -n '桃井 Airi|(^|[^桃井])爱莉' plugins/airi_point_salad plugins/airi_help/__init__.py
```

Expected: no runtime reference asset path, no local-path image send, no code comments/docstrings, no mixed character name, and standalone `爱莉` absent.

### Task 8: Memory, mtime, cleanup and final commit

**Files:**
- Modify: `/Users/liko/.Codex/projects/-Users-liko-Documents-GitHub-AiriCore/memory/airi-point-salad.md`

- [ ] **Step 1: Update project memory**

Record the generated asset tree, the reference-only boundary, redesigned costume motifs, layer order, built-in generation path, chroma-removal behavior, test counts, plugin-load count and final image byte measurements.

- [ ] **Step 2: Synchronize plugin directory mtime**

Run this exact one-liner, which ignores cache/runtime artifacts and sets only the plugin directory timestamp:

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/airidev/bin/python -c 'import os; from pathlib import Path; root=Path("plugins/airi_point_salad"); ignored={".pyc",".pyo",".pk",".log"}; files=[p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix not in ignored and p.name != ".DS_Store"]; latest=max(p.stat().st_mtime_ns for p in files); os.utime(root, ns=(latest, latest))'
```

Run the same command a second time and verify `stat` reports the same directory timestamp.

- [ ] **Step 3: Remove temporary artifacts**

Delete only these exact task-owned paths after all verification evidence is recorded:

```text
/tmp/airi_point_salad_generation
/tmp/airi_point_salad_art_tests
/tmp/airi_point_salad_art_preview
/tmp/airi_point_salad_art_pycache
```

Also delete `plugins/airi_point_salad/assets/.DS_Store` if it is untracked. Confirm none of the temporary paths remain.

- [ ] **Step 4: Verify scope and working tree**

Run `git diff --check`, inspect `git status --short`, inspect the commits added by this redesign, and confirm unrelated user changes were untouched.

- [ ] **Step 5: Commit any final tracked adjustment**

If visual verification required a tracked adjustment after Task 6, commit only those exact files:

```bash
git add plugins/airi_point_salad
git commit -m "fix: polish generated point salad artwork"
```

If no tracked file changed, do not create an empty commit.
