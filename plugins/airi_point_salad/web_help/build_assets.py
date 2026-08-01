from pathlib import Path
import importlib
import math
import sys

import nonebot
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

nonebot.init()

art_assets = importlib.import_module("plugins.airi_point_salad.art_assets")
renderer = importlib.import_module("plugins.airi_point_salad.renderer")
cards_module = importlib.import_module("plugins.airi_point_salad.cards")
models_module = importlib.import_module("plugins.airi_point_salad.models")
skills_module = importlib.import_module("plugins.airi_point_salad.skills")
build_rule = cards_module.build_rule
Card = models_module.Card
Character = models_module.Character
RuleKind = models_module.RuleKind
skill_usage = skills_module.skill_usage


OUTPUT_DIR = Path(__file__).resolve().parent
NAVY = (35, 49, 87)
PINK = (234, 104, 154)
DEEP_PINK = (190, 67, 121)
GOLD = (238, 184, 66)
MINT = (219, 247, 239)
PALE_PINK = (255, 231, 241)
PALE_BLUE = (229, 241, 255)
WHITE = (255, 255, 255)
GRAY = (92, 99, 118)


def font(size):
    return renderer.font(size)


def canvas(size):
    image = renderer.gradient(size, (244, 252, 255), (255, 235, 246))
    draw = ImageDraw.Draw(image)
    draw.ellipse((-180, -220, 520, 480), fill=(231, 249, 243, 150))
    draw.ellipse((size[0] - 460, size[1] - 430, size[0] + 120, size[1] + 150), fill=(255, 219, 235, 155))
    return image


def rounded_box(draw, box, fill=WHITE, outline=NAVY, width=4, radius=28):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, value, size, fill=NAVY, anchor="mm", stroke_width=0):
    draw.text(
        xy,
        value,
        font=font(size),
        fill=fill,
        anchor=anchor,
        stroke_width=stroke_width,
        stroke_fill=WHITE,
    )


def wrap_lines(draw, value, size, max_width):
    face = font(size)
    lines = []
    current = ""
    for character in value:
        candidate = current + character
        bounds = draw.textbbox((0, 0), candidate, font=face)
        if current and bounds[2] - bounds[0] > max_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def paragraph(draw, xy, value, size, max_width, fill=GRAY, spacing=10, anchor="ma"):
    lines = wrap_lines(draw, value, size, max_width)
    draw.multiline_text(
        xy,
        "\n".join(lines),
        font=font(size),
        fill=fill,
        anchor=anchor,
        align="center",
        spacing=spacing,
    )


