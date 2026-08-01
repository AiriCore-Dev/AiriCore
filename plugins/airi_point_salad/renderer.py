import base64
from collections import Counter
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from utils.asset_cache import get_font, get_image_copy
from utils.cache_mode import (
    get_cache_budget_bytes,
    is_balanced,
    is_disk,
    is_ram,
    register_cache,
)
from utils.cache_policy import ByteLRU, value_bytes

from .art_assets import (
    ASSET_DIR,
    BACK_BASE_PATH,
    FRONT_BASE_PATH,
    NAMEPLATE_PATH,
    TITLE_PATH,
    chibi_path,
    portrait_path,
)
from .missions import mission_catalog
from .models import Card, Character, GameMode, GameState, PlayerState, RuleKind
from .scoring import rank_players


CARD_SIZE = (750, 1050)
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
SCORE_ICON_SIZE = 204
SCORE_RULE_FONT_SIZE = 72
SCORE_VALUE_FONT_SIZE = 120
GOLD = (205, 171, 96, 255)
FONT_PATH = ASSET_DIR / "font.ttf"
_render_cache = ByteLRU(
    get_cache_budget_bytes("images"),
    owner="point_salad.rendered",
)
register_cache("point_salad.rendered", _render_cache)


CHARACTER_COLORS = {
    Character.MINORI: ((204, 246, 219), (72, 174, 116)),
    Character.HARUKA: ((211, 239, 252), (65, 142, 193)),
    Character.AIRI: ((253, 210, 231), (218, 84, 148)),
    Character.SHIZUKU: ((219, 236, 244), (95, 144, 164)),
    Character.MIKU: ((205, 247, 242), (50, 169, 166)),
    Character.RIN: ((255, 239, 178), (224, 164, 40)),
}


CHARACTER_INITIALS = {
    Character.MINORI: "MN",
    Character.HARUKA: "HR",
    Character.AIRI: "AI",
    Character.SHIZUKU: "SZ",
    Character.MIKU: "MK",
    Character.RIN: "RN",
}


def font(size: int):
    return get_font(FONT_PATH, size)


def character_source(character: Character) -> Image.Image:
    return get_image_copy(portrait_path(character)).convert("RGBA")


def chibi_source(character: Character) -> Image.Image:
    return get_image_copy(chibi_path(character)).convert("RGBA")


def gradient(size, top, bottom):
    layer = Image.linear_gradient("L").resize(size)
    return ImageOps.colorize(layer, top, bottom).convert("RGBA")


def _configure_render_cache() -> None:
    _render_cache.max_bytes = 0 if is_ram() else get_cache_budget_bytes("images")
    _render_cache.probationary = is_balanced()


def _cached_image(key, build) -> Image.Image:
    if is_disk():
        _render_cache.clear()
        return build().copy()
    _configure_render_cache()
    cached = _render_cache.get(key)
    if cached is not None:
        return cached.copy()
    image = build()
    _render_cache.put(key, image, value_bytes(image))
    return image.copy()


def _build_character_front(character: Character) -> Image.Image:
    image = get_image_copy(FRONT_BASE_PATH).convert("RGBA")
    art = character_source(character)
    art.thumbnail((650, 840), Image.Resampling.LANCZOS)
    x = (CARD_SIZE[0] - art.width) // 2
    y = max(45, 885 - art.height)
    shadow = Image.new("RGBA", art.size)
    shadow.putalpha(art.getchannel("A").filter(ImageFilter.GaussianBlur(14)))
    image.alpha_composite(shadow, (x + 10, y + 14))
    image.alpha_composite(art, (x, y))
    nameplate = get_image_copy(NAMEPLATE_PATH).convert("RGBA")
    nameplate.thumbnail((650, 118), Image.Resampling.LANCZOS)
    plate_x = (CARD_SIZE[0] - nameplate.width) // 2
    plate_y = 890 + (118 - nameplate.height) // 2
    image.alpha_composite(nameplate, (plate_x, plate_y))
    draw = ImageDraw.Draw(image)
    name = character.display_name
    draw.text(
        (375, 928),
        name,
        font=font(46),
        anchor="mm",
        fill=(255, 255, 255),
        stroke_width=2,
        stroke_fill=(71, 52, 69),
    )
    draw.text(
        (375, 974),
        character.value.upper(),
        font=font(22),
        anchor="mm",
        fill=(244, 232, 238),
        stroke_width=1,
        stroke_fill=(71, 52, 69),
    )
    return image


