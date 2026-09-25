import hashlib
import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = '_astral_card_tests'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / 'plugins/airi_astral_party')]
sys.modules[PACKAGE] = package


class NativeCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.render = importlib.import_module(f'{PACKAGE}.card_rendering')

    def test_all_game_cards_render_with_native_dimensions(self):
        for key in self.render.CARDS:
            with self.subTest(card=key):
                image = self.render.render_card({'id': int(key)}, {}, 4)
                self.assertEqual(image.size, (440, 644))
                self.assertGreater(image.getchannel('A').getextrema()[1], 0)

    def test_original_art_is_composited_without_repainting(self):
        image = self.render.render_card({'id': 10001}, {}, 4)
        art = Image.open(self.render.ASSETS / self.render.CARDS['10001']['image']).convert('RGBA')
        child = next(row for row in self.render.LAYOUT['items']['micc2g']['children'] if row['name'] == 'loader_FrontCard')
        art = self.render.loader_image(art, child)
        expected = art.crop((112, 81, 312, 261))
        difference = ImageChops.difference(image.crop((130, 100, 330, 280)).convert('RGB'), expected.convert('RGB'))
        self.assertLessEqual(max(maximum for _, maximum in difference.getextrema()), 1)

    def test_runtime_cost_changes_game_cost_icons(self):
        free = self.render.render_card({'id': 10001, 'cost': 0}, {}, 4)
        paid = self.render.render_card({'id': 10001, 'cost': 3}, {}, 4)
        self.assertIsNotNone(ImageChops.difference(free.crop((20, 85, 87, 350)).convert('RGB'), paid.crop((20, 85, 87, 350)).convert('RGB')).getbbox())
        self.assertEqual(free.crop((130, 100, 330, 280)).tobytes(), paid.crop((130, 100, 330, 280)).tobytes())

    def test_cost_points_follow_attack_and_defend_colors(self):
        attack = self.render.render_card({'id': 10001}, {}, 4)
        defend = self.render.render_card({'id': 10002}, {}, 4)
        for image, channel in ((attack, 0), (defend, 2)):
            pixels = list(image.crop((39, 99, 66, 126)).convert('RGB').getdata())
            self.assertGreater(sum(pixel[channel] > pixel[1 if channel == 0 else 0] + 60 for pixel in pixels), 100)


    def test_hidden_and_unknown_cards_do_not_show_another_cards_art(self):
        hidden = self.render.render_card({'id': None}, {}, 4)
        unknown = self.render.render_card({'id': 999999}, {}, 4)
        known = self.render.render_card({'id': 10001}, {}, 4)
        self.assertEqual(hidden.tobytes(), unknown.tobytes())
        self.assertNotEqual(hidden.tobytes(), known.tobytes())

    def test_grouping_keeps_distinct_states_and_hidden_cards_separate(self):
        cards = [{'id': 10001, 'unique_id': 1}, {'id': 10001, 'unique_id': 2},
                 {'id': 10001, 'cost': 0}, {'id': 10001, 'temporary': True},
                 {'id': 10001, 'purify': 1}, {'id': None}, {'id': None}]
        groups = self.render.group_cards(cards, {}, 4)
        self.assertEqual([count for _, count in groups], [2, 1, 1, 1, 1, 1])
        self.assertEqual(len(cards), 7)

    def test_manifest_covers_and_matches_shipped_card_assets(self):
        manifest = json.loads((self.render.ASSETS / 'cards_manifest.json').read_text('utf8'))
        for name, row in manifest['files'].items():
            with self.subTest(asset=name):
                self.assertEqual(hashlib.sha256((self.render.ASSETS / name).read_bytes()).hexdigest(), row['sha256'])
        self.assertEqual(manifest['count'], len(self.render.CARDS))
        self.assertTrue(self.render.CATALOG['buffs']['1211201'])

    def test_templates_and_localized_buff_links_are_resolved(self):
        text = self.render.resolve_text('造成{damage=3}伤害 [Astral=Buff:1211201][/Astral]')
        self.assertNotIn('{', text)
        self.assertNotIn('Astral', text)
        self.assertIn('[color=#FFB425]', text)
        self.assertIn(self.render.CATALOG['buffs']['1211201'], text)

    def test_inline_description_icons_use_native_assets(self):
        child = {'width': 180, 'height': 160, 'fontSize': 88, 'font': 'JingNanBoBoHei'}
        with patch.object(self.render, 'get_image', wraps=self.render.get_image) as source:
            image = self.render.rich_text("<img src='ui://xuaw6o8jkva0ay' width='140' height='140'/>", child)
        self.assertEqual(source.call_count, 1)
        self.assertIsNotNone(image.getbbox())

    def test_selected_cosmetics_and_alt_art_change_native_card(self):
        original = self.render.render_card({'id': 21002}, {}, 4)
        alternate = self.render.render_card({'id': 21002, 'alt_art_id': 13021002}, {}, 4)
        self.assertNotEqual(original.tobytes(), alternate.tobytes())
        self.assertGreater(alternate.width, 440)
        self.assertEqual(alternate.info['logical_size'], (440, 644))
        item = next(key for key, value in self.render.CATALOG['back_items'].items() if str(value) != self.render.CATALOG['default_back'])
        self.assertNotEqual(original.tobytes(), self.render.render_card({'id': 21002}, {'card_back_item_id': int(item)}, 4).tobytes())


if __name__ == '__main__':
    unittest.main()
