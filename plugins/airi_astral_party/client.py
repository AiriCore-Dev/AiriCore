import asyncio

from google.protobuf.json_format import MessageToDict

from .protocol import Frame, ProtocolError, QueryError, decode, encode_frame, message, read_frame


READ_CALLS = {
    'SearchPlayer': (5185, 5186),
    'GetShowPlayer': (5153, 5154),
    'GetPlayerFightRecord': (5155, 5156),
}


def as_dict(value):
    return MessageToDict(value, preserving_proto_field_name=True,
                         always_print_fields_with_no_presence=True, use_integers_for_enums=True)


class GameClient:
    def __init__(self, settings):
        self.settings = settings
        self._lock = asyncio.Lock()

    async def fetch(self, uid, detail=None):
        self.settings.validate()
        if not isinstance(uid, int) or isinstance(uid, bool) or not 0 < uid < 2**63:
            raise QueryError('玩家 UID 无效')
        if detail is not None and (not isinstance(detail, int) or not 1 <= detail <= 100):
            raise QueryError('对局序号应为 1 至 100')
        if self._lock.locked():
            raise QueryError('吉星派对正在查询其他玩家，请稍后重试')
        async with self._lock:
            writer = None
            try:
                async with asyncio.timeout(self.settings.timeout * 5):
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(self.settings.host, self.settings.port), self.settings.timeout
                    )
                    rpc = _Connection(reader, writer, self.settings.timeout)
                    await rpc.login(self.settings)
                    base = await rpc.call('SearchPlayer', playerId=uid)
                    profile = await rpc.call('GetShowPlayer', player_id=uid)
                    if not base.HasField('info') or base.info.playerId != uid:
                        raise QueryError('未找到该玩家，请检查 UID 和服务器配置')
                    if not profile.HasField('showData') or profile.showData.player_id != uid:
                        raise ProtocolError('游戏返回的玩家资料不匹配')
                    info, show = as_dict(base.info), as_dict(profile.showData)
                    show.pop('replayRecord', None)
                    if not show['isShowData']:
                        show.pop('statistics', None)
                    if not show['isShowFight']:
                        show['record'] = []
                    show['record'] = sorted(show['record'], key=lambda row: int(row['time']), reverse=True)[:100]
                    result = {'uid': uid, 'info': info, 'show': show, 'details': [], 'selected': None}
                    if detail is not None:
                        if not show['isShowFight']:
                            raise QueryError('该玩家未公开对局记录')
                        if detail > len(show['record']):
                            raise QueryError('该对局序号不存在，请先用“astral me recent”或“astral UID recent”查询战绩')
                        selected = show['record'][detail - 1]
                        response = await rpc.call('GetPlayerFightRecord', player_id=uid, index=selected['index'])
                        result['details'] = sorted(as_dict(response)['recordData'], key=lambda row: (row['rank'], row['slot']))
                        result['selected'] = selected
                        if not result['details']:
                            raise QueryError('该对局详情暂不可用，记录可能已经过期')
                    return result
            except TimeoutError:
                raise QueryError('查询游戏服务器超时，请稍后重试') from None
            except (OSError, ConnectionError):
                raise QueryError('暂时无法连接游戏服务器，请稍后重试或联系管理员') from None
            finally:
                if writer is not None:
                    writer.close()
                    try:
                        await asyncio.wait_for(writer.wait_closed(), 2)
                    except (OSError, TimeoutError):
                        pass


class _Connection:
    def __init__(self, reader, writer, timeout):
        self.reader, self.writer, self.timeout = reader, writer, timeout
        self.session, self.sequence = 0, 100

    async def exchange(self, command, response_command, request, response_name):
        self.sequence += 1
        frame = Frame(command, self.session, self.sequence, request.SerializeToString())
        async with asyncio.timeout(self.timeout):
            self.writer.write(encode_frame(frame))
            await self.writer.drain()
            for _ in range(256):
                response = await read_frame(self.reader)
                if response.command == 1001:
                    raise QueryError('查询账号已被断开，请管理员检查专用账号登录状态')
                if response.sequence != self.sequence:
                    continue
                if response.command != response_command:
                    raise ProtocolError('游戏返回的查询类型不匹配')
                if response.error:
                    if command in (5191, 5193, 5195):
                        watch_errors = {
                            11001: '观战房间不存在，请确认对局仍在进行并重新复制观战码',
                            11080: '观战对局已结束，请重新设置正在进行中的观战码',
                            11081: '观战码无效或当前不可用，请从游戏内重新复制',
                            11082: '该对局观战人数已满，请稍后重试',
                        }
                        if response.error in watch_errors:
                            raise QueryError(f'{watch_errors[response.error]}（{response.error}）')
                    if response.error == 12013:
                        raise QueryError('玩家资料暂未就绪，请稍后重试（12013）')
                    if response.error == 12014:
                        raise QueryError('游戏查询过于频繁，请稍后重试（12014）')
                    stage = '账号登录' if command == 5001 else '数据查询'
                    raise QueryError(f'游戏{stage}失败，错误码：{response.error}；请稍后重试或联系管理员')
                return decode(response_name, response.payload)
            raise ProtocolError('游戏推送数据过多，请稍后重试')

    async def login(self, settings):
        request = message('ConnectC2S', publicKey='t4UDM%2Q', auth=4, clientVer=settings.client_version,
                          china={'gameId': settings.game_id, 'channelId': settings.channel_id,
                                 'appId': settings.app_id, 'sid': settings.sid,
                                 'extra': settings.extra, 'deviceId': settings.device_id})
        response = await self.exchange(5001, 5002, request, 'ConnectS2C')
        if not response.HasField('account') or response.sessionId == 0 or response.queueTime > 0:
            raise QueryError('查询账号尚未完成登录或正在排队，请稍后重试')
        self.session = response.sessionId

    async def call(self, name, **values):
        command, response = READ_CALLS[name]
        return await self.exchange(command, response, message(name + 'C2S', **values), name + 'S2C')
