from collections.abc import Callable

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from utils.cache import get_font, get_image_copy
from utils.cache import get_cache_budget_bytes, is_balanced, is_disk, is_ram, register_cache
from utils.cache import ByteLRU, value_bytes

from .art_assets import ASSET_DIR, BACK_BASE_PATH, FRONT_BASE_PATH, NAMEPLATE_PATH, TITLE_PATH, chibi_path, portrait_path
from .models import Card, Character, RuleKind


CARD_SIZE = (750, 1050)
CARD_CORNER_RADIUS = 50
CARD_CORNER_SCALE = 4
PORTRAIT_SHADOW_OPACITY = 0.65
GOLD = (205, 171, 96, 255)
PLATE = (255, 252, 244, 238)
DARK = (66, 53, 69, 255)
PINK = (181, 87, 137, 255)
RED = (205, 52, 62, 255)
GREEN = (52, 151, 111, 255)
FONT_PATH = ASSET_DIR / "font.ttf"
_render_cache = ByteLRU(get_cache_budget_bytes("images"), owner="point_salad.cards")
register_cache("point_salad.cards", _render_cache)


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


def character_label(character: Character) -> str:
    return character.short_name


def _cached_image(key, build: Callable[[], Image.Image]) -> Image.Image:
    if is_disk():
        _render_cache.clear()
        return build().copy()
    _render_cache.max_bytes = 0 if is_ram() else get_cache_budget_bytes("images")
    _render_cache.probationary = is_balanced()
    cached = _render_cache.get(key)
    if cached is not None:
        return cached.copy()
    image = build()
    _render_cache.put(key, image, value_bytes(image))
    return image.copy()


def _round_card_corners(image: Image.Image) -> Image.Image:
    width, height = image.size
    scale = CARD_CORNER_SCALE
    mask = Image.new("L", (width * scale, height * scale))
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, width * scale - 1, height * scale - 1),
        radius=CARD_CORNER_RADIUS * scale,
        fill=255,
    )
    mask = mask.resize((width, height), Image.Resampling.LANCZOS)
    image.putalpha(ImageChops.multiply(image.getchannel("A"), mask))
    return image


