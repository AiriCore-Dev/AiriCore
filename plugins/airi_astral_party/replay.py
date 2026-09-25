import re
import http.client
import struct
import time
import urllib.request

from .client import as_dict
from .protocol import MAX_PAYLOAD, QueryError, decode, message
from .renewal import NoRedirect


MAX_REPLAY_BYTES = 32 * 1024 * 1024
STAT_FIELDS = (
    'killCount', 'totalDamage', 'totalDie', 'totalInjured', 'pvpResultGold',
    'pvpResultLv', 'totalGold', 'pveTransferGold', 'pkDamageMax',
    'treatmentScore', 'movePoint', 'battleDiceSixCount', 'finalKillBoss',
)


def wire_fields(data):
    offset, result = 0, {}
    def varint():
        nonlocal offset
        value = 0
        for shift in range(0, 70, 7):
            if offset >= len(data):
                raise QueryError('回放字段不完整')
            byte = data[offset]
            offset += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise QueryError('回放字段过长')
    while offset < len(data):
        tag = varint()
        kind = tag & 7
        if kind == 0:
            value = varint()
        elif kind in (1, 2, 5):
            length = varint() if kind == 2 else 8 if kind == 1 else 4
            if length > len(data) - offset:
                raise QueryError('回放字段越界')
            value = data[offset:offset + length]
            offset += length
            if kind != 2:
                value = int.from_bytes(value, 'little', signed=True)
        else:
            raise QueryError('回放字段类型不支持')
        result.setdefault(tag >> 3, []).append(value)
    return result


def equipped_relics(payload, name):
    room_field = message(name).DESCRIPTOR.fields_by_name['room']
    players_field = room_field.message_type.fields_by_name['players']
    hero_field = players_field.message_type.fields_by_name['hero']
    relics_field = hero_field.message_type.fields_by_name['select_relics']
    id_field = players_field.message_type.fields_by_name['id']
    room = wire_fields(wire_fields(payload)[room_field.number][0])
    result = {}
    for raw in room.get(players_field.number, []):
        player = wire_fields(raw)
        hero = wire_fields(player[hero_field.number][0])
        rows = [wire_fields(entry) for entry in hero.get(relics_field.number, [])]
        result[str(player[id_field.number][0])] = [row[1][0] for row in rows if row.get(2, [0])[0]][:128]
    return result


def download(replay_id):
    if not re.fullmatch(r'[0-9]{1,20}', str(replay_id)):
        raise QueryError('回放编号无效')
    request = urllib.request.Request('https://sereplaycn.feimogames.com/prod/' + str(replay_id))
    deadline = time.monotonic() + 17
    chunks, size = [], 0
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=8) as response:
        while True:
            chunk = response.read1(65536)
            size += len(chunk)
            if size > MAX_REPLAY_BYTES or time.monotonic() > deadline:
                raise QueryError('回放超过下载限制')
            if not chunk:
                return b''.join(chunks)
            chunks.append(chunk)


def parse_replay(data, snapshot):
    if not data or len(data) > MAX_REPLAY_BYTES:
        raise QueryError('回放大小异常')
    offset, count, frames, previous_snapshot = 0, 0, {}, None
    while offset < len(data):
        if len(data) - offset < 6:
            raise QueryError('回放帧不完整')
        command, size = struct.unpack_from('>hi', data, offset)
        offset += 6
        count += 1
        if count > 200000 or not 0 <= size <= min(MAX_PAYLOAD, len(data) - offset):
            raise QueryError('回放帧长度异常')
        if command in (1003, 1113, 1016):
            if command == 1113:
                previous_snapshot = frames.get(1113)
            frames[command] = data[offset:offset + size]
        offset += size
    if 1016 not in frames or previous_snapshot is None:
        raise QueryError('回放缺少结算数据')
    finish = as_dict(decode('GameFinishS2C', frames[1016]))
    room_payload = previous_snapshot
    room = as_dict(decode('ReplaySnapshotS2C', room_payload))['room']
    relics = equipped_relics(room_payload, 'ReplaySnapshotS2C')
    selected = snapshot['selected']
    if any(str(finish.get(a)) != str(selected.get(b)) for a, b in (
        ('replayId', 'replayId'), ('version', 'version'), ('finish_time', 'time'), ('mapType', 'mapType'),
    )) or str(room['id']) != str(finish['room_id']) or room['mapType'] != selected['mapType']:
        raise QueryError('回放与对局记录不匹配')
    expected = {str(row['playerId']): row for row in snapshot['details']}
    players = {str(row['id']): row for row in room['players']}
    if not expected or not expected.keys() <= players.keys() or not expected.keys() <= finish['newAchieve'].keys():
        raise QueryError('回放玩家不匹配')
    result = {}
    for uid, record in expected.items():
        player, stats = players[uid], finish['newAchieve'][uid]
        hero = player['hero']
        if hero['hero_id'] != record['heroId'] or player['slot'] != record['slot']:
            raise QueryError('回放角色或座位不匹配')
        plans = player.get('fashionPlan', [])
        plan = plans[0] if plans else {}
        fashion = plan.get('fashion', {})
        result[uid] = {
            'stats': {key: stats[key] for key in STAT_FIELDS},
            'relics': relics.get(uid, []),
            'standingPainting': hero.get('standingPainting', 0),
            'winner': str(hero.get('teamId')) == str(finish['winer']),
            'name': player['nick'], 'playerLevel': player['level'],
            'headIcon': fashion.get('1', record.get('headIcon')),
            'background': fashion.get('2', record.get('background')),
            'lv': hero.get('lv', record.get('lv')),
            'gold': stats.get('pvpResultGold', record.get('gold')) if selected['mapType'] not in (4, 6, 9, 10, 12) else record.get('gold'),
        }
    if selected['mapType'] not in (4, 6, 9, 10, 12):
        scores = sorted({(players[uid]['hero']['lv'], players[uid]['hero']['gold']) for uid in expected}, reverse=True)
        for uid, row in result.items():
            row['rank'] = (1 if row['winner'] else 2) if selected['mapType'] in (7, 11) else scores.index((players[uid]['hero']['lv'], players[uid]['hero']['gold'])) + 1
    return {
        'players': result, 'mapId': room['map_id'], 'round': room['round'],
        'difficulty': room['difficulty'], 'replayId': selected['replayId'],
    }


def enrich_snapshot(snapshot):
    if not snapshot.get('show', {}).get('isShowFight'):
        return snapshot
    selected = snapshot.get('selected') or {}
    if not selected.get('replayId') or not snapshot.get('details'):
        return snapshot
    try:
        settlement = parse_replay(download(selected['replayId']), snapshot)
    except (OSError, http.client.HTTPException, ValueError, KeyError, TypeError):
        return {**snapshot, 'settlementUnavailable': True}
    return {**snapshot, 'settlement': settlement}
