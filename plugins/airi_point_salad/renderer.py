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
    title.thumbnail((430, 190), Image.Resampling.LANCZOS)
    image.alpha_composite(title, ((CARD_SIZE[0] - title.width) // 2, 48))
    draw = ImageDraw.Draw(image)
    icons = [render_character_icon(character, 130) for character in card.rule.characters]
    total_width = len(icons) * 130 + max(0, len(icons) - 1) * 12
    icon_x = (750 - total_width) // 2
    for icon in icons:
        image.alpha_composite(icon, (icon_x, 325))
        icon_x += 142
    text, score = rule_text(card)
    draw.multiline_text((375, 570), text, font=font(44), anchor="mm", align="center", fill=(65, 51, 68), spacing=14)
    draw.text((375, 735), score, font=font(76), anchor="mm", fill=(181, 87, 137))
    draw.text((375, 950), card.card_id.upper(), font=font(20), anchor="mm", fill=(117, 98, 119))
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
        return f"{names[0]} {rule.relation} {names[1]}", f"+{rule.points}"
    return f"每个 {names[0]} ＋{rule.points}\n每个 {names[1]} {rule.penalty}", "风险牌"


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
    width = 1350
    base_height = 1920 if state.mode is GameMode.MIX else 1720
    current = state.players[state.current_player]
    player_start = 1355 if state.mode is GameMode.MIX else 1190
    detail_y = player_start + len(state.players) * 78 + 30
    height = max(
        base_height,
        detail_y + len(current.score_cards) * 34 + 190,
    )
    image = gradient((width, height), (246, 255, 252), (255, 244, 251))
    draw = ImageDraw.Draw(image)
    title = get_image_copy(TITLE_PATH).convert("RGBA")
    title.thumbnail((340, 150), Image.Resampling.LANCZOS)
    image.alpha_composite(title, (55, 35))
    mode = "混合模式" if state.mode is GameMode.MIX else "主题原版"
    speed = "快速局" if state.speed.value == "quick" else "标准局"
    draw.text((1280, 65), f"{speed} · {mode}", font=font(38), anchor="ra", fill=(66, 74, 83))
    draw.text((1280, 118), f"第 {state.turn_number} 回合 · 牌库 {len(state.deck)}", font=font(30), anchor="ra", fill=(104, 91, 108))
    draw.rounded_rectangle((55, 190, 1295, 275), 20, fill=(222, 247, 241), outline=(92, 176, 160), width=3)
    draw.text((85, 232), f"当前回合：{current.name}", font=font(34), anchor="lm", fill=(50, 120, 108))
    if current.center is not None:
        status = center_status(state, current)
        draw.text((1260, 232), f"Center：{current.center.display_name} · {status}", font=font(23), anchor="rm", fill=(73, 112, 122))
    card_width = 250
    card_height = 350
    market_y = 350
    for column in range(3):
        x = 145 + column * 405
        draw.text((x + card_width // 2, 315), chr(ord("A") + column), font=font(40), anchor="mm", fill=(95, 74, 97))
        score_id = state.score_market[column]
        if score_id:
            paste_card(image, render_score_back(state.cards[score_id]), x, market_y, card_width, card_height)
        for row in range(2):
            card_id = state.character_market[column][row]
            y = market_y + card_height + 24 + row * 195
            if card_id:
                paste_card(image, render_character_front(state.cards[card_id].character), x + 55, y, 140, 196)
                draw.text((x + 210, y + 98), f"{chr(65 + column)}{row + 1}", font=font(28), anchor="lm", fill=(71, 62, 76))
    cursor_y = 1135
    if state.mode is GameMode.MIX:
        catalog = mission_catalog()
        draw.text((55, cursor_y), "LIVE MISSION", font=font(34), fill=(171, 118, 37))
        for index, mission_id in enumerate(state.active_missions):
            mission = catalog[mission_id]
            x = 55 + index * 625
            draw.rounded_rectangle((x, cursor_y + 55, x + 585, cursor_y + 125), 16, fill=(255, 249, 230), outline=(215, 186, 107), width=2)
            draw.text((x + 20, cursor_y + 90), mission_label(mission.kind, mission.amount), font=font(25), anchor="lm", fill=(84, 69, 71))
            draw.text((x + 560, cursor_y + 90), f"+{mission.points}", font=font(30), anchor="rm", fill=(195, 139, 35))
        cursor_y += 165
    draw.text((55, cursor_y), "PLAYERS", font=font(34), fill=(89, 75, 92))
    cursor_y += 55
    for index, player in enumerate(state.players):
        y = cursor_y + index * 78
        active = index == state.current_player
        fill = (231, 249, 246) if active else (255, 255, 255)
        draw.rounded_rectangle((55, y, 1295, y + 62), 14, fill=fill, outline=(226, 210, 224), width=2)
        draw.text((80, y + 31), f"{index + 1}. {player.name}", font=font(25), anchor="lm", fill=(61, 52, 66))
        draw.text((1265, y + 31), f"计分 {len(player.score_cards)} · 角色 {len(player.character_cards)} · 任务 {len(player.mission_ids)}", font=font(23), anchor="rm", fill=(105, 91, 108))
    draw.text((55, detail_y), f"当前玩家持牌 · {current.name}", font=font(28), fill=(89, 75, 92))
    score_y = detail_y + 46
    if current.score_cards:
        for index, card_id in enumerate(current.score_cards):
            text, score = rule_text(state.cards[card_id])
            label = text.replace("\n", " ")
            draw.text((70, score_y), f"{index + 1}. {label}  {score}", font=font(22), fill=(100, 82, 102))
            score_y += 34
    else:
        draw.text((70, score_y), "暂无计分牌", font=font(22), fill=(125, 110, 126))
        score_y += 34
    counts = Counter(state.cards[card_id].character for card_id in current.character_cards)
    details = "  ".join(f"{character.display_name}×{counts.get(character, 0)}" for character in Character)
    draw.text((675, score_y + 28), f"角色牌：{details}", font=font(23), anchor="mm", fill=(91, 76, 94))
    draw.text((675, score_y + 82), "sl ta A · sl ta A1 B2 · sl fl 2 · sl sk", font=font(22), anchor="mm", fill=(114, 99, 116))
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
    while quality >= 82:
        buffer = BytesIO()
        flattened.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()
        if len(data) <= 3 * 1024 * 1024:
            break
        quality -= 2
    return "base64://" + base64.b64encode(data).decode("ascii")
