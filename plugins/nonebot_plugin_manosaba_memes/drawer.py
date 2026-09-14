import math
from pathlib import Path

from sketchbook import (
    Align,
    Drawer,
    Layer,
    ParseRule,
    Region,
    ScaleMode,
    StyleMod,
    TextStyle,
    VAlign,
)

from .asset_cache import get_fonts, get_source
from .models import Character, Option, Statement
from .utils import get_png_size

PLUGIN_PATH = Path(__file__).parent
TRIAL_ASSET_PATH = PLUGIN_PATH / "assets/trial"
TRIAL_CHARACTER_PATH = TRIAL_ASSET_PATH / "characters"
TRIAL_STATEMENT_PATH = TRIAL_ASSET_PATH / "statements"
TRIAL_UI_PATH = TRIAL_ASSET_PATH / "ui"


def get_anan_base_image(face: str | None = None) -> str:
    if face is not None and face not in {"害羞", "生气", "病娇", "无语", "开心"}:
        raise ValueError("表情无效，可选：害羞、生气、病娇、无语、开心")

    if face is None:
        return str(PLUGIN_PATH / "assets/anan/base.png")
    else:
        return str(PLUGIN_PATH / f"assets/anan/{face}.png")


def draw_anan(text: str, face: str | None = None) -> bytes:
    if not text.strip() or len(text) > 500:
        raise ValueError("请输入 1～500 字的文本")

    fonts = get_fonts(PLUGIN_PATH / "assets/fonts/SourceHanSansSC-Bold.otf")
    drawer = Drawer.from_image(get_source(get_anan_base_image(face)), fonts)
    drawer.layer(
        Layer("text").text(
            text,
            Region(100, 432, 319, 204),
            TextStyle(color=(0, 0, 0, 255), align=Align.Center, valign=VAlign.Middle),
        )
    )
    drawer.overlay(get_source(PLUGIN_PATH / "assets/anan/base_overlay.png"))
    return drawer.render()


def get_statement_image(statement: Statement) -> str:


    mapping = {
        Statement.AGREEMENT: "agreement.png",
        Statement.DOUBT: "doubt.png",
        Statement.PURJURY: "perjury.png",
        Statement.REFUTATION: "refutation.png",
        Statement.MAGIC_CHIYUSAISEI: "magic_chiyusaisei.png",
        Statement.MAGIC_EKITAISOUSA: "magic_ekitaisousa.png",
        Statement.MAGIC_FUYUU: "magic_fuyuu.png",
        Statement.MAGIC_GENSHI: "magic_genshi.png",
        Statement.MAGIC_HAKKA: "magic_hakka.png",
        Statement.MAGIC_IREKAWARI: "magic_irekawari.png",
        Statement.MAGIC_KAIRIKI: "magic_kairiki.png",
        Statement.MAGIC_MAJOGOROSHI: "magic_majogoroshi.png",
        Statement.MAGIC_MONOMANE: "magic_monomane.png",
        Statement.MAGIC_SENNOU: "magic_sennou.png",
        Statement.MAGIC_SENRIGAN: "magic_senrigan.png",
        Statement.MAGIC_SHINIMODORI: "magic_shinimodori.png",
        Statement.MAGIC_SHISENYUUDOU: "magic_shisenyuudou.png",
    }
    return str(TRIAL_STATEMENT_PATH / mapping[statement])


def get_option_coordinates(number: int) -> list[tuple[int, int]]:


    if number % 2 == 1:
        padding = min(
            286,
            (1080 - 364 - 216) // math.floor(number / 2)
            if math.floor(number / 2) != 0
            else 286,
            (-364 + 47) // math.ceil(-number / 2)
            if math.ceil(-number / 2) != 0
            else 286,
        )
        return [
            (29, 364 + padding * i)
            for i in range(math.ceil(-number / 2), math.floor(number / 2) + 1)
        ]
    else:
        padding = min(
            286,
            (1080 - 364 - 216) // (math.floor(number / 2) - 0.5),
            (-364 + 47) // (math.ceil(-number / 2) + 0.5),
        )
        return [
            (29, int(364 + padding * (i + 0.5)))
            for i in range(math.ceil(-number / 2), math.floor(number / 2))
        ]


def draw_trial(character: Character, options: list[Option]) -> bytes:
    if not 1 <= len(options) <= 6:
        raise ValueError("审判选项数量须为 1～6 个")
    if any(not option.text.strip() or len(option.text) > 300 for option in options):
        raise ValueError("每个审判选项须为 1～300 字")

    fonts = get_fonts(PLUGIN_PATH / "assets/fonts/SourceHanSerifSC.otf")
    drawer = Drawer.from_image(get_source(TRIAL_UI_PATH / "black.png"), fonts)
    drawer.layer(
        Layer("background").image_fit(
            get_source(TRIAL_UI_PATH / "background.png"),
            Region(0, 0, 1260, 1080),
            scale=ScaleMode.Stretch,
        )
    )

    character_image = TRIAL_CHARACTER_PATH / f"{character.value.lower()}.png"
    character_width, character_height = get_png_size(character_image)
    drawer.layer(
        Layer("character").image_fit(
            get_source(character_image),
            Region(1260 - character_width, 0, character_width, character_height),
            scale=ScaleMode.Stretch,
        )
    )

    coordinates = get_option_coordinates(len(options))
    for idx, (option, (x, y)) in enumerate(zip(options, coordinates)):

        drawer.layer(
            Layer(f"option_bg_{idx}").image_fit(
                get_source(TRIAL_UI_PATH / "option.png"),
                Region(x, y, 802, 216),
                scale=ScaleMode.Stretch,
            )
        )


        drawer.layer(
            Layer(f"option_text_{idx}").text(
                option.text,
                Region(x + 109, y + 32, 589, 150),
                TextStyle(
                    color=(39, 33, 30, 255),
                    max_font_size=32.0,
                    parse_rules=[
                        ParseRule(
                            "【文本】",
                            "【",
                            "】",
                            StyleMod.color(39, 33, 30, 255),
                            keep_delim=True,
                        )
                    ],
                ),
            )
        )


        drawer.layer(
            Layer(f"statement_{idx}").image_fit(
                get_source(get_statement_image(option.statement)),
                Region(x + 21, y - 43, 146, 128),
                scale=ScaleMode.Stretch,
            )
        )

    return drawer.render()