def _character_source(character: Character) -> Image.Image:
    image = get_image_copy(portrait_path(character)).convert("RGBA")
    image = image.crop((0, 0, image.width, round(image.height * 0.88)))
    alpha = image.getchannel("A")
    feather = Image.new("L", image.size)
    draw = ImageDraw.Draw(feather)
    inset = max(55, image.width // 12)
    draw.rounded_rectangle(
        (inset, -80, image.width - inset, image.height - 65),
        radius=image.width // 3,
        fill=255,
    )
    feather = feather.filter(ImageFilter.GaussianBlur(max(36, image.width // 18)))
    image.putalpha(ImageChops.multiply(alpha, feather))
    return image


def _chibi_source(character: Character) -> Image.Image:
    return get_image_copy(chibi_path(character)).convert("RGBA")


def _build_character_front(character: Character) -> Image.Image:
    image = get_image_copy(FRONT_BASE_PATH).convert("RGBA")
    art = _character_source(character)
    art.thumbnail((650, 840), Image.Resampling.LANCZOS)
    x = (CARD_SIZE[0] - art.width) // 2
    y = max(45, 885 - art.height)
    shadow = Image.new("RGBA", art.size)
    shadow_alpha = art.getchannel("A").filter(ImageFilter.GaussianBlur(14))
    shadow.putalpha(shadow_alpha.point(lambda value: round(value * PORTRAIT_SHADOW_OPACITY)))
    image.alpha_composite(shadow, (x + 10, y + 14))
    image.alpha_composite(art, (x, y))
    nameplate = get_image_copy(NAMEPLATE_PATH).convert("RGBA")
    nameplate.thumbnail((650, 118), Image.Resampling.LANCZOS)
    image.alpha_composite(nameplate, ((CARD_SIZE[0] - nameplate.width) // 2, 890 + (118 - nameplate.height) // 2))
    draw = ImageDraw.Draw(image)
    draw.text((375, 928), character.display_name, font=font(46), anchor="mm", fill=(255, 255, 255), stroke_width=2, stroke_fill=(71, 52, 69))
    draw.text((375, 974), character.value.upper(), font=font(22), anchor="mm", fill=(244, 232, 238), stroke_width=1, stroke_fill=(71, 52, 69))
    return _round_card_corners(image)


def render_character_front(character: Character) -> Image.Image:
    return _cached_image(("character_front", character.value), lambda: _build_character_front(character))


def _build_character_icon(character: Character, size: int) -> Image.Image:
    source = _chibi_source(character)
    bbox = source.getchannel("A").getbbox()
    if bbox is not None:
        source = source.crop(bbox)
    source.thumbnail((size - 14, size - 14), Image.Resampling.LANCZOS)
    icon = Image.new("RGBA", (size, size), CHARACTER_COLORS[character][0] + (255,))
    icon.alpha_composite(source, ((size - source.width) // 2, (size - source.height) // 2))
    mask = Image.new("L", (size, size))
    ImageDraw.Draw(mask).ellipse((3, 3, size - 4, size - 4), fill=255)
    icon.putalpha(mask)
    draw = ImageDraw.Draw(icon)
    draw.ellipse((3, 3, size - 4, size - 4), outline=GOLD, width=max(2, size // 24))
    draw.text((size - 8, size - 10), CHARACTER_INITIALS[character], font=font(max(12, size // 6)), anchor="rs", fill=(50, 42, 55), stroke_width=2, stroke_fill=(255, 255, 255))
    return icon


def render_character_icon(character: Character, size: int = 100) -> Image.Image:
    return _cached_image(("character_icon", character.value, size), lambda: _build_character_icon(character, size))


def _badge(draw: ImageDraw.ImageDraw, center: tuple[int, int], text: str, fill=PINK, width: int = 240) -> None:
    x, y = center
    draw.rounded_rectangle((x - width // 2, y - 58, x + width // 2, y + 58), 32, fill=fill, outline=GOLD, width=4)
    draw.text((x, y), text, font=font(64), anchor="mm", fill=(255, 255, 255), stroke_width=1, stroke_fill=(70, 52, 68))


def _operator(draw: ImageDraw.ImageDraw, position: tuple[int, int], text: str) -> None:
    draw.text(position, text, font=font(64), anchor="mm", fill=DARK)


def _icon(image: Image.Image, character: Character, center: tuple[int, int], size: int) -> None:
    icon = render_character_icon(character, size)
    image.alpha_composite(icon, (center[0] - size // 2, center[1] - size // 2))


def _frame(card: Card) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = get_image_copy(BACK_BASE_PATH).convert("RGBA")
    title = get_image_copy(TITLE_PATH).convert("RGBA")
    title.thumbnail((470, 180), Image.Resampling.LANCZOS)
    image.alpha_composite(title, ((CARD_SIZE[0] - title.width) // 2, 28))
    draw = ImageDraw.Draw(image)
    color = CHARACTER_COLORS[card.character][1] + (245,)
    draw.polygon(((0, 0), (160, 0), (0, 160)), fill=color)
    draw.polygon(((750, 1050), (590, 1050), (750, 890)), fill=color)
    _icon(image, card.character, (58, 58), 90)
    _icon(image, card.character, (692, 992), 90)
    draw.rounded_rectangle((54, 214, 696, 928), 36, fill=PLATE, outline=GOLD, width=5)
    return image, draw


def _comparison(image: Image.Image, draw: ImageDraw.ImageDraw, card: Card) -> None:
    label = "最多" if card.rule.kind is RuleKind.MOST else "最少"
    draw.text((375, 315), label, font=font(80), anchor="mm", fill=DARK)
    _icon(image, card.rule.target, (375, 520), 230)
    _badge(draw, (375, 790), f"+{card.rule.points}")


def _parity(image: Image.Image, draw: ImageDraw.ImageDraw, card: Card) -> None:
    _icon(image, card.rule.target, (190, 490), 195)
    draw.text((485, 345), "偶数", font=font(64), anchor="mm", fill=DARK)
    _badge(draw, (500, 455), f"+{card.rule.points}", width=210)
    draw.text((485, 600), "奇数", font=font(64), anchor="mm", fill=DARK)
    _badge(draw, (500, 710), f"+{card.rule.odd_points}", fill=GREEN, width=210)


def _linear(image: Image.Image, draw: ImageDraw.ImageDraw, card: Card) -> None:
    items = list(card.rule.weights.items())
    start = 540 - (len(items) - 1) * 105
    for index, (character, weight) in enumerate(items):
        y = start + index * 210
        draw.text((180, y), f"{weight:+d}", font=font(78), anchor="mm", fill=RED if weight < 0 else GREEN)
        _operator(draw, (290, y), "×")
        _icon(image, character, (470, y), 180)


def _repeated(image: Image.Image, draw: ImageDraw.ImageDraw, card: Card) -> None:
    count = card.rule.threshold
    if count == 3:
        for center in ((280, 400), (470, 400), (375, 630)):
            _icon(image, card.rule.target, center, 170)
        _operator(draw, (375, 520), "+")
        _operator(draw, (375, 745), "=")
        _badge(draw, (375, 840), f"+{card.rule.points}")
        return
    _icon(image, card.rule.target, (270, 480), 180)
    _operator(draw, (375, 480), "+")
    _icon(image, card.rule.target, (480, 480), 180)
    _operator(draw, (375, 650), "=")
    _badge(draw, (375, 790), f"+{card.rule.points}")


def _set_rule(image: Image.Image, draw: ImageDraw.ImageDraw, card: Card) -> None:
    characters = list(card.rule.requirements)
    if len(characters) == 3:
        for character, center in zip(
            characters,
            ((280, 400), (470, 400), (375, 630)),
        ):
            _icon(image, character, center, 170)
        _operator(draw, (375, 520), "+")
        _operator(draw, (375, 745), "=")
        _badge(draw, (375, 840), f"+{card.rule.points}")
        return
    _icon(image, characters[0], (270, 480), 180)
    _operator(draw, (375, 480), "+")
    _icon(image, characters[1], (480, 480), 180)
    _operator(draw, (375, 650), "=")
    _badge(draw, (375, 790), f"+{card.rule.points}")


def _types_rule(image: Image.Image, draw: ImageDraw.ImageDraw, card: Card) -> None:
    labels = {
        RuleKind.MISSING_TYPES: ("每缺少 1 种角色", "0 张"),
        RuleKind.TYPES_AT_LEAST: ("每种达到数量", f"≥ {card.rule.threshold} 张"),
    }
    title, condition = labels[card.rule.kind]
    draw.text((375, 315), title, font=font(60), anchor="mm", fill=DARK)
    icons = list(Character)
    for index, character in enumerate(icons):
        _icon(image, character, (170 + index % 3 * 205, 465 + index // 3 * 145), 120)
    draw.text((375, 730), condition, font=font(54), anchor="mm", fill=DARK)
    _badge(draw, (375, 840), f"+{card.rule.points}", width=210)


def _total_rule(image: Image.Image, draw: ImageDraw.ImageDraw, card: Card) -> None:
    label = "角色总数最多" if card.rule.kind is RuleKind.MOST_TOTAL else "角色总数最少"
    draw.text((375, 315), label, font=font(66), anchor="mm", fill=DARK)
    for index, character in enumerate(Character):
        _icon(image, character, (125 + index * 100, 520), 100)
    _badge(draw, (375, 780), f"+{card.rule.points}")


def _complete_set(image: Image.Image, draw: ImageDraw.ImageDraw, card: Card) -> None:
    draw.text((375, 300), "每套完整六种角色", font=font(60), anchor="mm", fill=DARK)
    for index, character in enumerate(Character):
        _icon(image, character, (175 + index % 3 * 200, 450 + index // 3 * 160), 130)
    _badge(draw, (375, 835), f"+{card.rule.points}")


def _build_score_back(card: Card) -> Image.Image:
    image, draw = _frame(card)
    handlers = {
        RuleKind.MOST: _comparison,
        RuleKind.FEWEST: _comparison,
        RuleKind.PARITY: _parity,
        RuleKind.LINEAR: _linear,
        RuleKind.SAME_PAIR: _repeated,
        RuleKind.SAME_TRIPLE: _repeated,
        RuleKind.SET: _set_rule,
        RuleKind.MISSING_TYPES: _types_rule,
        RuleKind.TYPES_AT_LEAST: _types_rule,
        RuleKind.FEWEST_TOTAL: _total_rule,
        RuleKind.MOST_TOTAL: _total_rule,
        RuleKind.COMPLETE_SET: _complete_set,
    }
    handlers[card.rule.kind](image, draw, card)
    draw.text((375, 966), f"{card.card_id} · {card.source}", font=font(25), anchor="mm", fill=(117, 98, 119))
    return _round_card_corners(image)


def _score_cache_key(card: Card):
    rule = card.rule
    return (
        "score_back",
        card.card_id,
        card.produce,
        card.source,
        rule.kind.value,
        None if rule.target is None else rule.target.value,
        rule.points,
        rule.odd_points,
        rule.threshold,
        tuple(sorted((character.value, value) for character, value in rule.weights.items())),
        tuple(sorted((character.value, value) for character, value in rule.requirements.items())),
    )


def render_score_back(card: Card) -> Image.Image:
    return _cached_image(_score_cache_key(card), lambda: _build_score_back(card))


def rule_text(card: Card) -> tuple[str, str]:
    rule = card.rule
    target = "" if rule.target is None else character_label(rule.target)
    if rule.kind is RuleKind.MOST:
        return f"{target}最多", f"+{rule.points}"
    if rule.kind is RuleKind.FEWEST:
        return f"{target}最少", f"+{rule.points}"
    if rule.kind is RuleKind.PARITY:
        return f"{target}偶/奇", f"+{rule.points}/+{rule.odd_points}"
    if rule.kind is RuleKind.LINEAR:
        return " ".join(f"{character_label(character)}{value:+d}" for character, value in rule.weights.items()), ""
    if rule.kind in {RuleKind.SAME_PAIR, RuleKind.SAME_TRIPLE}:
        return f"每 {rule.threshold} 个{target}", f"+{rule.points}"
    if rule.kind is RuleKind.SET:
        return "＋".join(character_label(character) for character in rule.requirements), f"+{rule.points}"
    if rule.kind is RuleKind.MISSING_TYPES:
        return "每缺少一种角色", f"+{rule.points}"
    if rule.kind is RuleKind.TYPES_AT_LEAST:
        return f"每种达到{rule.threshold}张", f"+{rule.points}"
    if rule.kind is RuleKind.FEWEST_TOTAL:
        return "角色总数最少", f"+{rule.points}"
    if rule.kind is RuleKind.MOST_TOTAL:
        return "角色总数最多", f"+{rule.points}"
    if rule.kind is RuleKind.COMPLETE_SET:
        return "每套完整六种角色", f"+{rule.points}"
    raise ValueError("未知计分规则")
