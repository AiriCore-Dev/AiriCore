import base64
from collections import Counter
from io import BytesIO

from PIL import Image, ImageDraw, ImageOps

from utils.asset_cache import get_image_copy

from .art_assets import TITLE_PATH, portrait_path
from .card_renderer import character_label, font, render_character_front, render_character_icon, render_score_back
from .missions import mission_catalog
from .models import Character, GameMode, GameState, Phase, PlayerState
from .scoring import rank_players, score_player


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
BOARD_RADIUS = 50
GOLD = (205, 171, 96, 255)
TURN_CHANGE_HEIGHT = 650
TURN_CHANGE_LABEL_Y = 215
TURN_CHANGE_CARD_Y = 280
TURN_CHANGE_SCORE_SIZE = (220, 308)
TURN_CHANGE_CHARACTER_SIZE = 150


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
    height = 2850 if state.phase is not Phase.LOBBY else 1450
    image = gradient((BOARD_WIDTH, height), (246, 255, 252), (255, 244, 251))
    draw = ImageDraw.Draw(image)
    if state.phase is Phase.PLAYING and state.mode is GameMode.MIX and state.players:
        current = state.players[state.current_player]
        if current.center is not None:
            _paste_center_background(image, current.center, SECTION_Y, height - SECTION_Y)
    title = get_image_copy(TITLE_PATH).convert("RGBA")
    title.thumbnail((520, 230), Image.Resampling.LANCZOS)
    image.alpha_composite(title, (80, 45))
    mode = "混合模式" if state.mode is GameMode.MIX else "普通模式"
    speed = "快速局" if state.speed.value == "quick" else "标准局"
    draw.text((2040, 92), f"{speed} · {mode}", font=font(58), anchor="ra", fill=(66, 74, 83))
    if state.phase is Phase.LOBBY:
        draw.text((1080, 720), "游戏未开始", font=font(86), anchor="mm", fill=(104, 91, 108))
        draw.text((1080, 850), f"当前已有 {len(state.players)} 名玩家，等待房主开始", font=font(40), anchor="mm", fill=(125, 110, 126))
        return image_b64(image)
    current = state.players[state.current_player]
    pile_counts = " / ".join(str(len(deck)) for deck in state.decks)
    draw.text((2040, 170), f"第 {state.turn_number} 回合 · 三叠余牌 {pile_counts}", font=font(46), anchor="ra", fill=(104, 91, 108))
    draw.rounded_rectangle((80, 270, 2080, 420), BOARD_RADIUS, fill=(222, 247, 241), outline=(92, 176, 160), width=4)
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
            draw.rounded_rectangle((x, MARKET_SCORE_Y, x + score_width, MARKET_SCORE_Y + score_height), BOARD_RADIUS, outline=(190, 177, 191), width=4)
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
            draw.rounded_rectangle((x, SECTION_Y + 80, x + 920, SECTION_Y + 200), BOARD_RADIUS, fill=(255, 249, 230), outline=(215, 186, 107), width=3)
            draw.text((x + 35, SECTION_Y + 140), mission_label(mission.kind, mission.amount), font=font(36), anchor="lm", fill=(84, 69, 71))
            draw.text((x + 885, SECTION_Y + 140), f"+{mission.points}", font=font(42), anchor="rm", fill=(195, 139, 35))
    return image_b64(image)


def render_board_images(state: GameState, viewer_id: str) -> tuple[str, str]:
    return render_board(state, viewer_id), render_players(state, viewer_id)