def paste_contained(target, source, box):
    x1, y1, x2, y2 = box
    image = source.copy().convert("RGBA")
    image.thumbnail((x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
    x = x1 + (x2 - x1 - image.width) // 2
    y = y1 + (y2 - y1 - image.height) // 2
    target.alpha_composite(image, (x, y))
    return x, y, x + image.width, y + image.height


def arrow(draw, start, end, fill=PINK, width=12):
    draw.line((start, end), fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    length = 28
    spread = 0.58
    points = [
        end,
        (
            end[0] - length * math.cos(angle - spread),
            end[1] - length * math.sin(angle - spread),
        ),
        (
            end[0] - length * math.cos(angle + spread),
            end[1] - length * math.sin(angle + spread),
        ),
    ]
    draw.polygon(points, fill=fill)


def page_title(draw, value, subtitle):
    text(draw, (80, 64), value, 62, anchor="lm")
    text(draw, (80, 124), subtitle, 28, fill=GRAY, anchor="lm")
    draw.line((80, 158, 1520, 158), fill=GOLD, width=5)


def card_thumb(image, size):
    result = image.copy().convert("RGBA")
    result.thumbnail(size, Image.Resampling.LANCZOS)
    return result


def chibi(character):
    return Image.open(art_assets.chibi_path(character)).convert("RGBA")


def save(image, name):
    image.convert("RGB").save(OUTPUT_DIR / name, "PNG", optimize=True)


def build_cover():
    image = canvas((1600, 900))
    draw = ImageDraw.Draw(image)
    title_image = Image.open(art_assets.TITLE_PATH).convert("RGBA")
    paste_contained(image, title_image, (410, 30, 1190, 390))
    rounded_box(draw, (390, 330, 1210, 470), fill=(255, 255, 255, 225), outline=GOLD, width=5, radius=38)
    text(draw, (800, 386), "完整玩法指南", 66, fill=DEEP_PINK)
    text(draw, (800, 442), "角色组合 · 翻牌规划 · 多种计分", 30, fill=GRAY)
    positions = (90, 330, 570, 810, 1050, 1290)
    for x, character in zip(positions, Character):
        art = chibi(character)
        paste_contained(image, art, (x, 500, x + 220, 800))
        rounded_box(draw, (x + 18, 790, x + 202, 850), fill=WHITE, outline=renderer.CHARACTER_COLORS[character][0], width=4, radius=22)
        text(draw, (x + 110, 820), character.short_name, 32)
    save(image, "cover.png")


def build_market_guide():
    image = canvas((1800, 1280))
    draw = ImageDraw.Draw(image)
    page_title(draw, "市场坐标怎么读", "每列上方是计分牌，下方两格是角色牌")
    cards = [
        Card(f"guide-{index}", character, build_rule(character, index))
        for index, character in enumerate((Character.MINORI, Character.HARUKA, Character.AIRI))
    ]
    centers = (380, 900, 1420)
    for column, (x, card) in enumerate(zip(centers, cards)):
        letter = "ABC"[column]
        text(draw, (x, 208), f"{letter} 列", 52, fill=DEEP_PINK)
        score = card_thumb(renderer.render_score_back(card), (210, 294))
        image.alpha_composite(score, (x - score.width // 2, 250))
        draw.rounded_rectangle((x - 135, 235, x + 135, 565), radius=28, outline=GOLD, width=9)
        text(draw, (x + 165, 285), letter, 44, fill=DEEP_PINK)
        for row, character in enumerate((list(Character)[column * 2], list(Character)[column * 2 + 1]), 1):
            front = card_thumb(renderer.render_character_front(character), (185, 259))
            y = 600 + (row - 1) * 278
            image.alpha_composite(front, (x - front.width // 2, y))
            draw.ellipse((x - 126, y - 15, x + 126, y + 273), outline=PINK, width=8)
            text(draw, (x + 170, y + 125), f"{letter}{row}", 42, fill=DEEP_PINK)
    rounded_box(draw, (120, 1140, 820, 1240), fill=MINT, outline=(83, 168, 144), radius=26)
    text(draw, (470, 1175), "拿计分牌：,sl ta A", 34)
    text(draw, (470, 1215), "一次选择 A、B 或 C 其中一列", 26, fill=GRAY)
    arrow(draw, (300, 1135), (380, 545), fill=(83, 168, 144), width=10)
    rounded_box(draw, (980, 1140, 1680, 1240), fill=PALE_PINK, outline=PINK, radius=26)
    text(draw, (1330, 1175), "拿角色牌：,sl ta A1 B2", 34)
    text(draw, (1330, 1215), "通常从六个坐标中选择两个不同位置", 26, fill=GRAY)
    arrow(draw, (1160, 1135), (380, 735), width=10)
    arrow(draw, (1490, 1135), (900, 1015), width=10)
    save(image, "market-guide.png")


def build_turn_flow():
    image = canvas((1600, 900))
    draw = ImageDraw.Draw(image)
    page_title(draw, "一个回合的完整流程", "翻牌是可选动作，拿牌是必须动作")
    steps = (
        ("1", "轮到你", "Airi 会发送 @提醒和桌面图", PALE_BLUE),
        ("2", "可选：翻牌", "用 ,sl fl 2 翻一张自己的计分牌", MINT),
        ("3", "必须：拿牌", "拿一张计分牌，或通常拿两张角色牌", PALE_PINK),
        ("4", "补牌并换人", "市场自动补满，下一位玩家开始回合", (255, 246, 214)),
    )
    xs = (55, 445, 835, 1225)
    for x, (number, title, body, fill) in zip(xs, steps):
        rounded_box(draw, (x, 245, x + 320, 600), fill=fill, outline=NAVY, width=4, radius=34)
        draw.ellipse((x + 120, 195, x + 200, 275), fill=PINK, outline=WHITE, width=4)
        text(draw, (x + 160, 235), number, 44, fill=WHITE)
        text(draw, (x + 160, 330), title, 42)
        paragraph(draw, (x + 160, 390), body, 28, 260)
        if x != xs[-1]:
            arrow(draw, (x + 326, 425), (x + 384, 425), width=10)
    front = card_thumb(renderer.render_character_front(Character.MINORI), (150, 210))
    back = card_thumb(
        renderer.render_score_back(Card("turn", Character.MINORI, build_rule(Character.MINORI, 0))),
        (150, 210),
    )
    image.alpha_composite(back, (522, 645))
    image.alpha_composite(front, (712, 645))
    arrow(draw, (680, 750), (705, 750), fill=GOLD, width=10)
    text(draw, (800, 855), "翻转后永久成为角色牌，不能再翻回计分面", 30, fill=GRAY)
    save(image, "turn-flow.png")


def build_scoring_guide():
    image = canvas((1800, 1100))
    draw = ImageDraw.Draw(image)
    page_title(draw, "五类计分牌", "同一张角色牌可以同时参与多张计分牌")
    kinds = list(RuleKind)
    labels = (
        ("每个", "指定角色每有 1 张，就获得牌面分数"),
        ("双人组", "两名指定角色每凑成 1 组就得分"),
        ("三人组", "三名指定角色每凑成 1 组就得分"),
        ("数量比较", "满足 >、< 或 = 时获得一次分数"),
        ("加分与扣分", "两种角色分别加分和扣分，结果可为负"),
    )
    characters = list(Character)
    x_positions = (60, 410, 760, 1110, 1460)
    for index, (kind, (title, body), x) in enumerate(zip(kinds, labels, x_positions)):
        rule = build_rule(characters[index], index)
        if rule.kind is not kind:
            raise ValueError(f"计分牌示例不匹配：{kind.value}")
        card = Card(f"web-{kind.value}", characters[index], rule)
        rendered = card_thumb(renderer.render_score_back(card), (260, 364))
        image.alpha_composite(rendered, (x + 15, 220))
        rounded_box(draw, (x, 620, x + 290, 900), fill=WHITE, outline=PINK if kind is RuleKind.RISK else GOLD, radius=28)
        text(draw, (x + 145, 680), title, 38, fill=DEEP_PINK)
        paragraph(draw, (x + 145, 735), body, 26, 240)
        draw.line((x + 65, 610, x + 225, 610), fill=PINK, width=6)
    rounded_box(draw, (250, 965, 1550, 1050), fill=(255, 255, 255, 225), outline=NAVY, radius=26)
    text(draw, (900, 1008), "结算时逐张计算计分牌，再加上混合模式的 Live Mission 分数", 34)
    save(image, "scoring-guide.png")


def build_center_skills():
    image = canvas((1800, 1300))
    draw = ImageDraw.Draw(image)
    page_title(draw, "六名 Center 技能", "仅混合模式开放；每局只能成功使用一次")
    summaries = {
        Character.MINORI: "先拿两张角色牌，再把其中一张与市场交换",
        Character.HARUKA: "刷新指定市场列，不结束当前回合",
        Character.AIRI: "拿同列计分牌和角色牌，本回合不能翻牌",
        Character.SHIZUKU: "额外翻一张自己的计分牌",
        Character.MIKU: "让指定计分牌额外视为拥有一张角色",
        Character.RIN: "直接取得三名不同角色并结束回合",
    }
    positions = ((70, 210), (630, 210), (1190, 210), (70, 740), (630, 740), (1190, 740))
    for (x, y), character in zip(positions, Character):
        color = renderer.CHARACTER_COLORS[character][0]
        rounded_box(draw, (x, y, x + 540, y + 470), fill=(255, 255, 255, 230), outline=color, width=6, radius=34)
        art = chibi(character)
        paste_contained(image, art, (x + 18, y + 25, x + 240, y + 290))
        text(draw, (x + 375, y + 82), character.short_name, 48, fill=NAVY)
        paragraph(draw, (x + 375, y + 145), summaries[character], 27, 270)
        rounded_box(draw, (x + 40, y + 330, x + 500, y + 425), fill=PALE_BLUE, outline=color, width=3, radius=22)
        paragraph(draw, (x + 270, y + 354), skill_usage(character), 25, 420, fill=NAVY)
    save(image, "center-skills.png")


def build_mixed_mode():
    image = canvas((1600, 900))
    draw = ImageDraw.Draw(image)
    page_title(draw, "混合模式多了什么", "基础玩法不变，在其上加入 Center 与公开 Live Mission")
    sources = (
        ((85, 250, 475, 510), "基础选牌计分", "拿牌、翻牌与五类计分规则", PALE_BLUE),
        ((85, 585, 475, 845), "Center 技能", "每名玩家获得不重复 Center，每局一次", PALE_PINK),
        ((1125, 250, 1515, 510), "公开 Live Mission", "桌面最多公开两项，每回合最多领取一项", MINT),
    )
    for box, title, body, fill in sources:
        rounded_box(draw, box, fill=fill, outline=NAVY, radius=34)
        text(draw, ((box[0] + box[2]) // 2, box[1] + 72), title, 40)
        paragraph(draw, ((box[0] + box[2]) // 2, box[1] + 135), body, 28, box[2] - box[0] - 60)
    rounded_box(draw, (610, 355, 990, 690), fill=(255, 255, 255, 238), outline=GOLD, width=8, radius=48)
    title_image = Image.open(art_assets.TITLE_PATH).convert("RGBA")
    paste_contained(image, title_image, (665, 380, 935, 530))
    text(draw, (800, 575), "混合模式总分", 46, fill=DEEP_PINK)
    text(draw, (800, 635), "计分牌 + Mission", 32, fill=GRAY)
    arrow(draw, (475, 380), (600, 470), fill=(83, 145, 201), width=12)
    arrow(draw, (475, 710), (600, 610), width=12)
    arrow(draw, (1125, 380), (1000, 470), fill=(83, 168, 144), width=12)
    for index, character in enumerate((Character.MINORI, Character.HARUKA, Character.AIRI)):
        art = chibi(character)
        paste_contained(image, art, (1030 + index * 145, 575, 1160 + index * 145, 790))
    save(image, "mixed-mode.png")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    build_cover()
    build_market_guide()
    build_turn_flow()
    build_scoring_guide()
    build_center_skills()
    build_mixed_mode()


if __name__ == "__main__":
    main()