def render_character_front(character: Character) -> Image.Image:
    def build():
        return _build_character_front(character)

    return _cached_image(("character_front", character.value), build)


def _build_character_icon(character: Character, size: int) -> Image.Image:
    source = chibi_source(character)
    bbox = source.getchannel("A").getbbox()
    if bbox is not None:
        source = source.crop(bbox)
    source.thumbnail((size - 14, size - 14), Image.Resampling.LANCZOS)
    icon = Image.new("RGBA", (size, size), CHARACTER_COLORS[character][0] + (255,))
    icon.alpha_composite(
        source,
        ((size - source.width) // 2, (size - source.height) // 2),
    )
    mask = Image.new("L", (size, size))
    ImageDraw.Draw(mask).ellipse((3, 3, size - 4, size - 4), fill=255)
    icon.putalpha(mask)
    draw = ImageDraw.Draw(icon)
    draw.ellipse((3, 3, size - 4, size - 4), outline=GOLD, width=max(2, size // 24))
    draw.text(
        (size - 8, size - 10),
        CHARACTER_INITIALS[character],
        font=font(max(12, size // 6)),
        anchor="rs",
        fill=(50, 42, 55),
        stroke_width=2,
        stroke_fill=(255, 255, 255),
    )
    return icon


def render_character_icon(character: Character, size: int = 100) -> Image.Image:
    def build():
        return _build_character_icon(character, size)

    return _cached_image(("character_icon", character.value, size), build)


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
        image.alpha_composite(icon, (icon_x, 270))
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


def rule_text(card: Card) -> tuple[str, str]:
    rule = card.rule
    names = [character.display_name for character in rule.characters]
    if rule.kind is RuleKind.EACH:
        return f"每个 {names[0]}", f"+{rule.points}"
    if rule.kind is RuleKind.PAIR:
        return f"每组\n{names[0]}＋{names[1]}", f"+{rule.points}"
    if rule.kind is RuleKind.SET:
        return "每组三名角色", f"+{rule.points}"
    if rule.kind is RuleKind.COMPARE:
        return f"{names[0]} {rule.relation}\n{names[1]}", f"+{rule.points}"
    return (
        f"每个 {names[0]} ＋{rule.points}\n每个 {names[1]}\n{rule.penalty}",
        "风险牌",
    )


def center_status(state: GameState, player: PlayerState) -> str:
    if player.skill_used:
        return "已使用"
    if state.pending_skill.get("user_id") == player.user_id:
        return {
            "airi_armed": "已准备：sl ta A A1",
            "minori_armed": "已准备：先 sl ta A1 B2",
            "minori_swap": "待交换：sl sk A1 C2",
        }.get(state.pending_skill.get("kind"), "待完成")
    return "可使用"


def render_board(state: GameState, _viewer_id: str) -> str:
    current = state.players[state.current_player]
    mission_height = 280 if state.mode is GameMode.MIX else 0
    player_header_y = SECTION_Y + mission_height
    player_rows_y = player_header_y + 80
    detail_y = player_rows_y + len(state.players) * PLAYER_ROW_HEIGHT + 80
    detail_lines = max(1, len(current.score_cards))
    height = max(
        3100 if state.mode is GameMode.MIX else 2800,
        detail_y + detail_lines * DETAIL_LINE_HEIGHT + 230,
    )
    image = gradient((BOARD_WIDTH, height), (246, 255, 252), (255, 244, 251))
    draw = ImageDraw.Draw(image)
    title = get_image_copy(TITLE_PATH).convert("RGBA")
    title.thumbnail((520, 230), Image.Resampling.LANCZOS)
    image.alpha_composite(title, (80, 45))
    mode = "混合模式" if state.mode is GameMode.MIX else "主题原版"
    speed = "快速局" if state.speed.value == "quick" else "标准局"
    draw.text(
        (2040, 92),
        f"{speed} · {mode}",
        font=font(58),
        anchor="ra",
        fill=(66, 74, 83),
    )
    draw.text(
        (2040, 170),
        f"第 {state.turn_number} 回合 · 牌库 {len(state.deck)}",
        font=font(46),
        anchor="ra",
        fill=(104, 91, 108),
    )
    draw.rounded_rectangle(
        (80, 270, 2080, 400),
        30,
        fill=(222, 247, 241),
        outline=(92, 176, 160),
        width=4,
    )
    draw.text(
        (125, 335),
        f"当前回合：{current.name}",
        font=font(52),
        anchor="lm",
        fill=(50, 120, 108),
    )
    if current.center is not None:
        status = center_status(state, current)
        draw.text(
            (2030, 335),
            f"Center：{current.center.display_name} · {status}",
            font=font(36),
            anchor="rm",
            fill=(73, 112, 122),
        )
    score_width, score_height = MARKET_SCORE_SIZE
    character_width, character_height = MARKET_CHARACTER_SIZE
    for column in range(3):
        x = MARKET_X[column]
        draw.text(
            (x + score_width // 2, 470),
            chr(ord("A") + column),
            font=font(60),
            anchor="mm",
            fill=(95, 74, 97),
        )
        score_id = state.score_market[column]
        if score_id:
            paste_card(
                image,
                render_score_back(state.cards[score_id]),
                x,
                MARKET_SCORE_Y,
                score_width,
                score_height,
            )
        for row in range(2):
            card_id = state.character_market[column][row]
            y = MARKET_CHARACTER_Y + row * MARKET_CHARACTER_STEP
            if card_id:
                character_x = x + (score_width - character_width) // 2
                paste_card(
                    image,
                    render_character_front(state.cards[card_id].character),
                    character_x,
                    y,
                    character_width,
                    character_height,
                )
                draw.text(
                    (x + 365, y + character_height // 2),
                    f"{chr(65 + column)}{row + 1}",
                    font=font(42),
                    anchor="lm",
                    fill=(71, 62, 76),
                )
    if state.mode is GameMode.MIX:
        catalog = mission_catalog()
        draw.text(
            (80, SECTION_Y),
            "LIVE MISSION",
            font=font(48),
            fill=(171, 118, 37),
        )
        for index, mission_id in enumerate(state.active_missions):
            mission = catalog[mission_id]
            x = 80 + index * 1000
            draw.rounded_rectangle(
                (x, SECTION_Y + 80, x + 920, SECTION_Y + 200),
                24,
                fill=(255, 249, 230),
                outline=(215, 186, 107),
                width=3,
            )
            draw.text(
                (x + 35, SECTION_Y + 140),
                mission_label(mission.kind, mission.amount),
                font=font(36),
                anchor="lm",
                fill=(84, 69, 71),
            )
            draw.text(
                (x + 885, SECTION_Y + 140),
                f"+{mission.points}",
                font=font(42),
                anchor="rm",
                fill=(195, 139, 35),
            )
    draw.text(
        (80, player_header_y),
        "PLAYERS",
        font=font(48),
        fill=(89, 75, 92),
    )
    for index, player in enumerate(state.players):
        y = player_rows_y + index * PLAYER_ROW_HEIGHT
        active = index == state.current_player
        fill = (231, 249, 246) if active else (255, 255, 255)
        draw.rounded_rectangle(
            (80, y, 2080, y + 92),
            20,
            fill=fill,
            outline=(226, 210, 224),
            width=3,
        )
        draw.text(
            (120, y + 46),
            f"{index + 1}. {player.name}",
            font=font(38),
            anchor="lm",
            fill=(61, 52, 66),
        )
        draw.text(
            (2040, y + 46),
            f"计分 {len(player.score_cards)} · 角色 {len(player.character_cards)} · 任务 {len(player.mission_ids)}",
            font=font(34),
            anchor="rm",
            fill=(105, 91, 108),
        )
    draw.text(
        (80, detail_y),
        f"当前玩家持牌 · {current.name}",
        font=font(42),
        fill=(89, 75, 92),
    )
    score_y = detail_y + 66
    if current.score_cards:
        for index, card_id in enumerate(current.score_cards):
            text, score = rule_text(state.cards[card_id])
            label = text.replace("\n", " ")
            draw.text(
                (105, score_y),
                f"{index + 1}. {label}  {score}",
                font=font(32),
                fill=(100, 82, 102),
            )
            score_y += DETAIL_LINE_HEIGHT
    else:
        draw.text(
            (105, score_y),
            "暂无计分牌",
            font=font(32),
            fill=(125, 110, 126),
        )
        score_y += DETAIL_LINE_HEIGHT
    counts = Counter(state.cards[card_id].character for card_id in current.character_cards)
    details = "  ".join(
        f"{character.display_name}×{counts.get(character, 0)}"
        for character in Character
    )
    draw.text(
        (1080, score_y + 45),
        f"角色牌：{details}",
        font=font(34),
        anchor="mm",
        fill=(91, 76, 94),
    )
    draw.text(
        (1080, score_y + 115),
        "sl ta A · sl ta A1 B2 · sl fl 2 · sl sk",
        font=font(32),
        anchor="mm",
        fill=(114, 99, 116),
    )
    return image_b64(image)


def render_result(state: GameState) -> str:
    ranked = rank_players(state)
    image = gradient((1200, 420 + len(ranked) * 155), (248, 255, 252), (255, 242, 250))
    draw = ImageDraw.Draw(image)
    draw.text((600, 75), "FINAL LIVE RESULT", font=font(48), anchor="mm", fill=(67, 111, 112))
    for index, item in enumerate(ranked):
        y = 150 + index * 155
        draw.rounded_rectangle((60, y, 1140, y + 125), 20, fill=(255, 255, 255), outline=GOLD, width=2)
        draw.text((95, y + 42), f"#{item.rank}  {item.player.name}", font=font(34), anchor="lm", fill=(62, 52, 67))
        draw.text((1100, y + 42), f"{item.breakdown.total} 分", font=font(38), anchor="rm", fill=(181, 87, 137))
        detail = " + ".join(str(score.points) for score in item.breakdown.card_scores) or "无计分牌"
        draw.text((95, y + 92), f"计分：{detail} · Mission {item.breakdown.mission_points}", font=font(22), anchor="lm", fill=(112, 96, 114))
    return image_b64(image)


def mission_label(kind: str, amount: int) -> str:
    return {
        "same": f"拥有 {amount} 张同角色",
        "different": f"拥有 {amount} 名不同角色",
        "pairs": f"拥有 {amount} 组对子",
        "turn_types": "本回合同时取得两类卡牌",
    }.get(kind, "完成舞台目标")


def paste_card(canvas, card, x, y, width, height):
    resized = card.resize((width, height), Image.Resampling.LANCZOS)
    canvas.alpha_composite(resized, (x, y))


def image_b64(image: Image.Image) -> str:
    flattened = Image.new("RGB", image.size, (255, 255, 255))
    if image.mode == "RGBA":
        flattened.paste(image, mask=image.getchannel("A"))
    else:
        flattened.paste(image.convert("RGB"))
    quality = 92
    data = b""
    while quality >= 40:
        buffer = BytesIO()
        flattened.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()
        if len(data) <= 3 * 1024 * 1024:
            break
        quality -= 2
    return "base64://" + base64.b64encode(data).decode("ascii")
