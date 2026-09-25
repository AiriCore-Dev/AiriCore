import base64
import importlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import nonebot
from nonebot.adapters.onebot.v11 import Message


try:
    nonebot.get_driver()
except ValueError:
    nonebot.init(_env_file=None, driver="~fastapi", log_level="WARNING")

plugin = importlib.import_module("plugins.airi_llm")


class LlmEmojiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="airicore-emoji-test-")
        self.addCleanup(directory.cleanup)
        self.image_bytes = base64.b64decode(
            "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
        )
        self.paths = []
        self.images = {}
        for name, color in (
            ("neutral.gif", b"\x80\x80\x80"),
            ("positive.gif", b"\xff\xff\x00"),
            ("negative.gif", b"\x00\x00\xff"),
        ):
            path = Path(directory.name) / name
            self.images[name] = self.image_bytes[:13] + color + self.image_bytes[16:]
            path.write_bytes(self.images[name])
            self.paths.append(str(path))
        for target, name, value in (
            (plugin.airi_state, "emoji_list", self.paths),
            (plugin.airi_state, "emoji_moods", {
                "neutral.gif": 0.0, "positive.gif": 0.8, "negative.gif": -0.8,
            }),
        ):
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        sleeper = patch.object(plugin.asyncio, "sleep", new_callable=AsyncMock)
        sleeper.start()
        self.addCleanup(sleeper.stop)
        self.bot = SimpleNamespace(send_group_msg=AsyncMock())

    def sent_segments(self):
        return [
            segment
            for call in self.bot.send_group_msg.call_args_list
            for segment in Message(call.kwargs["message"])
        ]

    async def test_neutral_unknown_and_missing_emotions_can_send_emoji(self):
        for emotion in ("neutral", "unknown", None, "anxious"):
            with self.subTest(emotion=emotion):
                self.bot.send_group_msg.reset_mock()
                with patch.object(plugin.random, "random", side_effect=[0.0, 0.9]):
                    await plugin.send_llm_reply(
                        "一起聊聊吧", bot=self.bot, group_id="10001",
                        reply_emotion=emotion,
                    )
                segments = self.sent_segments()
                self.assertEqual([segment.type for segment in segments], ["text", "image"])
                encoded = segments[-1].data["file"]
                self.assertTrue(encoded.startswith("base64://"))
                self.assertIn(base64.b64decode(encoded[9:]), self.images.values())

    async def test_passive_candidate_can_send_leading_emoji(self):
        result = plugin.llm_client.normalize_dialogue_result({
            "addressed": False, "emotion": "neutral", "reply_strategy": "react",
            "addressed_reply": "", "passive_reply": "这话题挺有意思",
        })
        reply, reply_to, _ = plugin._select_dialogue_candidate(result, False, set())
        with patch.object(plugin.random, "random", side_effect=[0.0, 0.0]):
            await plugin.send_llm_reply(
                reply, reply_to, bot=self.bot, group_id="10001",
                reply_emotion=result["emotion"],
            )
        self.assertEqual([segment.type for segment in self.sent_segments()], ["image", "text"])

    async def test_probability_miss_sends_only_text(self):
        with patch.object(plugin.random, "random", return_value=0.99):
            await plugin.send_llm_reply(
                "今天过得怎么样", bot=self.bot, group_id="10001", reply_emotion="positive",
            )
        self.assertEqual([segment.type for segment in self.sent_segments()], ["text"])

    async def test_emoji_selection_matches_emotion(self):
        for emotion, expected in (("neutral", "neutral.gif"), ("positive", "positive.gif"), ("sad", "negative.gif")):
            with self.subTest(emotion=emotion):
                self.bot.send_group_msg.reset_mock()
                with patch.object(plugin.random, "random", side_effect=[0.0, 0.9]):
                    await plugin.send_llm_reply(
                        "一起聊聊吧", bot=self.bot, group_id="10001", reply_emotion=emotion,
                    )
                segments = self.sent_segments()
                self.assertEqual([segment.type for segment in segments], ["text", "image"])
                self.assertEqual(base64.b64decode(segments[-1].data["file"][9:]), self.images[expected])

    async def test_failed_leading_emoji_does_not_block_quoted_text(self):
        self.bot.send_group_msg.side_effect = [RuntimeError("图片发送失败"), None]
        with patch.object(plugin.random, "random", side_effect=[0.0, 0.0]):
            await plugin.send_llm_reply(
                "今天也加油", "123", bot=self.bot, group_id="10001", reply_emotion="positive",
            )
        segments = self.sent_segments()
        self.assertEqual([segment.type for segment in segments], ["image", "reply", "text"])
        self.assertEqual(segments[1].data["id"], "123")
        self.assertEqual(segments[2].data["text"], "今天也加油")

    async def test_empty_emoji_library_still_sends_text(self):
        with patch.object(plugin.airi_state, "emoji_list", []), patch.object(
            plugin.random, "random", side_effect=[0.0, 0.9],
        ):
            await plugin.send_llm_reply(
                "今天也加油", bot=self.bot, group_id="10001", reply_emotion="positive",
            )
        self.assertEqual([segment.type for segment in self.sent_segments()], ["text"])
