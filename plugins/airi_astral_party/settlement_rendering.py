import copy
import json
import math
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from utils.cache import get_image

from .profile_rendering import blank, label_image, resize_sprite, text_image


ASSETS = Path(__file__).parent / "assets"
LAYOUTS = {
    name: json.loads((ASSETS / "settlement" / f"{name}.json").read_text("utf8"))
    for name in ("BattleSettlement", "Common", "Common_Internal", "Background")
}
PACKAGES = {value["id"]: name for name, value in LAYOUTS.items()}
CHARACTERS = json.loads((ASSETS / "settlement/characters.json").read_text("utf8"))
DATA = {name: json.loads((ASSETS / 'settlement' / (name + '.json')).read_text('utf8'))
        for name in ('paintings', 'relic', 'achieve', 'map', 'difficulty')}
RESAMPLE = Image.Resampling.LANCZOS
PVE_MODES = frozenset((4, 6, 9, 10, 12))
STATISTICS = (
    ("com_killCount", "击倒次数"),
    ("com_TotalDie", "倒下次数"),
    ("com_TotalDamage", "输出伤害"),
    ("com_TotalInjured", "承受伤害"),
    ("com_TreatmentScore", "治疗评分"),
)


def integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def nodes(key, package="BattleSettlement", state=None, transition=None):
    item = LAYOUTS[package]["items"][key]
    result = copy.deepcopy(item.get("children", []))
    state = state or {}
    pages = []
    for controller in item.get("controllers", []):
        index = state.get(controller["name"], 0)
        choices = controller["pages"]
        pages.append(choices[index][0] if 0 <= index < len(choices) else None)
    for child in result:
        for gear in child.get("gears", []):
            page = pages[gear["controller"]]
            values = gear["values"]
            kind = gear["kind"]
            if kind in (0, 8):
                child["visible"] &= not values["pages"] or page in values["pages"]
                continue
            value = values.get(page, values.get("default"))
            if value is None:
                continue
            if kind == 1:
                child.update(zip(("x", "y"), value))
            elif kind == 2:
                child.update(width=value[0], height=value[1], scale=value[2:])
            elif kind == 3:
                child.update(alpha=value[0], rotation=value[1])
            elif kind == 4:
                child.update(color=value[:4], outlineColor=value[4:])
            elif kind in (6, 7, 9):
                child[{6: "text", 7: "url", 9: "fontSize"}[kind]] = value
    for animation in item.get("transitions", []):
        if animation["name"] != transition:
            continue
        for action in sorted(animation["items"], key=lambda row: row["time"] + row.get("duration", 0)):
            if action["target"] < 0:
                continue
            child = result[action["target"]]
            kind, value = action["kind"], action["value"]
            if kind in (0, 1):
                keys = ("x", "y") if kind == 0 else ("width", "height")
                for index, field in enumerate(keys):
                    if value[index]:
                        child[field] = round(value[index + 2])
            elif kind == 2:
                child["scale"] = value
            elif kind == 3:
                child["pivot"] = [*value[2:], 0]
            elif kind in (4, 5, 6, 8, 14, 15):
                child[{4: "alpha", 5: "rotation", 6: "color", 8: "visible", 14: "text", 15: "url"}[kind]] = value
    return result


