import random
from pathlib import Path
from typing import Dict, List, Tuple, Union

import nonebot
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import (GroupMessageEvent, MessageEvent,
                                               PrivateMessageEvent)
from nonebot.matcher import Matcher

from . import cache
from .config import EventNotSupport, ResourceError, tarot_config

try:
    import ujson as json
except ModuleNotFoundError:
    import json


def chain_reply(bot: Bot,
                chain: List[Dict[str, Union[str, Dict[str, Union[str, MessageSegment]]]]],
                msg: MessageSegment
                ) -> List[Dict[str, Union[str, Dict[str, Union[str, MessageSegment]]]]]:
    data = {
        "type": "node",
        "data": {
            "name": "Momoi Airi",
            "uin": bot.self_id,
            "content": msg
        },
    }
    chain.append(data)
    return chain


def pick_theme() -> str:
    return "BilibiliTarot"

def pick_sub_types(theme: str) -> List[str]:
    all_sub_types: List[str] = ["MajorArcana",
                                "Cups", "Pentacles", "Swords", "Wands"]

    if theme == "TouhouTarot":
        return ["MajorArcana"]

    return all_sub_types


class Tarot:
    def __init__(self):
        self.tarot_json: Path = Path(__file__).resolve().parent / "tarot.json"

    async def divine(self, bot: Bot, matcher: Matcher, event: MessageEvent, f_name) -> None:
        session_id = str(event.get_session_id())
        if 'group' in session_id:
            split_id = session_id.split('_')
            user_id = split_id[2]
            gruop_id = split_id[1]
        else:
            user_id = session_id
            gruop_id = None
        user_nick = await bot.get_group_member_info(group_id=gruop_id, user_id=user_id)
        user_nick = (user_nick.get("card") or user_nick.get("nickname") or user_id)

        theme: str = pick_theme()

        with open(self.tarot_json, 'r', encoding='utf-8') as f:
            content = json.load(f)
            all_cards = content.get("cards")
            all_formations = content.get("formations")
            formation_name = f_name
            if formation_name[-2:] != '牌阵': formation_name += '牌阵'
            if formation_name not in list(all_formations):
                msgs = f'没有找到{formation_name}！\n可用的牌阵：'
                for i in list(all_formations):
                    msgs += f'{i}, '
                msgs = msgs[:-2]
                await matcher.finish(msgs, reply_message = True)
            formation = all_formations.get(formation_name)
        cards_num: int = formation.get("cards_num")
        cards_info_list = self._random_cards(all_cards, theme, cards_num)

        is_cut: bool = formation.get("is_cut")
        representations: List[Union[str, List[str]]] = random.choice(
            formation.get("representations"))

        chain = []
        chain = chain_reply(bot, chain, MessageSegment.text(f"{user_nick}的{formation_name}"))
        for i in range(cards_num):
            if is_cut and i == cards_num - 1:
                if formation_name == '无牌阵': msg_header = MessageSegment.text(f"切牌\n")
                else: msg_header = MessageSegment.text(f"切牌「{representations[i]}」\n")
            else:
                if formation_name == '无牌阵': msg_header = MessageSegment.text(f"第{i+1}张牌\n")
                else: msg_header = MessageSegment.text(f"第{i+1}张牌「{representations[i]}」\n")

            flag, msg_body = await self._get_text_and_image(theme, cards_info_list[i], 1)
            if not flag:
                await matcher.finish(msg_body)

            if isinstance(event, PrivateMessageEvent):
                await matcher.send(msg_header + msg_body)

            elif isinstance(event, GroupMessageEvent):
                chain = chain_reply(bot, chain, msg_header + msg_body)
            else:
                raise EventNotSupport

        if isinstance(event, GroupMessageEvent):
            await bot.send_group_forward_msg(group_id=event.group_id, messages=chain)

    async def onetime_divine(self) -> MessageSegment:
        theme: str = pick_theme()

        with open(self.tarot_json, 'r', encoding='utf-8') as f:
            content = json.load(f)
            all_cards = content.get("cards")
            card_info_list = self._random_cards(all_cards, theme, 1)

        flag, body = await self._get_text_and_image(theme, card_info_list[0], 1)

        return body

    def _random_cards(self,
                      all_cards: Dict[str, Dict[str, Dict[str, Union[str, Dict[str, str]]]]],
                      theme: str,
                      num: int = 1
                      ) -> List[Dict[str, Union[str, Dict[str, str]]]]:
        sub_types: List[str] = pick_sub_types(theme)

        if len(sub_types) < 1:
            raise ResourceError(f"本地塔罗牌主题 {theme} 为空！请检查资源！")

        subset: Dict[str, Dict[str, Union[str, Dict[str, str]]]] = {
            k: v for k, v in all_cards.items() if v.get("type") in sub_types
        }

        cards_index: List[str] = random.sample(list(subset), num)
        cards_info: List[Dict[str, Union[str, Dict[str, str]]]] = [
            v for k, v in subset.items() if k in cards_index]

        return cards_info

    async def _get_text_and_image(self,
                                  theme: str,
                                  card_info: Dict[str,
                                                  Union[str, Dict[str, str]]],
                                  flag
                                  ) -> Tuple[bool, MessageSegment]:
        _type: str = card_info.get("type")
        _name: str = card_info.get("pic")
        img_name: str = ""
        img_dir: Path = tarot_config.tarot_path / theme / _type

        for p in img_dir.glob(_name + ".*"):
            img_name = p.name

        name_cn: str = card_info.get("name_cn")
        is_reversed: bool = random.random() >= 0.5
        if not is_reversed:
            meaning: str = card_info.get("meaning").get("up")
            if flag: msg = MessageSegment.text(f"「{name_cn}正位」「{meaning}」\n")
            else: msg = MessageSegment.text(f"「{name_cn}正位」\n")
        else:
            meaning: str = card_info.get("meaning").get("down")
            if flag: msg = MessageSegment.text(f"「{name_cn}逆位」「{meaning}」\n")
            else: msg = MessageSegment.text(f"「{name_cn}逆位」\n")

        if img_name == "":
            raise ResourceError(f"塔罗牌图片 {theme}/{_type}/{_name} 缺失！请检查资源完整性！")

        img_b64 = cache.get_card_b64(img_dir / img_name, is_reversed)
        if img_b64 is None:
            return False, MessageSegment.text("图片读取出错，请检查本地资源……")

        return True, msg + MessageSegment.image(img_b64)


tarot_manager = Tarot()


@nonebot.get_driver().on_shutdown
async def _tarot_cache_flush() -> None:
    cache.flush()
