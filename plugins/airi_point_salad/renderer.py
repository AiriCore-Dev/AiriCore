import base64
from collections import Counter
from io import BytesIO

from PIL import Image, ImageDraw, ImageOps

from utils.asset_cache import get_image_copy

from .art_assets import TITLE_PATH
from .card_renderer import character_label, font, render_character_front, render_score_back, rule_text
from .missions import mission_catalog
from .models import Character, GameMode, GameState, PlayerState
from .scoring import rank_players


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
GOLD = (205, 171, 96, 255)


def gradient(size, top, bottom):
    layer = Image.linear_gradient("L").resize(size)
    return ImageOps.colorize(layer, top, bottom).convert("RGBA")


def center_status(state: GameState, player: PlayerState) -> str:
    if player.skill_used:
        return "已使用"
    if state.pending_skill.get("user_id") == player.user_id:
        return {
            "airi_armed": "已准备：,sl ta A A1",
            "minori_armed": "已准备：先 ,sl ta A1 B2",
            "minori_swap": "待交换：,sl sk A1 C2",
        }.get(state.pending_skill.get("kind"), "待完成")
    return "可使用"


def render_board(state: GameState, _viewer_id: str) -> str:
    current = state.players[state.current_player]
    mission_height = 280 if state.mode is GameMode.MIX else 0
    player_header_y = SECTION_Y + mission_height
    player_rows_y = player_header_y + 80
    detail_y = player_rows_y + len(state.players) * PLAYER_ROW_HEIGHT + 80
    detail_lines = max(1, len(current.score_cards))
    height = max(3100 if state.mode is GameMode.MIX else 2800, detail_y + detail_lines * DETAIL_LINE_HEIGHT + 230)
    image = gradient((BOARD_WIDTH, height), (246, 255, 252), (255, 244, 251))
    draw = ImageDraw.Draw(image)
    title = get_image_copy(TITLE_PATH).convert("RGBA")
    title.thumbnail((520, 230), Image.Resampling.LANCZOS)
    image.alpha_composite(title, (80, 45))
    mode = "混合模式" if state.mode is GameMode.MIX else "普通模式"
    speed = "快速局" if state.speed.value == "quick" else "标准局"
    draw.text((2040, 92), f"{speed} · {mode}", font=font(58), anchor="ra", fill=(66, 74, 83))
    pile_counts = " / ".join(str(len(deck)) for deck in state.decks)
    draw.text((2040, 170), f"第 {state.turn_number} 回合 · 三叠余牌 {pile_counts}", font=font(46), anchor="ra", fill=(104, 91, 108))
    draw.rounded_rectangle((80, 270, 2080, 420), 30, fill=(222, 247, 241), outline=(92, 176, 160), width=4)
    draw.text((125, 325), f"当前回合：{current.name}", font=font(52), anchor="lm", fill=(50, 120, 108))
    if state.post_flip_available and state.post_flip_user_id:
        previous = next((player.name for player in state.players if player.user_id == state.post_flip_user_id), state.post_flip_user_id)
        draw.text((125, 385), f"{previous} 仍可用 ,sl fl 编号完成行动后翻牌", font=font(30), anchor="lm", fill=(165, 91, 119))
    else:
        draw.text((125, 385), "本回合可在主行动前翻一张计分牌", font=font(30), anchor="lm", fill=(91, 110, 116))
    if current.center is not None:
        draw.text((2030, 335), f"Center：{character_label(current.center)} · {center_status(state, current)}", font=font(36), anchor="rm", fill=(73, 112, 122))
    score_width, score_height = MARKET_SCORE_SIZE
    character_width, character_height = MARKET_CHARACTER_SIZE
    for column in range(3):
        x = MARKET_X[column]
        draw.text((x + score_width // 2, 470), f"{chr(ord('A') + column)} · 余 {len(state.decks[column])}", font=font(48), anchor="mm", fill=(95, 74, 97))
        if state.decks[column]:
            score_id = state.decks[column][-1]
            paste_card(image, render_score_back(state.cards[score_id]), x, MARKET_SCORE_Y, score_width, score_height)
        else:
            draw.rounded_rectangle((x, MARKET_SCORE_Y, x + score_width, MARKET_SCORE_Y + score_height), 24, outline=(190, 177, 191), width=4)
            draw.text((x + score_width // 2, MARKET_SCORE_Y + score_height // 2), "空牌堆", font=font(40), anchor="mm", fill=(145, 132, 146))
        for row in range(2):
            card_id = state.character_market[column][row]
            y = MARKET_CHARACTER_Y + row * MARKET_CHARACTER_STEP
            coordinate = f"{chr(65 + column)}{row + 1}"
            if card_id:
                character_x = x + (score_width - character_width) // 2
                paste_card(image, render_character_front(state.cards[card_id].character), character_x, y, character_width, character_height)
                draw.text((x + 365, y + character_height // 2), coordinate, font=font(42), anchor="lm", fill=(71, 62, 76))
            else:
                draw.text((x + score_width // 2, y + character_height // 2), f"{coordinate} · 空", font=font(34), anchor="mm", fill=(145, 132, 146))
    if state.mode is GameMode.MIX:
        catalog = mission_catalog()
        draw.text((80, SECTION_Y), "LIVE MISSION", font=font(48), fill=(171, 118, 37))
        for index, mission_id in enumerate(state.active_missions):
            mission = catalog[mission_id]
            x = 80 + index * 1000
            draw.rounded_rectangle((x, SECTION_Y + 80, x + 920, SECTION_Y + 200), 24, fill=(255, 249, 230), outline=(215, 186, 107), width=3)
            draw.text((x + 35, SECTION_Y + 140), mission_label(mission.kind, mission.amount), font=font(36), anchor="lm", fill=(84, 69, 71))
            draw.text((x + 885, SECTION_Y + 140), f"+{mission.points}", font=font(42), anchor="rm", fill=(195, 139, 35))
    draw.text((80, player_header_y), "PLAYERS", font=font(48), fill=(89, 75, 92))
    for index, player in enumerate(state.players):
        y = player_rows_y + index * PLAYER_ROW_HEIGHT
        active = index == state.current_player
        draw.rounded_rectangle((80, y, 2080, y + 92), 20, fill=(231, 249, 246) if active else (255, 255, 255), outline=(226, 210, 224), width=3)
        draw.text((120, y + 46), f"{index + 1}. {player.name}", font=font(38), anchor="lm", fill=(61, 52, 66))
        mission = f" · 任务 {len(player.mission_ids)}" if state.mode is GameMode.MIX else ""
        draw.text((2040, y + 46), f"计分 {len(player.score_cards)} · 角色 {len(player.character_cards)}{mission}", font=font(34), anchor="rm", fill=(105, 91, 108))
    draw.text((80, detail_y), f"当前玩家持牌 · {current.name}", font=font(42), fill=(89, 75, 92))
    score_y = detail_y + 66
    if current.score_cards:
        for index, card_id in enumerate(current.score_cards):
            text, score = rule_text(state.cards[card_id])
            draw.text((105, score_y), f"{index + 1}. {text.replace(chr(10), ' ')}  {score}", font=font(32), fill=(100, 82, 102))
            score_y += DETAIL_LINE_HEIGHT
    else:
        draw.text((105, score_y), "暂无计分牌", font=font(32), fill=(125, 110, 126))
        score_y += DETAIL_LINE_HEIGHT
    counts = Counter(state.cards[card_id].character for card_id in current.character_cards)
    details = "  ".join(f"{character_label(character)}×{counts.get(character, 0)}" for character in Character)
    draw.text((1080, score_y + 45), f"角色牌：{details}", font=font(34), anchor="mm", fill=(91, 76, 94))
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
        mission = f" · Mission {item.breakdown.mission_points}" if state.mode is GameMode.MIX else ""
        draw.text((95, y + 92), f"计分：{detail}{mission} · 同分按最后行动顺序", font=font(22), anchor="lm", fill=(112, 96, 114))
    return image_b64(image)


def mission_label(kind: str, amount: int) -> str:
    return {
        "same": f"拥有 {amount} 张同角色",
        "different": f"拥有 {amount} 名不同角色",
        "pairs": f"拥有 {amount} 组对子",
        "turn_types": "本回合同时取得两类卡牌",
    }.get(kind, "完成舞台目标")


def paste_card(canvas, card, x, y, width, height):
    canvas.alpha_composite(card.resize((width, height), Image.Resampling.LANCZOS), (x, y))


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
