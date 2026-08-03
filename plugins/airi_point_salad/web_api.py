import secrets
import time

from .models import GameMode, GameSpeed, Phase


PRESENCE_TTL = 90
FINISHED_TTL = 600


class WebRooms:
    def __init__(self, service):
        self.service = service
        self.codes = {}
        self.room_codes = {}
        self.code_generations = {}
        self.access = {}
        self.presence = {}
        self.finished = {}

    def _new_room_id(self):
        return f"web:{secrets.token_urlsafe(12)}"

    def _new_code(self):
        return secrets.token_urlsafe(8).upper()

    def _grant(self, room_id, qq):
        self.access.setdefault(room_id, set()).add(qq)

    def _drop_code(self, room_id):
        code = self.room_codes.pop(room_id, None)
        self.code_generations.pop(room_id, None)
        if code is not None:
            self.codes.pop(code, None)

    def _ensure_code(self, room_id, state=None):
        current = self.room_codes.get(room_id)
        generation = getattr(state, "created_at", None)
        if (
            current is not None
            and self.codes.get(current) == room_id
            and self.code_generations.get(room_id) == generation
        ):
            return current
        if current is not None:
            self._drop_code(room_id)
        code = self._new_code()
        self.codes[code] = room_id
        self.room_codes[room_id] = code
        self.code_generations[room_id] = generation
        return code

    def revoke(self, room_id, qq):
        members = self.access.get(room_id)
        if members is not None:
            members.discard(qq)
            if not members:
                self.access.pop(room_id, None)
        self.presence.pop((room_id, qq), None)

    def _prune_finished(self):
        now = time.time()
        self.finished = {
            room_id: record
            for room_id, record in self.finished.items()
            if record[2] > now
        }

    def close(self, room_id, payload=None):
        self._prune_finished()
        members = set(self.access.get(room_id, set()))
        if payload is not None and members:
            self.finished[room_id] = (dict(payload), members, time.time() + FINISHED_TTL)
        self.access.pop(room_id, None)
        self._drop_code(room_id)
        self.presence = {
            key: seen_at
            for key, seen_at in self.presence.items()
            if key[0] != room_id
        }

    def allowed(self, room_id, qq):
        self._prune_finished()
        state = self.service.games.get(room_id)
        if state is not None:
            return qq in self.access.get(room_id, set()) or any(player.user_id == qq for player in state.players)
        record = self.finished.get(room_id)
        return record is not None and qq in record[1]

    def list_rooms(self, qq):
        self._prune_finished()
        return [
            self.snapshot(room_id, qq)
            for room_id, state in self.service.games.items()
            if state.phase is not Phase.FINISHED and self.allowed(room_id, qq)
        ]

    async def create(self, qq, nick, speed, mode):
        room_id = self._new_room_id()
        state = await self.service.create(room_id, qq, nick, GameSpeed(speed), GameMode(mode))
        self._grant(room_id, qq)
        self._ensure_code(room_id, state)
        return state

    async def code(self, room_id, qq):
        state = self.service.games.get(room_id)
        if state is None or state.phase is Phase.FINISHED:
            self._drop_code(room_id)
            raise ValueError("房间不存在或已结束")
        if qq not in self.access.get(room_id, set()) and not any(player.user_id == qq for player in state.players):
            raise ValueError("无权访问该房间码")
        return self._ensure_code(room_id, state)

    async def redeem(self, code, qq, nick):
        normalized = code.strip().upper()
        room_id = self.codes.get(normalized)
        if room_id is None:
            raise ValueError("房间码无效或已过期")
        state = self.service.games.get(room_id)
        if state is None or state.phase is Phase.FINISHED:
            self._drop_code(room_id)
            raise ValueError("房间码无效或已过期")
        state = await self.service.board_state(room_id)
        if state.phase is not Phase.LOBBY:
            raise ValueError("房间已经开始，无法加入")
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
        self._prune_finished()
        if not self.allowed(room_id, qq):
            raise ValueError("无权访问该房间")
        state = self.service.games.get(room_id)
        if state is None:
            record = self.finished.get(room_id)
            if record is None:
                raise ValueError("房间不存在或已结束")
            payload = dict(record[0])
            payload["viewer_id"] = qq
            payload["web_active"] = False
            return payload
        payload = state.to_dict()
        payload["room_id"] = room_id
        payload["web_room"] = room_id.startswith("web:")
        payload["viewer_id"] = qq
        payload["web_active"] = self.active(room_id, qq)
        return payload
