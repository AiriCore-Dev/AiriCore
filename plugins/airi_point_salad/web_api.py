import secrets
import time

from .models import GameMode, GameSpeed, Phase


CODE_TTL = 600
PRESENCE_TTL = 90


class WebRooms:
    def __init__(self, service):
        self.service = service
        self.codes = {}
        self.access = {}
        self.presence = {}

    def _new_room_id(self):
        return f"web:{secrets.token_urlsafe(12)}"

    def _new_code(self):
        return secrets.token_urlsafe(8).upper()

    def _grant(self, room_id, qq):
        self.access.setdefault(room_id, set()).add(qq)

    def revoke(self, room_id, qq):
        members = self.access.get(room_id)
        if members is not None:
            members.discard(qq)
            if not members:
                self.access.pop(room_id, None)
        self.presence.pop((room_id, qq), None)

    def close(self, room_id):
        self.access.pop(room_id, None)
        self.codes = {
            code: record
            for code, record in self.codes.items()
            if record[0] != room_id
        }
        self.presence = {
            key: seen_at
            for key, seen_at in self.presence.items()
            if key[0] != room_id
        }

    def allowed(self, room_id, qq):
        state = self.service.games.get(room_id)
        return state is not None and (qq in self.access.get(room_id, set()) or any(player.user_id == qq for player in state.players))

    def list_rooms(self, qq):
        return [
            self.snapshot(room_id, qq)
            for room_id, state in self.service.games.items()
            if state.phase is not Phase.FINISHED and self.allowed(room_id, qq)
        ]

    async def create(self, qq, nick, speed, mode):
        room_id = self._new_room_id()
        state = await self.service.create(room_id, qq, nick, GameSpeed(speed), GameMode(mode))
        self._grant(room_id, qq)
        return state

    async def code(self, room_id, qq):
        state = await self.service.board_state(room_id)
        if state.host_id != qq or state.phase is not Phase.LOBBY:
            raise ValueError("只有大厅中的房主可以创建房间码")
        code = self._new_code()
        self.codes[code] = (room_id, time.time() + CODE_TTL)
        return code

    async def redeem(self, code, qq, nick):
        record = self.codes.pop(code.strip().upper(), None)
        if record is None or record[1] < time.time():
            raise ValueError("房间码无效或已过期")
        room_id = record[0]
        state = await self.service.join(room_id, qq, nick)
        self._grant(room_id, qq)
        return state

    def heartbeat(self, room_id, qq):
        if not self.allowed(room_id, qq):
            raise ValueError("无权访问该房间")
        self.presence[(room_id, qq)] = time.time()

    def active(self, room_id, qq):
        return time.time() - self.presence.get((room_id, qq), 0) <= PRESENCE_TTL

    def snapshot(self, room_id, qq):
        if not self.allowed(room_id, qq):
            raise ValueError("无权访问该房间")
        state = self.service.games.get(room_id)
        if state is None:
            raise ValueError("房间不存在或已结束")
        payload = state.to_dict()
        payload["room_id"] = room_id
        payload["web_room"] = room_id.startswith("web:")
        payload["viewer_id"] = qq
        payload["web_active"] = self.active(room_id, qq)
        return payload
