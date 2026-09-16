import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "nonebot_plugin_manosaba_memes"
PACKAGE = "_manosaba_dialogue_regression"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(PLUGIN)]
sys.modules[PACKAGE] = package


def interaction_module():
    import nonebot

    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init()
    return importlib.import_module(f"{PACKAGE}.dialogue.interaction")


class DialogueParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = importlib.import_module(f"{PACKAGE}.dialogue.parser")

    def test_parameters_can_be_in_any_order_and_sprite_order_is_stable(self):
        request = self.parser.parse_dialogue(
            "*艾玛 #CFAMVMR9LZ 开始 @BG001 #23456789AB #BCDEFGHJKL 结束"
        )
        self.assertEqual(request.background, "@BG001")
        self.assertEqual(
            request.sprites,
            ("#CFAMVMR9LZ", "#23456789AB", "#BCDEFGHJKL"),
        )
        self.assertEqual(request.author, "Ema")
        self.assertEqual(request.text, "开始 结束")

    def test_none_unknown_and_omitted_author_are_distinct(self):
        hidden = self.parser.parse_dialogue("@BG001 *none 旁白")
        unknown = self.parser.parse_dialogue("@BG001 *? 是谁")
        omitted = self.parser.parse_dialogue("@BG001 没有姓名牌")
        self.assertIsNone(hidden.author)
        self.assertEqual(unknown.author, "?")
        self.assertIsNone(omitted.author)

    def test_quotes_and_escapes_keep_parameter_like_text_in_body(self):
        request = self.parser.parse_dialogue(
            '@BG001 "#CFAMVMR9LZ *艾玛" \\@BG002 \\*none'
        )
        self.assertEqual(request.sprites, ())
        self.assertIsNone(request.author)
        self.assertEqual(request.text, "#CFAMVMR9LZ *艾玛 @BG002 *none")

    def test_body_preserves_line_breaks(self):
        request = self.parser.parse_dialogue(
            "@BG001 #CFAMVMR9LZ 第一行\n第二行\n\n第三行"
        )
        self.assertEqual(request.text, "第一行\n第二行\n\n第三行")

    def test_body_keeps_line_break_before_parameter(self):
        request = self.parser.parse_dialogue(
            "第一行\n@BG001 #CFAMVMR9LZ 第二行"
        )
        self.assertEqual(request.text, "第一行\n第二行")

    def test_duplicate_singleton_parameters_are_rejected(self):
        cases = (
            "@BG001 @BG002 正文",
            "@BG001 *艾玛 *none 正文",
        )
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.parser.parse_dialogue(value)

    def test_four_sprites_are_rejected(self):
        with self.assertRaises(ValueError):
            self.parser.parse_dialogue(
                "@BG001 #CFAMVMR9LZ #23456789AB #BCDEFGHJKL #CDEFGHJKLM 正文"
            )

    def test_invalid_codes_missing_background_and_empty_body_are_rejected(self):
        cases = (
            "@BG001 #BAD 正文",
            "@BAD #CFAMVMR9LZ 正文",
            "#CFAMVMR9LZ 正文",
            "@BG001 #CFAMVMR9LZ",
            "@BG001 *不存在 正文",
            '@BG001 "没有结束',
        )
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.parser.parse_dialogue(value)


class BackgroundCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog_module = importlib.import_module(f"{PACKAGE}.dialogue.catalog")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="airicore-dialogue-catalog-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        backgrounds = []
        for index in range(1, 28):
            category = "场景" if index <= 26 else "插图"
            backgrounds.append(
                {
                    "code": f"@BG{index:03d}",
                    "category": category,
                    "path": f"backgrounds/BG{index:03d}.webp",
                    "name": f"背景 {index}",
                }
            )
        (self.root / "backgrounds.json").write_text(
            json.dumps({"version": 1, "backgrounds": backgrounds}, ensure_ascii=False),
            encoding="utf-8",
        )
        self.catalog = self.catalog_module.BackgroundCatalog(self.root)

    def test_entries_filter_lookup_and_page_with_global_numbers(self):
        self.assertEqual(len(self.catalog.entries()), 27)
        self.assertEqual(len(self.catalog.entries("场景")), 26)
        self.assertEqual(self.catalog.get("@bg027").name, "背景 27")
        first = self.catalog.page("场景", 1)
        self.assertEqual(len(first.entries), 25)
        self.assertEqual(first.entries[-1].code, "@BG025")
        page = self.catalog.page("场景", 2)
        self.assertEqual([entry.code for entry in page.entries], ["@BG026"])
        self.assertEqual((page.page, page.total_pages, page.start), (2, 2, 25))

    def test_invalid_category_unknown_code_and_bad_manifest_are_rejected(self):
        with self.assertRaises(ValueError):
            self.catalog.entries("人物")
        with self.assertRaises(KeyError):
            self.catalog.get("@BG999")
        (self.root / "backgrounds.json").write_text(
            json.dumps({"version": 2, "backgrounds": []}), encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            self.catalog_module.BackgroundCatalog(self.root)


class BackgroundStateTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.state_module = importlib.import_module(f"{PACKAGE}.dialogue.state")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="airicore-dialogue-state-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "background_sessions.json"

    async def test_picker_context_survives_restart_with_original_codes(self):
        context = self.state_module.BackgroundPickerContext(
            category="场景",
            page=2,
            codes=[f"@BG{index:03d}" for index in range(1, 12)],
        )
        store = self.state_module.BackgroundSessionStore(self.path)
        await store.set_message("onebot|1|channel|2|3|99", context)
        restored = self.state_module.BackgroundSessionStore(self.path)
        self.assertEqual(
            await restored.get_message("onebot|1|channel|2|3|99"), context
        )

    async def test_failed_update_keeps_previous_context(self):
        original = self.state_module.BackgroundPickerContext(
            category="场景", page=1, codes=["@BG001"]
        )
        changed = self.state_module.BackgroundPickerContext(
            category="场景", page=2, codes=["@BG001", "@BG002"]
        )
        store = self.state_module.BackgroundSessionStore(self.path)
        await store.set_message("message", original)
        with patch.object(store, "_write_atomic", side_effect=OSError("磁盘不可写")):
            with self.assertRaises(OSError):
                await store.set_message("message", changed)
        self.assertEqual(await store.get_message("message"), original)
        self.assertEqual(
            await self.state_module.BackgroundSessionStore(self.path).get_message(
                "message"
            ),
            original,
        )


class BackgroundInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.interaction = interaction_module()

    def test_background_command_supports_default_category_page_and_code(self):
        self.assertEqual(
            self.interaction.parse_background_command(""), ("picker", "场景", 1)
        )
        self.assertEqual(
            self.interaction.parse_background_command("插图 3"),
            ("picker", "插图", 3),
        )
        self.assertEqual(
            self.interaction.parse_background_command("2"), ("picker", "场景", 2)
        )
        self.assertEqual(
            self.interaction.parse_background_command("@bg012"),
            ("background", "@BG012", None),
        )

    def test_background_command_rejects_extra_or_invalid_arguments(self):
        for value in (
            "人物",
            "场景 0",
            "场景 二",
            "场景 插图",
            "场景 2 多余",
            "@BAD",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.interaction.parse_background_command(value)

    def test_picker_choice_uses_cross_page_numbering(self):
        codes = [f"@BG{index:03d}" for index in range(1, 27)]
        self.assertEqual(self.interaction.background_choice(codes, "B26"), "@BG026")
        with self.assertRaises(ValueError):
            self.interaction.background_choice(codes, "B27")

    def test_page_navigation_is_bounded(self):
        self.assertEqual(self.interaction.next_page(1, 25, "下一页"), 1)
        self.assertEqual(self.interaction.next_page(1, 26, "下一页"), 2)
        self.assertEqual(self.interaction.next_page(2, 26, "下一页"), 2)
        self.assertEqual(self.interaction.next_page(1, 26, "上一页"), 1)


class _PlainText:
    def __init__(self, text):
        self.text = text

    def extract_plain_text(self):
        return self.text


class _Event:
    def __init__(self, text="原始消息不应作为命令参数", user_id="10001"):
        self.text = text
        self.user_id = user_id

    def get_message(self):
        return _PlainText(self.text)

    def get_user_id(self):
        return self.user_id


class DialogueHandlerTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.interaction = interaction_module()

    async def asyncSetUp(self):
        import asyncio
        from utils import credit

        self.credit = credit
        self.directory = tempfile.TemporaryDirectory(prefix="airicore-dialogue-credit-")
        self.addCleanup(self.directory.cleanup)
        for name, value in (
            ("DATA_FILE", Path(self.directory.name) / "credits.pk"),
            ("_balances", {}),
            ("_loaded_file", None),
            ("_load_failed", False),
            ("_lock", asyncio.Lock()),
        ):
            patcher = patch.object(credit, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_dialogue_empty_and_help_use_command_argument(self):
        sent = []

        async def capture(message, **kwargs):
            sent.append(str(message))

        with patch.object(self.interaction.UniMessage, "send", capture):
            for value in ("", "-h", "帮助"):
                await self.interaction.handle_dialogue(
                    object(), _Event(), _PlainText(value)
                )
        self.assertEqual(len(sent), 3)
        self.assertTrue(all("魔裁对话 @背景短码" in value for value in sent))

    async def test_background_help_uses_command_argument(self):
        sent = []

        async def capture(message, **kwargs):
            sent.append(str(message))

        with patch.object(self.interaction.UniMessage, "send", capture):
            for value in ("-h", "帮助"):
                await self.interaction.handle_background(
                    object(), _Event(), _PlainText(value)
                )
        self.assertEqual(len(sent), 2)
        self.assertTrue(all("魔裁背景 [场景/插图/特效]" in value for value in sent))

    async def test_invalid_sprite_error_is_sent_before_charge(self):
        await self.credit.credit("10001", 20)
        sent = []

        async def capture(message, **kwargs):
            sent.append(str(message))

        with patch.object(self.interaction.UniMessage, "send", capture):
            await self.interaction.handle_dialogue(
                object(), _Event(), _PlainText("@BG001 #C222222222 正文")
            )
        self.assertEqual(len(sent), 1)
        self.assertIn("立绘短码无效", sent[0])
        self.assertEqual(await self.credit.get_balance("10001"), 20)

    async def test_failed_dialogue_send_refunds_charge(self):
        await self.credit.credit("10001", 20)
        with (
            patch.object(self.interaction, "run_sync", AsyncMock(return_value=b"png")),
            patch.object(
                self.interaction.UniMessage,
                "send",
                AsyncMock(side_effect=OSError("发送失败")),
            ),
        ):
            with self.assertRaises(OSError):
                await self.interaction.handle_dialogue(
                    object(), _Event(), _PlainText("@BG001 正文")
                )
        self.assertEqual(await self.credit.get_balance("10001"), 20)


class BackgroundReplyHandlerTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.interaction = interaction_module()

    async def test_only_matching_reply_context_selects_background(self):
        directory = tempfile.TemporaryDirectory(prefix="airicore-dialogue-reply-")
        self.addCleanup(directory.cleanup)
        store = self.interaction.BackgroundSessionStore(
            Path(directory.name) / "sessions.json"
        )
        context = self.interaction.BackgroundPickerContext(
            category="场景", page=1, codes=["@BG001"]
        )
        await store.set_message("matched", context)
        sender = AsyncMock()
        reply = [self.interaction.Reply("42")]
        with (
            patch.object(self.interaction, "_SESSION_STORE", store),
            patch.object(self.interaction, "_message_key", return_value="missing"),
            patch.object(self.interaction, "_send_background", sender),
        ):
            await self.interaction.handle_background_followup(
                object(), _Event("B1"), reply
            )
            sender.assert_not_awaited()
        with (
            patch.object(self.interaction, "_SESSION_STORE", store),
            patch.object(self.interaction, "_message_key", return_value="matched"),
            patch.object(self.interaction, "_send_background", sender),
        ):
            await self.interaction.handle_background_followup(
                object(), _Event("B1"), reply
            )
        sender.assert_awaited_once()
        self.assertEqual(sender.await_args.args[2].code, "@BG001")


if __name__ == "__main__":
    unittest.main()