def positioned(image, child):
    width, height = image.info.get("logical_size", image.size)
    ox, oy = image.info.get("origin", (0, 0))
    sx, sy = child.get("scale", (1, 1))
    if sx == 0 or sy == 0:
        return blank((1, 1)), (child["x"], child["y"])
    image = image.resize((max(1, round(image.width * abs(sx))), max(1, round(image.height * abs(sy)))), RESAMPLE)
    x, y = child["x"], child["y"]
    px, py, anchor = child.get("pivot") or (0, 0, 0)
    pivot_x, pivot_y = x + (0 if anchor else px * width), y + (0 if anchor else py * height)
    x += -px * width * abs(sx) if anchor else px * width * (1 - abs(sx))
    y += -py * height * abs(sy) if anchor else py * height * (1 - abs(sy))
    x += ox * abs(sx)
    y += oy * abs(sy)
    if sx < 0:
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if sy < 0:
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    alpha = child.get("alpha", 1)
    if alpha < 1:
        image.putalpha(image.getchannel("A").point(lambda value: round(value * max(0, alpha))))
    rotation = child.get("rotation", 0)
    if rotation:
        radians = math.radians(rotation)
        dx, dy = x + image.width / 2 - pivot_x, y + image.height / 2 - pivot_y
        cx = pivot_x + dx * math.cos(radians) - dy * math.sin(radians)
        cy = pivot_y + dx * math.sin(radians) + dy * math.cos(radians)
        image = image.rotate(-rotation, Image.Resampling.BICUBIC, expand=True)
        x, y = cx - image.width / 2, cy - image.height / 2
    return image, (round(x), round(y))


def place(canvas, image, child):
    image, (x, y) = positioned(image, child)
    ox, oy = canvas.info.get("origin", (0, 0))
    canvas.alpha_composite(image, (x - ox, y - oy))


def clip(image, box):
    ox, oy = image.info.get("origin", (0, 0))
    result = image.crop((box[0] - ox, box[1] - oy, box[2] - ox, box[3] - oy))
    result.info.clear()
    return result


def texture(key, package, child):
    item = LAYOUTS[package]["items"][key]
    image = get_image(ASSETS / "settlement" / package / f"{key}.png").copy()
    size = (child.get('width', image.width), child.get('height', image.height))
    if item.get('scaleOption') == 2:
        tiled = blank(size)
        for y in range(0, size[1], image.height):
            for x in range(0, size[0], image.width):
                tiled.alpha_composite(image, (x, y))
        image = tiled
    else:
        image = resize_sprite(image, size, item.get("scale9Grid"))
    if child.get("color"):
        image = ImageChops.multiply(image, Image.new("RGBA", image.size, tuple(child["color"])))
    flip = child.get("flip", 0)
    if flip in (1, 3):
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip in (2, 3):
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return image


def component(key, package="BattleSettlement", state=None, transition=None, images=None, texts=None, hidden=(), changes=None):
    item = LAYOUTS[package]["items"][key]
    width, height = item["width"], item["height"]
    children = nodes(key, package, state, transition)
    images, texts, changes = images or {}, texts or {}, changes or {}
    mask_index = item.get("mask", -1)
    layers, mask_layer = [], None
    for index, child in enumerate(children):
        name = child["name"]
        child.update(changes.get(name, {}))
        if name in hidden or not child["visible"] or child.get("alpha", 1) <= 0:
            continue
        child_package = PACKAGES.get(child.get("package"), package)
        image = images.get(name)
        if image is None:
            kind = child["type"]
            if kind == 0:
                image = texture(child["source"], child_package, child)
            elif kind == 1 and child["source"] + "_0" in LAYOUTS[package]["items"]:
                image = texture(child["source"] + "_0", package, child)
            elif kind == 9:
                if child["source"] not in LAYOUTS[child_package]["items"]:
                    continue
                image = component(child["source"], child_package, state)
            elif kind == 4 and child.get("url", ""):
                url = child["url"]
                target_package = PACKAGES.get(url[5:13])
                if target_package and url[13:] in LAYOUTS[target_package]["items"]:
                    target_key = url[13:]
                    if LAYOUTS[target_package]['items'][target_key].get('type') == 1:
                        target_key += '_0'
                    if target_key in LAYOUTS[target_package]['items']:
                        image = texture(target_key, target_package, child)
            elif kind in (6, 7, 8):
                value = texts.get(name, child.get("text") or "")
                if (child.get('font') or '').endswith('_TMP') and child.get('outline'):
                    child['outline'] = 3
                child["font"] = (child.get("font") or "JingNanBoBoHei").removesuffix("_TMP")
                image = text_image(re.sub(r"\[/?(?:color|size)[^\]]*\]", "", str(value)), child, fit=True)
            elif kind == 3 and child.get("shape") == 1:
                image = blank((child["width"], child["height"]))
                ImageDraw.Draw(image).rounded_rectangle(
                    (0, 0, image.width - 1, image.height - 1),
                    radius=child.get("cornerRadius", [0])[0],
                    fill=tuple(child["color"]),
                    outline=tuple(child["lineColor"]),
                    width=child["lineSize"],
                )
        if image is not None:
            if index == mask_index:
                mask_layer = positioned(image, child)
            else:
                layers.append(positioned(image, child))
    left = min([0] + [xy[0] for image, xy in layers])
    top = min([0] + [xy[1] for image, xy in layers])
    right = max([width] + [xy[0] + image.width for image, xy in layers])
    bottom = max([height] + [xy[1] + image.height for image, xy in layers])
    canvas = blank((right - left, bottom - top))
    for image, (x, y) in layers:
        canvas.alpha_composite(image, (x - left, y - top))
    if mask_layer is not None:
        mask_image = blank(canvas.size)
        image, (x, y) = mask_layer
        mask_image.alpha_composite(image, (x - left, y - top))
        alpha = mask_image.getchannel("A")
        if item.get("reversedMask"):
            alpha = ImageChops.invert(alpha)
        canvas.putalpha(ImageChops.multiply(canvas.getchannel("A"), alpha))
    canvas.info.update(origin=(left, top), logical_size=(width, height))
    return canvas


