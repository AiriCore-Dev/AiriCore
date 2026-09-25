import asyncio
import time

from .client import _Connection
from .protocol import ProtocolError, QueryError, message
from .watch_store import room_id, watch_code


PVE_MODES = frozenset((4, 6, 9, 10, 12))


def snapshot(room, expected_room):
    if str(room.id) != str(expected_room):
        raise ProtocolError('观战房间数据不匹配，请重新设置观战码')
    if room.mapType not in PVE_MODES:
        raise QueryError('仅支持 PVE 对局观战，无法查询 PVP 手牌')
    if room.state != 25:
        raise QueryError('该对局已结束或尚未开始，请设置正在进行中的观战码')
    if not 1 <= len(room.players) <= 4:
        raise ProtocolError('观战返回的玩家人数异常')
    players = []
    ids, slots = set(), set()
    for player in sorted(room.players, key=lambda value: value.slot):
        if player.id == 0 or player.id in ids or player.slot in slots or not 0 <= player.slot < 4 or not player.HasField('hero'):
            raise ProtocolError('观战返回的玩家或座位数据异常')
        ids.add(player.id)
        slots.add(player.slot)
        if len(player.hero.cards) > 128:
            raise ProtocolError('观战返回的手牌数量超过限制')
        fashion = player.fashionPlan[0].fashion if player.fashionPlan else {}
        alt_arts = {item.cardId: item.cardFaceId for item in player.altArtCards.values()
                    if item.cardId > 0 and item.cardFaceId > 0 and item.cardId != item.cardFaceId}
        buffs = [{'id': buff.buff_id, 'progress': buff.progress,
                  'chain': [{'source': source.s, 'id': source.id} for source in buff.chain]}
                 for buff in sorted(player.hero.buffs.values(), key=lambda value: (value.buff_id, value.unique_id))]
        cards = [{
            'id': card.cardId if card.cardId > 0 else None,
            'alt_art_id': alt_arts.get(card.cardId) if card.cardId > 0 else None,
            'unique_id': card.uniqueId,
            'temporary': card.isTemp,
            'purify': card.purifyNum,
            'cost': card.battleCost,
        } for card in player.hero.cards]
        players.append({'uid': str(player.id), 'slot': player.slot, 'name': player.nick[:128],
                        'hero_id': player.hero.hero_id, 'cards': cards,
                        'card_back_item_id': fashion.get(3) or None,
                        'card_attack_bonus': player.hero.cardAtk + sum(attr.cardAtk for attr in player.hero.addition_attrs.values()),
                        'card_distance_bonus': player.hero.cardDistance + sum(attr.cardDistance for attr in player.hero.addition_attrs.values()),
                        'buffs': buffs})
    return {'room_id': str(room.id), 'map_type': room.mapType, 'round': room.round,
            'captured_at': time.time(), 'players': players}


class WatchClient:
    def __init__(self, settings):
        self.settings = settings

    async def fetch(self, code, expected_room=None):
        code = watch_code(code)
        expected_room = room_id(expected_room) if expected_room is not None else None
        self.settings.validate()
        writer, rpc = None, None
        join_attempted, completed = False, False
        try:
            async with asyncio.timeout(self.settings.timeout * 4):
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.settings.host, self.settings.port), self.settings.timeout)
                rpc = _Connection(reader, writer, self.settings.timeout)
                await rpc.login(self.settings)
                join_attempted = True
                joined = await rpc.exchange(5191, 5192, message('WatchJoinRoomC2S', watchCode=code), 'WatchJoinRoomS2C')
                current_room = room_id(joined.room_id)
                if joined.room_server_id <= 0:
                    raise ProtocolError('观战返回的房间服务器编号无效')
                if expected_room is not None and current_room != expected_room:
                    raise QueryError('本群原观战对局已失效，观战码指向了其他房间；请重新发送 astral watch 观战码')
                if joined.map_type not in PVE_MODES:
                    raise QueryError('仅支持 PVE 对局观战，无法查询 PVP 手牌')
                response = await rpc.exchange(5193, 5194, message('WatchRefreshRoomStateC2S',
                    room_id=joined.room_id, room_server_id=joined.room_server_id), 'WatchRefreshRoomStateS2C')
                if response.room_id not in (0, joined.room_id) or not response.HasField('room'):
                    raise ProtocolError('观战房间快照缺失或不匹配')
                result = snapshot(response.room, current_room)
                completed = True
                return result
        except TimeoutError:
            raise QueryError('获取观战手牌超时，请稍后重试') from None
        except (OSError, ConnectionError):
            raise QueryError('暂时无法连接观战服务，请稍后重试') from None
        finally:
            try:
                if join_attempted and rpc is not None:
                    try:
                        async with asyncio.timeout(min(self.settings.timeout, 3)):
                            await rpc.exchange(5195, 5196, message('WatchExitRoomC2S'), 'WatchExitRoomS2C')
                    except (QueryError, OSError, TimeoutError):
                        if completed:
                            raise QueryError('退出观战未获确认，本次查询未完成，请稍后重试') from None
            finally:
                if writer is not None:
                    writer.close()
                    try:
                        await asyncio.wait_for(writer.wait_closed(), 2)
                    except (OSError, TimeoutError):
                        pass