def render_players(state: GameState, _viewer_id: str) -> str:
    max_score_cards = max((len(player.score_cards) for player in state.players), default=0)
    row_height = max(640, 175 + ((max_score_cards + 8) // 9) * 235 + 150)
    header = 180
    height = header + max(1, len(state.players)) * row_height + 100
    image = gradient((BOARD_WIDTH, height), (255, 252, 246), (246, 249, 255))
    draw = ImageDraw.Draw(image)
    draw.text((80, 85), "所有玩家的积分与卡组", font=font(58), anchor="lm", fill=(77, 67, 86))
    for index, player in enumerate(state.players):
        y = header + index * row_height
        active = state.phase is Phase.PLAYING and index == state.current_player
        draw.rounded_rectangle((80, y, 2080, y + row_height - 35), BOARD_RADIUS, fill=(231, 249, 246) if active else (255, 255, 255), outline=(226, 210, 224), width=3)
        breakdown = score_player(state, player) if state.cards else None
        total = breakdown.total if breakdown is not None else 0
        draw.text((125, y + 62), f"{index + 1}. {player.name}", font=font(44), anchor="lm", fill=(61, 52, 66))
        draw.text((2030, y + 62), f"预览总分：{total} 分", font=font(40), anchor="rm", fill=(181, 87, 137))
        draw.text((125, y + 125), "计分牌", font=font(30), fill=(112, 96, 114))
        card_x = 125
        if player.score_cards:
            card_width, card_height = 150, 210
            for card_index, card_id in enumerate(player.score_cards):
                x = card_x + (card_index % 9) * 155
                card_y = y + 175 + (card_index // 9) * 235
                card_image = render_score_back(state.cards[card_id]).resize((card_width, card_height), Image.Resampling.LANCZOS)
                image.alpha_composite(card_image, (x, card_y))
                points = breakdown.card_scores[card_index].points if breakdown is not None else 0
                draw.text((x + card_width // 2, card_y + card_height + 20), f"{points:+d}", font=font(27), anchor="mm", fill=(181, 87, 137))
        else:
            draw.text((card_x, y + 250), "暂无计分牌", font=font(30), anchor="lm", fill=(145, 132, 146))
        if state.mode is GameMode.MIX:
            draw.text((2030, y + 125), f"Center：{character_label(player.center) if player.center else '—'} · Mission {player.mission_points} 分", font=font(26), anchor="ra", fill=(112, 96, 114))
        draw.text((1560, y + 170), "角色牌", font=font(30), fill=(112, 96, 114))
        counts = Counter(state.cards[card_id].character for card_id in player.character_cards) if state.cards else Counter()
        visible = [(character, counts.get(character, 0)) for character in Character if counts.get(character, 0)]
        for char_index, (character, count) in enumerate(visible):
            x = 1580 + (char_index % 4) * 125
            icon = render_character_icon(character, 92)
            image.alpha_composite(icon, (x, y + 220 + (char_index // 4) * 130))
            draw.text((x + 46, y + 325 + (char_index // 4) * 130), f"×{count}", font=font(30), anchor="mm", fill=(77, 67, 86))
    return image_b64(image)


def render_turn_change(before: GameState | None, after: GameState) -> str | None:
    if before is None or before.phase is not Phase.PLAYING or after.phase is not Phase.PLAYING:
        return None
    if before.current_player == after.current_player:
        return None
    previous_user_id = after.last_turn_user_id
    if previous_user_id is None:
        return None
    previous = next(
        (player for player in after.players if player.user_id == previous_user_id),
        None,
    )
    if previous is None:
        return None
    current_after = previous
    old_scores = Counter(after.last_turn_score_cards_before)
    new_scores = Counter(current_after.score_cards)
    gained_scores = list((new_scores - old_scores).elements())
    old_chars = Counter(after.last_turn_character_cards_before)
    new_chars = Counter(current_after.character_cards)
    gained_chars = list((new_chars - old_chars).elements())
    image = gradient((2160, TURN_CHANGE_HEIGHT), (255, 250, 240), (250, 241, 250))
    draw = ImageDraw.Draw(image)
    draw.text((80, 70), f"上一轮 {previous.name} 的卡组变化", font=font(48), anchor="lm", fill=(104, 76, 99))
    draw.text((80, 145), "新获得的牌已加入下方卡组；翻面牌会从计分区移到角色区", font=font(28), anchor="lm", fill=(125, 110, 126))
    x = 100
    if gained_scores:
        draw.text((x, TURN_CHANGE_LABEL_Y), "计分牌", font=font(28), fill=(112, 96, 114))
        for card_id in gained_scores[:7]:
            card_image = render_score_back(after.cards[card_id]).resize(TURN_CHANGE_SCORE_SIZE, Image.Resampling.LANCZOS)
            image.alpha_composite(card_image, (x, TURN_CHANGE_CARD_Y))
            x += TURN_CHANGE_SCORE_SIZE[0] + 20
    if gained_chars:
        x = 420 if gained_scores else 100
        draw.text((x, TURN_CHANGE_LABEL_Y), "角色牌", font=font(28), fill=(112, 96, 114))
        for card_id in gained_chars[:7]:
            icon = render_character_icon(after.cards[card_id].character, TURN_CHANGE_CHARACTER_SIZE)
            image.alpha_composite(icon, (x, TURN_CHANGE_CARD_Y))
            x += TURN_CHANGE_CHARACTER_SIZE + 20
    if not gained_scores and not gained_chars:
        draw.text((1080, 280), "本轮没有新增卡牌", font=font(34), anchor="mm", fill=(145, 132, 146))
    return image_b64(image)


def _paste_center_background(image: Image.Image, character: Character, y: int, area_height: int) -> None:
    source = get_image_copy(portrait_path(character)).convert("RGBA")
    source = source.resize((BOARD_WIDTH, round(source.height * BOARD_WIDTH / source.width)), Image.Resampling.LANCZOS)
    source = source.crop((0, 0, BOARD_WIDTH, min(area_height, source.height)))
    source.putalpha(source.getchannel("A").point(lambda value: round(value * 0.2)))
    image.alpha_composite(source, (0, y))
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
        score_total = sum(score.points for score in item.breakdown.card_scores)
        mission = f" · Mission {item.breakdown.mission_points} 分" if state.mode is GameMode.MIX else ""
        detail = f"计分牌 {score_total:+d} 分（{len(item.breakdown.card_scores)} 张）{mission} · 同分按最后行动顺序"
        draw.text((95, y + 92), detail, font=font(22), anchor="lm", fill=(112, 96, 114))
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
