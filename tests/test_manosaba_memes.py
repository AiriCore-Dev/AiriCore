import asyncio
import importlib
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "nonebot_plugin_manosaba_memes"
PACKAGE = "_manosaba_regression"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(PLUGIN)]
sys.modules[PACKAGE] = package


class MigrationTests(unittest.TestCase):
    def test_plugin_is_available(self):
        self.assertTrue((PLUGIN / "__init__.py").is_file(), "魔裁插件尚未移植")

    def test_invalid_face_is_rejected_before_file_access(self):
        drawer = importlib.import_module(f"{PACKAGE}.drawer")
        for face in ("../trial/ui/black", "不存在", "../../outside"):
            with self.subTest(face=face), self.assertRaises(ValueError):
                drawer.get_anan_base_image(face)

    def test_trial_option_limit(self):
        drawer = importlib.import_module(f"{PACKAGE}.drawer")
        models = importlib.import_module(f"{PACKAGE}.models")
        for count in (0, 7):
            with self.subTest(count=count), self.assertRaises(ValueError):
                drawer.draw_trial(models.Character.EMA, [models.Option(models.Statement.DOUBT, "测试")] * count)

    def test_anan_and_trial_render_real_png(self):
        drawer = importlib.import_module(f"{PACKAGE}.drawer")
        models = importlib.import_module(f"{PACKAGE}.models")
        for payload in (
            drawer.draw_anan("Airi 移植验证", "开心"),
            drawer.draw_trial(models.Character.EMA, [models.Option(models.Statement.DOUBT, "这是验证选项")]),
        ):
            with Image.open(io.BytesIO(payload)) as image:
                image.load()
                self.assertGreater(image.width, 300)
                self.assertGreater(image.height, 300)
                self.assertIsNotNone(image.getbbox())


class SessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = importlib.import_module(f"{PACKAGE}.sprite_editor.state")
        self.directory = tempfile.TemporaryDirectory(prefix="airicore-manosaba-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sessions.json"
        self.store = self.state.SessionStore(self.path)
        self.recipe = self.state.SpriteRecipe(base_preset="test-preset")

    async def test_roundtrip_and_defensive_copies(self):
        code = await self.store.put_sprite("Ema", self.recipe)
        context = self.state.MessageContext(kind="sprite", character="Ema", sprite=code)
        await self.store.set_message("onebot|1|group|2|3", context)
        restored = self.state.SessionStore(self.path)
        self.assertEqual((await restored.get_sprite(code)).recipe, self.recipe)
        self.assertEqual(await restored.get_message("onebot|1|group|2|3"), context)
        copy = await restored.get_sprite(code)
        copy.recipe.overrides.append("changed")
        self.assertEqual((await restored.get_sprite(code)).recipe.overrides, [])

    async def test_failed_sprite_write_can_be_retried(self):
        await self.store.load()
        with patch.object(self.store, "_write_atomic", side_effect=OSError("磁盘不可写")):
            with self.assertRaises(OSError):
                await self.store.put_sprite("Ema", self.recipe)
        self.assertFalse(self.store.data.sprites)
        code = await self.store.put_sprite("Ema", self.recipe)
        self.assertIsNotNone(await self.state.SessionStore(self.path).get_sprite(code))

    async def test_failed_message_update_preserves_previous_context(self):
        original = self.state.MessageContext(kind="picker", character="Ema", picker="preset", choices=["first"])
        await self.store.set_message("message", original)
        changed = original.model_copy(update={"page": 2})
        with patch.object(self.store, "_write_atomic", side_effect=OSError("磁盘不可写")):
            with self.assertRaises(OSError):
                await self.store.set_message("message", changed)
        self.assertEqual(await self.store.get_message("message"), original)
        self.assertEqual(await self.state.SessionStore(self.path).get_message("message"), original)

    async def test_corrupt_data_is_backed_up_before_recovery(self):
        self.path.write_bytes(b"broken json")
        await self.store.load()
        backups = list(self.path.parent.glob("sessions.json.broken.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b"broken json")
        await self.store.put_sprite("Ema", self.recipe)
        self.assertTrue(self.path.is_file())


class CacheTests(unittest.TestCase):
    def test_bitmaps_obey_modes_and_decoded_byte_budget(self):
        cache = importlib.import_module(f"{PACKAGE}.asset_cache")
        from utils import cache as shared

        with tempfile.TemporaryDirectory(prefix="airicore-bitmap-") as directory:
            path = Path(directory) / "test.png"
            Image.new("RGBA", (32, 16), "red").save(path)
            for mode in ("ram", "balanced", "disk"):
                with self.subTest(mode=mode), patch.object(shared, "_mode", mode):
                    cache.clear()
                    cache.get_bitmap(path)
                    cache.get_bitmap(path)
                    self.assertEqual(cache._bitmaps.bytes, 0 if mode == "disk" else 32 * 16 * 4)
            with patch.object(shared, "_mode", "balanced"), patch.object(cache._bitmaps, "max_bytes", 1024):
                cache.clear()
                cache.get_bitmap(path)
                cache.get_bitmap(path)
                self.assertEqual(cache._bitmaps.bytes, 0)

    def test_changed_bitmap_is_not_reused(self):
        cache = importlib.import_module(f"{PACKAGE}.asset_cache")
        from utils import cache as shared

        with tempfile.TemporaryDirectory(prefix="airicore-bitmap-") as directory, patch.object(shared, "_mode", "ram"):
            path = Path(directory) / "test.png"
            Image.new("RGBA", (8, 8), "red").save(path)
            first = cache.get_bitmap(path)
            Image.new("RGBA", (16, 16), "blue").save(path)
            second = cache.get_bitmap(path)
            self.assertIsNot(first, second)
        cache.clear()


class BillingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from utils import credit

        self.credit = credit
        self.billing = importlib.import_module(f"{PACKAGE}.billing")
        directory = tempfile.TemporaryDirectory(prefix="airicore-manosaba-credit-")
        self.addCleanup(directory.cleanup)
        for name, value in (
            ("DATA_FILE", Path(directory.name) / "credits.pk"),
            ("_balances", {}),
            ("_loaded_file", None),
            ("_load_failed", False),
            ("_lock", asyncio.Lock()),
        ):
            patcher = patch.object(credit, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_creation_costs_ten_and_edit_is_free(self):
        await self.credit.credit("10001", 30)
        async with self.billing.production_charge("10001", paid=True):
            self.assertEqual(await self.credit.get_balance("10001"), 20)
        async with self.billing.production_charge("10001", paid=False):
            pass
        self.assertEqual(await self.credit.get_balance("10001"), 20)

    async def test_failed_send_and_cancellation_refund(self):
        await self.credit.credit("10001", 20)
        for error in (OSError("发送失败"), asyncio.CancelledError()):
            with self.assertRaises(type(error)):
                async with self.billing.production_charge("10001", paid=True):
                    raise error
            self.assertEqual(await self.credit.get_balance("10001"), 20)

    async def test_insufficient_balance_stops_production(self):
        await self.credit.credit("10001", 9)
        with self.assertRaises(self.credit.ChargeRejected):
            async with self.billing.production_charge("10001", paid=True):
                self.fail("余额不足不应继续制作")
        self.assertEqual(await self.credit.get_balance("10001"), 9)


if __name__ == "__main__":
    unittest.main()
