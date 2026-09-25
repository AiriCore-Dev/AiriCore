import json
import re
from pathlib import Path


_ASSETS = Path(__file__).parent / 'assets'
_CARDS = json.loads((_ASSETS / 'cards.json').read_text(encoding='utf-8'))
_CATALOG = json.loads((_ASSETS / 'cards/catalog.json').read_text(encoding='utf-8'))
_SKILLS = {int(key): value for key, value in _CATALOG.get('skills', {}).items()}
_RANGE_CARDS = frozenset((20001, 20004, 20008, 20010, 20012, 20013, 20018, 20019,
                          20025, 20028, 20029, 20030, 20031, 20033, 21001, 21007,
                          21009, 21012, 21013, 21019))


def _card_config(card_id):
    value = _CARDS.get(str(card_id))
    if not isinstance(value, dict):
        return {}
    return value


def _skill_cost_delta(player):
    for buff in player.get('buffs', ()):
        if buff.get('id') != 1151201:
            continue
        chains = buff.get('chain', ())
        if chains and chains[0].get('source') == 1:
            params = _SKILLS.get(int(chains[0].get('id', 0)))
            if params is not None and len(params) > 5:
                return int(params[5])
        return None
    return None


def _cost(card_id, card, config, player, map_type):
    configured = int(config.get('cost', 0))
    battle_cost = card.get('cost')
    if battle_cost is None or not isinstance(battle_cost, int) or battle_cost < 0:
        battle_cost = configured
    if card_id == 10007:
        delta = _skill_cost_delta(player)
        if delta is not None:
            return max(0, battle_cost + delta)
    if map_type == 10:
        return configured
    return battle_cost


def _description(card_id, card, config, player):
    text = str(config.get('description', ''))
    distance = int(player.get('card_distance_bonus', 0) or 0)
    params = config.get('params', ())
    if distance > 0 and card_id in _RANGE_CARDS and params:
        base_range = int(params[-1] if card_id == 21019 else params[0])
        text = text.replace(f'range={base_range}',
                            f'range=[color=#94FF46]{base_range + distance}[/color]')
    attack = int(player.get('card_attack_bonus', 0) or 0)
    if card_id == 20031:
        attack += next((int(buff.get('progress', 0) or 0) for buff in player.get('buffs', ())
                        if buff.get('id') == 1211201), 0)
    if attack > 0 and len(params) > 2 and card_id != 21022:
        damage = -int(params[2])
        text = text.replace(f'damage={damage}', f'damage=[color=#94FF46]{damage + attack}[/color]')
    if card_id == 21022:
        purify = int(card.get('purify', 0) or 0)
        match = re.search(r'\{stack=(-?\d+)\}', text)
        if match:
            value = int(match.group(1)) - purify
            rendered = f'{{stack=[color=#94FF46]{value}[/color]}}' if purify > 0 else f'{{stack={value}}}'
            text = text[:match.start()] + rendered + text[match.end():]
    return text


def card_state(card, player, map_type):
    card_id = int(card.get('id') or 0)
    config = _card_config(card_id)
    return {'cost': _cost(card_id, card, config, player, int(map_type)),
            'description': _description(card_id, card, config, player)}
