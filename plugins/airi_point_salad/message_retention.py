from collections import defaultdict
from dataclasses import dataclass


@dataclass(slots=True)
class _Record:
    token: int
    user_message_id: str | None
    bot_message_id: str | None = None
    active: bool = False
    trimmed: bool = False


class MessageRetention:
    def __init__(self, limit: int = 3):
        self.limit = limit
        self._next_token = 0
        self._records = defaultdict(dict)
        self._active = defaultdict(list)

    def reserve(self, group_id: str, user_message_id: str | None) -> int:
        token = self._next_token
        self._next_token += 1
        self._records[group_id][token] = _Record(token, user_message_id)
        return token

    async def activate(self, group_id: str, token: int, delete) -> None:
        record = self._records.get(group_id, {}).get(token)
        if record is None or record.active or record.trimmed:
            return
        record.active = True
        active = self._active[group_id]
        active.append(token)
        active.sort()
        while len(active) > self.limit:
            old_token = active.pop(0)
            old_record = self._records[group_id][old_token]
            old_record.active = False
            old_record.trimmed = True
            await self._delete_ids(
                (old_record.user_message_id, old_record.bot_message_id),
                delete,
            )

    async def complete(
        self,
        group_id: str,
        token: int,
        bot_message_id: str | None,
        delete,
    ) -> None:
        record = self._records.get(group_id, {}).get(token)
        if record is None:
            if bot_message_id is not None:
                await self._delete_ids((bot_message_id,), delete)
            return
        record.bot_message_id = bot_message_id
        if record.trimmed and bot_message_id is not None:
            await self._delete_ids((bot_message_id,), delete)
        if record.trimmed:
            self._records[group_id].pop(token, None)
            self._drop_empty(group_id)

    def cancel(self, group_id: str, token: int) -> None:
        record = self._records.get(group_id, {}).pop(token, None)
        if record is not None and record.active:
            active = self._active.get(group_id, [])
            if token in active:
                active.remove(token)
        self._drop_empty(group_id)

    async def remember(
        self,
        group_id: str,
        user_message_id: str | None,
        bot_message_id: str | None,
        delete,
    ) -> None:
        token = self.reserve(group_id, user_message_id)
        await self.activate(group_id, token, delete)
        await self.complete(group_id, token, bot_message_id, delete)

    def ids(self, group_id: str) -> list[tuple[str | None, str | None]]:
        records = self._records.get(group_id, {})
        return [
            (records[token].user_message_id, records[token].bot_message_id)
            for token in self._active.get(group_id, ())
            if token in records
        ]

    def clear(self, group_id: str) -> None:
        self._records.pop(group_id, None)
        self._active.pop(group_id, None)

    async def _delete_ids(self, message_ids, delete) -> None:
        for message_id in message_ids:
            if message_id is None:
                continue
            try:
                await delete(message_id)
            except Exception:
                continue

    def _drop_empty(self, group_id: str) -> None:
        if not self._records.get(group_id):
            self._records.pop(group_id, None)
        if not self._active.get(group_id):
            self._active.pop(group_id, None)
