from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from plugins.airi_point_salad.card_renderer import font, render_character_front, render_score_back
from plugins.airi_point_salad.cards import load_catalog
from plugins.airi_point_salad.game import create_game, start_game
from plugins.airi_point_salad.models import Character, GameMode, GameSpeed, PlayerState, RuleKind


ROOT = Path(__file__).resolve().parent
SIZE = (1600, 900)
INK = (65, 56, 70)
MUTED = (112, 99, 116)
PINK = (227, 127, 174)
MINT = (124, 201, 179)
BLUE = (129, 184, 220)
GOLD = (215, 178, 91)


def canvas(title, subtitle):
    layer = Image.linear_gradient("L").resize(SIZE)
    image = ImageOps.colorize(layer, (247, 255, 252), (255, 240, 249)).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.text((800, 70), title, font=font(56), anchor="mm", fill=INK)
    draw.text((800, 130), subtitle, font=font(28), anchor="mm", fill=MUTED)
    return image, draw


def card(image, source, center, height=560):
    width = round(height * 750 / 1050)
    resized = source.resize((width, height), Image.Resampling.LANCZOS)
    image.alpha_composite(resized, (center[0] - width // 2, center[1] - height // 2))


def save(image, name):
    image.convert("RGB").save(ROOT / name, "PNG", optimize=True)


def example(kind):
    return next(item for item in load_catalog() if item.rule.kind is kind)


def build_cover():
    image, draw = canvas("MORE MORE JUMP！得分沙拉", "官方 108 张卡牌 · 群聊 2–6 人")
    card(image, render_character_front(Character.MINORI), (285, 520), 520)
    card(image, render_score_back(example(RuleKind.LINEAR)), (800, 500), 620)
    card(image, render_character_front(Character.HARUKA), (1315, 520), 520)
    draw.rounded_rectangle((470, 790, 1130, 855), 28, fill=(255, 255, 255, 230), outline=GOLD, width=3)
    draw.text((800, 822), "普通模式遵循官方规则 · 混合模式叠加扩展", font=font(28), anchor="mm", fill=INK)
    save(image, "cover.png")


def build_market():
    state = create_game("guide", "a", "A", GameSpeed.QUICK, GameMode.CLASSIC, 731, 0)
    state.players.extend((PlayerState("b", "B"), PlayerState("c", "C")))
    start_game(state, "a", 1)
    image, draw = canvas("三叠独立牌库", "顶部计分牌与下方角色牌都属于同一列")
    for column in range(3):
        x = 300 + column * 500
        draw.text((x, 205), f"{chr(65 + column)} 列 · 余 {len(state.decks[column])}", font=font(34), anchor="mm", fill=INK)
        card(image, render_score_back(state.cards[state.decks[column][-1]]), (x, 420), 390)
        for row in range(2):
            item = state.character_market[column][row]
            card(image, render_character_front(state.cards[item].character), (x - 105 + row * 210, 720), 270)
            draw.text((x - 105 + row * 210, 860), f"{chr(65 + column)}{row + 1}", font=font(28), anchor="mm", fill=INK)
        draw.line((x, 585, x, 615), fill=PINK, width=8)
        draw.polygon(((x - 10, 610), (x + 10, 610), (x, 626)), fill=PINK)
    save(image, "market-guide.png")


def build_turn_flow():
    image, draw = canvas("一个回合的完整流程", "前置与后置翻面合计最多一次")
    items = (
        ("可选", "行动前翻面", MINT),
        ("必须", "拿计分牌\n或两张角色牌", BLUE),
        ("自动", "同列补牌\n必要时拆分空堆", GOLD),
        ("可选", "行动后翻面\n可翻刚取得的牌", PINK),
        ("换人", "下一名首次有效行动\n关闭上一窗口", MINT),
    )
    for index, (tag, text, color) in enumerate(items):
        x = 55 + index * 310
        draw.rounded_rectangle((x, 300, x + 250, 650), 34, fill=(255, 255, 255, 235), outline=color, width=6)
        draw.rounded_rectangle((x + 55, 330, x + 195, 385), 24, fill=color)
        draw.text((x + 125, 357), tag, font=font(25), anchor="mm", fill=(255, 255, 255))
        draw.multiline_text((x + 125, 490), text, font=font(31), anchor="mm", align="center", spacing=14, fill=INK)
        if index < len(items) - 1:
            draw.line((x + 255, 475, x + 300, 475), fill=MUTED, width=6)
            draw.polygon(((x + 292, 463), (x + 310, 475), (x + 292, 487)), fill=MUTED)
    save(image, "turn-flow.png")


def build_scoring():
    image, draw = canvas("基础组合计分", "图标、系数、加号与分值按官方信息关系排列")
    kinds = (RuleKind.LINEAR, RuleKind.SAME_PAIR, RuleKind.SAME_TRIPLE, RuleKind.SET)
    for index, kind in enumerate(kinds):
        x = 220 + index * 387
        card(image, render_score_back(example(kind)), (x, 500), 520)
    draw.text((800, 840), "线性加减 · 两张一组 · 三张一组 · 指定组合", font=font(31), anchor="mm", fill=INK)
    save(image, "scoring-guide.png")


def build_special():
    image, draw = canvas("比较与特殊计分", "比较并列者都得分 · 0 张在奇偶中视为偶数")
    kinds = (RuleKind.MOST, RuleKind.PARITY, RuleKind.TYPES_AT_LEAST, RuleKind.MOST_TOTAL, RuleKind.COMPLETE_SET)
    for index, kind in enumerate(kinds):
        x = 180 + index * 310
        card(image, render_score_back(example(kind)), (x, 495), 420)
    draw.text((800, 830), "最多/最少 · 奇偶 · 缺少种类/达到数量 · 总数比较 · 完整六种套组", font=font(29), anchor="mm", fill=INK)
    save(image, "scoring-special.png")


def build_mixed():
    image, draw = canvas("普通模式与混合模式", "混合模式只在官方基础引擎上增加扩展")
    draw.rounded_rectangle((120, 260, 1480, 690), 48, fill=(255, 255, 255, 235), outline=BLUE, width=7)
    draw.text((800, 340), "官方基础规则", font=font(50), anchor="mm", fill=INK)
    draw.text((800, 420), "三叠牌库 · 官方拿牌与翻面 · 十二类计分 · 行动顺序同分判定", font=font(30), anchor="mm", fill=MUTED)
    draw.rounded_rectangle((230, 510, 720, 635), 36, fill=(249, 225, 239), outline=PINK, width=5)
    draw.rounded_rectangle((880, 510, 1370, 635), 36, fill=(225, 247, 239), outline=MINT, width=5)
    draw.text((475, 573), "Center · 每局一次", font=font(34), anchor="mm", fill=INK)
    draw.text((1125, 573), "Live Mission · 公开任务", font=font(34), anchor="mm", fill=INK)
    draw.text((800, 770), "普通模式 = 基础框 · 混合模式 = 基础框 + 两项扩展", font=font(32), anchor="mm", fill=INK)
    save(image, "mixed-mode.png")


def build_centers():
    image, draw = canvas("六名 Center 技能", "仅混合模式开放 · 每位玩家每局成功使用一次")
    labels = (
        (Character.MINORI, "交换本回合取得的\n一张角色牌"),
        (Character.HARUKA, "刷新一列并放回\n同列牌堆底部"),
        (Character.AIRI, "同列取得计分牌与角色牌\n本回合不能翻牌"),
        (Character.SHIZUKU, "额外翻面一张\n自己的计分牌"),
        (Character.MIKU, "指定计分牌结算时\n单独多一张指定角色"),
        (Character.RIN, "取得三张不同角色牌\n并结束回合"),
    )
    for index, (character, label) in enumerate(labels):
        column = index % 3
        row = index // 3
        x = 80 + column * 510
        y = 220 + row * 300
        draw.rounded_rectangle((x, y, x + 470, y + 245), 34, fill=(255, 255, 255, 235), outline=(PINK, BLUE, MINT)[column], width=5)
        portrait = render_character_front(character).resize((130, 182), Image.Resampling.LANCZOS)
        image.alpha_composite(portrait, (x + 24, y + 28))
        name = "Airi" if character is Character.AIRI else character.short_name
        draw.text((x + 180, y + 70), name, font=font(38), anchor="lm", fill=INK)
        draw.multiline_text((x + 180, y + 145), label, font=font(23), anchor="lm", fill=MUTED, spacing=10)
    save(image, "center-skills.png")


def main():
    build_cover()
    build_market()
    build_turn_flow()
    build_scoring()
    build_special()
    build_mixed()
    build_centers()


if __name__ == "__main__":
    main()