def caption(value, width, height=38, size=24, color=(255, 255, 255, 255)):
    return text_image(
        value,
        {
            "width": width, "height": height, "font": "JingNanBoBoHei",
            "fontSize": size, "color": color, "align": 1, "verticalAlign": 1,
        },
        fit=True,
    )


def role_image(player):
    row = DATA['paintings'].get(str(integer(player.get('standingPainting')))) if player.get('standingPainting') else CHARACTERS.get(str(integer(player.get("heroId"))))
    child = next(
        child for child in nodes("qees2p", transition="SJ Cut in")
        if child["name"] == "loader_Role"
    )
    loader = blank((child["width"], child["height"]))
    if row:
        image = get_image(ASSETS / row["path"]).copy()
        loader.alpha_composite(image, (round((loader.width - image.width) / 2), 0))
    else:
        loader.alpha_composite(caption("立绘资源未收录", loader.width, 80, 32), (0, 60))
    return component("qees2p", transition="SJ Cut in", images={"loader_Role": loader})


def asset_image(row, size):
    return get_image(ASSETS / row['path']).resize(size, RESAMPLE)


def relic_image(player):
    if 'relics' not in player:
        return caption('遗物记录未提供', 358, 254, 30, (70, 65, 75, 255))
    canvas = blank((358, 254))
    relics = player['relics']
    for index in range(14):
        entry = DATA['relic'].get(str(relics[index])) if index < len(relics) else None
        images = {}
        if entry:
            images['com_Quality'] = component('9wy8bw', 'Common', {'quality': entry['quality']})
            images['loader_Relic'] = asset_image(entry, (72, 72))
        child = nodes('w0q938')[index % 7]
        child['y'] += (index // 7) * 174
        place(canvas, component('w0q934', images=images), child)
    return canvas


def pve_result(player=None):
    player = player or {}
    relic = component(
        "w0q933",
        images={"list_RelicGroup": relic_image(player)},
        changes={
            "n117": {"height": 327},
            "n116": {"height": 285},
            "list_RelicGroup": {"height": 254},
        },
    )
    relic = clip(relic, (0, 0, 430, 315))
    return component(
        "w0q932",
        texts={"txt_GoldCount": player.get('stats', {}).get('totalGold', '—'),
               "txt_TranGoldCount": player.get('stats', {}).get('pveTransferGold', '—')},
        images={"com_Relic": relic},
        changes={
            'n112': {'x': 280, 'y': 39},
            'n116': {'x': 280, 'y': 129},
            'n118': {'x': 309, 'y': 36},
            "txt_GoldCount": {"x": 321, 'y': 67, "width": 73, 'fontSize': 36},
            "txt_TranGoldCount": {"x": 321, 'y': 157, "width": 73, 'fontSize': 36},
        },
    )


def battle_values(player):
    stats = player.get('stats', {})
    keys = {1: 'killCount', 2: 'totalDamage', 4: 'totalDie', 5: 'totalInjured',
            9: 'pvpResultGold', 8: 'pvpResultLv', 10: 'totalGold', 11: 'pveTransferGold',
            3: 'pkDamageMax', 16: 'totalGold', 13: 'treatmentScore', 14: 'movePoint',
            17: 'battleDiceSixCount', 12: 'finalKillBoss'}
    values = {key: integer(stats.get(field)) for key, field in keys.items()}
    values[15], values[7] = -values[14], int(bool(player.get('winner')))
    return values


def achievements(player, players, pvp):
    if 'stats' not in player:
        return []
    values = battle_values(player)
    maxima = {key: max(battle_values(row)[key] for row in players) for key in values}
    eligible = [(key, value) for key, value in values.items()
                if str(key) in DATA['achieve'] and value != 0 and value == maxima[key] and (pvp or key != 7)]
    return sorted(eligible, key=lambda pair: DATA['achieve'][str(pair[0])]['weight'], reverse=True)[:3]


def player_image(player, pvp, players=None):
    players = players or [player]
    slot = max(0, min(3, integer(player.get("slot"))))
    state = {"slot": slot, "step": 2, "IsWinner": 0, "ShowAchievement": 0, "type": 0 if pvp else 1}
    statistic_images = {}
    for (name, label), field in zip(STATISTICS, ('killCount', 'totalDie', 'totalDamage', 'totalInjured', 'treatmentScore')):
        value = player.get('stats', {}).get(field)
        values = [integer(row.get('stats', {}).get(field)) for row in players]
        best = value is not None and value != 0 and value == max(values)
        bar = component('qees2j', state={'type': int(best)},
                        hidden=(() if best else ('n9',)) + (() if value else ('bar',)),
                        changes={'bar': {'width': max(1, min(225, round(225 * integer(value) / max(1, sum(values)))))}})
        statistic_images[name] = component(
            "qees2k", state={'type': int(best)}, transition="Cut in", texts={"title": label, "txt_Count": value if value is not None else '—'},
            images={"slider_Data": bar},
        )
    if pvp:
        stars = blank((118, 43))
        level = integer(player.get("lv"), -1)
        if level < 0:
            stars.alpha_composite(caption("未提供", 118, 43))
        else:
            for index in range(3):
                star = component("imo37v", "Common", {"slot": slot, "avtiveLevel": int(level > index)})
                stars.alpha_composite(star, (index * 39, 0))
        rank = integer(player.get("rank"))
        result = component(
            "w0q931", state={"slot": slot, "rand": rank - 1},
            texts={"txt_GoldCount": player.get("gold", "—")},
            images={"list_Level": stars},
            changes={"txt_GoldCount": {"x": 350, "width": 48}},
        )
        if rank < 1 or rank > 4:
            place(result, caption("名次未提供", 220, 70, 30), {"x": 10, "y": 70})
        statistic_images["com_PVP"] = result
    else:
        statistic_images["com_PVE"] = pve_result(player)
    info = {
        "name": player.get("name") or "未提供昵称",
        "lv": player.get("playerLevel"),
        "headIcon": player.get("headIcon"),
        "background": player.get("background"),
    }
    label, _ = label_image(info)
    badges = {}
    for index, (key, value) in enumerate(achievements(player, players, pvp)):
        badges[f'loader_Achieve_{index + 1}'] = component(
            'w0q930', images={'icon': asset_image(DATA['achieve'][str(key)], (109, 112))},
            texts={'title_Down': abs(value), 'title_Up': abs(value)},
            hidden=('title_Down', 'title_Up') if key == 7 else (),
        )
    image = component(
        "qees2o", state=state, transition="SJ Cut in",
        images={
            "com_Role": role_image(player), "com_PlayerLabel": label,
            "com_BattleData": component("qees2l", state=state, images=statistic_images),
            'com_AchieveBottom': component('qees2n', state=state, transition='Cut in', hidden=('n132',)),
            **badges,
        },
        hidden=(
            'com_Achievement', 'btn_Praise', 'btn_AddFriend',
        ) + tuple(f'loader_Achieve_{index}' for index in range(len(badges) + 1, 4))
          + (() if 'stats' in player else ('com_AchieveBottom',)),
    )
    status = "已放弃对局" if player.get("isGiveUp") else ""
    if not pvp and 'stats' not in player:
        status = f"结余金币：{player.get('gold', '—')}" + (f" · {status}" if status else "")
    if status:
        place(image, caption(status, 380, 42, 24), {"x": 40, "y": 1135})
    return image


def settlement_page(snapshot, mode, time, pvp, notice):
    settlement = snapshot.get('settlement') or {}
    details = sorted(
        [{**row, **settlement.get('players', {}).get(str(row.get('playerId')), {})}
         for row in (snapshot.get('details') or [])[:16]],
        key=lambda row: (
            integer(row.get("slot")), integer(row.get("rank")), str(row.get("playerId", "")),
        ),
    )
    pages = max(1, math.ceil(len(details) / 4))
    canvas = Image.new("RGBA", (1920, 1080 * pages), "#25212e")
    for page in range(pages):
        players = details[page * 4:page * 4 + 4]
        images = {f"com_Player{index + 1}": player_image(player, pvp, details) for index, player in enumerate(players)}
        map_info = DATA['map'].get(str(settlement.get('mapId')))
        footer = component(
            "qees2t", texts={"txt_MapName": f"{map_info['name']}({mode.split(' · ')[0]})" if map_info else mode,
                            "txt_Difficulty": DATA['difficulty'].get(str(settlement.get('difficulty')), '') if not pvp else '',
                            "txt_Round": f"{integer(settlement['round']):02d}" if 'round' in settlement else '—'},
            images={'loader_Map': asset_image(map_info, (305, 84))} if map_info else {},
            hidden=() if map_info else ('loader_Map',),
            changes={"txt_MapName": {"width": 870, 'fontSize': 56, 'y': 10}, 'txt_Round': {'width': 90}},
        )
        if not map_info:
            place(footer, caption(time, 295, 84, 22), {"x": 0, "y": 0})
        place(footer, caption('轮', 42, 45, 32, (255, 0, 132, 255)), {'x': 1432, 'y': 38})
        images["com_Map"] = footer
        hidden = [f"com_Player{index}" for index in range(len(players) + 1, 5)]
        background = get_image(ASSETS / "ui/Common/kn6fq3y.png").resize((1920, 1080), RESAMPLE)
        stripes = texture('g1i49l', 'Common', {'width': 1920, 'height': 1080})
        place(background, stripes, {'x': 0, 'y': 0, 'alpha': 0.2})
        place(background, component("qees2w", transition="ShowTime", images=images, hidden=hidden), {"x": 0, "y": 0})
        if not settlement:
            background.alpha_composite(caption(notice, 1550, 36, 22), (80, 937))
        canvas.alpha_composite(background, (0, page * 1080))
    return canvas


def render_pve_settlement(snapshot, mode, time):
    rank = integer((snapshot.get("selected") or {}).get("rank"))
    result = "协作胜利" if rank == 1 else "协作失败" if rank > 1 else "胜负未提供"
    return settlement_page(
        snapshot, f"{mode} · {result}", time, False,
        "默认立绘；历史皮肤、战斗统计、遗物、地图、回合、累计、转交金币未提供",
    )


def render_pvp_settlement(snapshot, mode, time):
    return settlement_page(
        snapshot, mode, time, True,
        "公开战绩未提供伤害、成就、地图及回合；角色使用默认立绘，历史皮肤未提供",
    )


def render_settlement(snapshot, mode, time):
    mode_id = integer((snapshot.get("selected") or {}).get("mapType"))
    render = render_pve_settlement if mode_id in PVE_MODES else render_pvp_settlement
    return render(snapshot, mode, time)
