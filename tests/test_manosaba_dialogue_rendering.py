import importlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/nonebot_plugin_manosaba_memes"
PACKAGE = "_manosaba_dialogue_render_tests"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(PLUGIN)]
sys.modules[PACKAGE] = package


class DialogueRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rendering = importlib.import_module(f"{PACKAGE}.dialogue.rendering")

    def test_wrapping_preserves_text_and_rejects_overflow(self):
        wrap = self.rendering.wrap_body
        text = "证据已经准备好了。\n下一步，该轮到我们了。"
        self.assertEqual(wrap(text), ["证据已经准备好了。", "下一步，该轮到我们了。"])
        for value in ("测试" * 150, "一\n二\n三\n四", "   "):
            with self.subTest(value=value[:10]), self.assertRaises(ValueError):
                wrap(value)

    def test_punctuation_does_not_start_wrapped_line(self):
        lines = self.rendering.wrap_body("测" * 29 + "，证据。")
        self.assertEqual("".join(lines), "测" * 29 + "，证据。")
        self.assertFalse(any(line.startswith("，") for line in lines))

    def test_nameplate_independent_of_cast(self):
        render = self.rendering.render_dialogue
        request = lambda author: types.SimpleNamespace(background="@BG001", sprites=(), author=author, text="测试正文")
        images = [Image.open(io.BytesIO(render(request(author)))).convert("RGB") for author in (None, "Ema", "?")]
        self.assertTrue(all(image.size == (2560, 1440) for image in images))
        for image in images[1:]:
            self.assertIsNotNone(ImageChops.difference(images[0], image).crop((340, 900, 1450, 1120)).getbbox())
            self.assertIsNone(ImageChops.difference(images[0], image).crop((0, 0, 2560, 900)).getbbox())

    def test_three_characters_render_and_four_rejected(self):
        request = types.SimpleNamespace(background="@BG001", sprites=("#CFAMVMR9LZ",) * 3, author="Hiro", text="三个人一起出发。")
        image = Image.open(io.BytesIO(self.rendering.render_dialogue(request))).convert("RGB")
        empty = types.SimpleNamespace(background=request.background, sprites=(), author=request.author, text=request.text)
        base = Image.open(io.BytesIO(self.rendering.render_dialogue(empty))).convert("RGB")
        delta = ImageChops.difference(image, base)
        for left, right in ((300, 1000), (1000, 1600), (1600, 2300)):
            self.assertIsNotNone(delta.crop((left, 100, right, 900)).getbbox())
        request.sprites += ("#CFAMVMR9LZ",)
        with self.assertRaises(ValueError):
            self.rendering.render_dialogue(request)

    def test_bad_checksum_returns_user_error(self):
        request = types.SimpleNamespace(background="@BG001", sprites=("#23456789AB",), author=None, text="测试")
        with self.assertRaises(ValueError):
            self.rendering.render_dialogue(request)

    def test_background_preview_and_picker_use_real_assets(self):
        catalog = importlib.import_module(f"{PACKAGE}.dialogue.catalog").BackgroundCatalog()
        entry = catalog.get("@BG001")
        with Image.open(io.BytesIO(self.rendering.render_background(entry))) as image:
            self.assertGreater(image.width, 1000)
        with Image.open(io.BytesIO(self.rendering.render_background_picker(catalog.entries("场景")[:25], 0))) as image:
            self.assertEqual(image.size, (2560, 1680))
            for row in range(5):
                for column in range(5):
                    tile = image.crop((column * 512 + 8, row * 336 + 8, column * 512 + 504, row * 336 + 288))
                    self.assertIsNone(tile.getcolors(maxcolors=1))
        with self.assertRaises(ValueError):
            self.rendering.render_background_picker(catalog.entries("场景")[:26], 0)

    def test_picker_font_has_all_short_code_glyphs(self):
        font = self.rendering._font(26, self.rendering.PICKER_FONT)
        missing = bytes(font.getmask("\u0378"))
        for char in "B@G0123456789":
            with self.subTest(char=char):
                self.assertNotEqual(bytes(font.getmask(char)), missing)

    def test_updated_sprite_resources_are_used_without_restart(self):
        models = importlib.import_module(f"{PACKAGE}.models")
        state = importlib.import_module(f"{PACKAGE}.sprite_editor.state")
        with tempfile.TemporaryDirectory() as directory:
            assets = Path(directory)
            (assets / "presets").mkdir()
            records = {}
            for character in models.Character:
                name = character.value
                root = assets / "prefabs" / name
                (root / "sprites").mkdir(parents=True)
                (root / "character.json").write_text(json.dumps({"character": name, "nodes": [
                    {"name": name, "children": [1]}, {"name": "Part01", "sprite": {"enabled": True}}]}), encoding="utf-8")
                (root / "composition.json").write_text(json.dumps({"defaultAppearance": "State01", "compositionMap": [{"Key": "State01", "Composition": ">Part01"}]}), encoding="utf-8")
                Image.new("RGBA", (200, 400), "red").save(root / "sprites/Part01.png")
                records[name] = [{"id": name + "-01", "nodes": ["Part01"], "appearance": ["State01"], "frequency": 0}]
            (assets / "presets/official_presets.json").write_text(json.dumps({"schema_version": 2, "source_digest": "fixture", "characters": records}), encoding="utf-8")
            with patch.object(self.rendering, "ASSETS", assets):
                _, codec = self.rendering._sprite_runtime()
                code = "#" + codec.encode("Ema", state.SpriteRecipe(base_preset="Ema-01"))
                request = types.SimpleNamespace(background="@BG001", sprites=(code,), author=None, text="资源更新")
                before = self.rendering.render_dialogue(request)
                Image.new("RGBA", (240, 400), "blue").save(assets / "prefabs/Ema/sprites/Part01.png")
                after = self.rendering.render_dialogue(request)
                self.assertNotEqual(before, after)
                renderer, _ = self.rendering._sprite_runtime()
                self.assertEqual(renderer.prefab("Ema")._sprite_size, (240, 400))


if __name__ == "__main__":
    unittest.main()
