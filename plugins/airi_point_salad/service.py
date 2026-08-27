import asyncio
import copy
import inspect
from pathlib import Path
import time
from typing import Any
import weakref

from utils.coordination import registry

from .game import (
    GameError,
    add_player,
    create_game,
    flip_score,
    remove_player,
    request_player_swap,
    respond_player_swap,
    start_game,
    stop_game,
    take_characters,
    take_score,
)
from .models import GameMode, GameSpeed, GameState, Phase
from .persistence import GameStore
from .render_runtime import run_sync
from .skills import skill_usage, use_skill


LOBBY_TIMEOUT = 15 * 60
GAME_TIMEOUT = 30 * 60


class GameService:
    def __init__(self, store: GameStore | None = None):
        self.store = store or GameStore(Path("data/airi_point_salad/games.pk"))
        self.games: dict[str, GameState] = {}
        self.locks = weakref.WeakValueDictionary()
        self.timers: dict[str, asyncio.Task] = {}
        self.timeout_callback = None

    async def load(self) -> None:
        self.games = await self.store.load()
        now = time.time()
        removable = [
            group_id
            for group_id, state in self.games.items()
            if state.phase is Phase.FINISHED
            or now - state.updated_at >= self._timeout_for(state)
        ]
        for group_id in removable:
            self.games.pop(group_id, None)
        if removable:
            await self.store.save(self.games)
        for group_id in self.games:
            self._schedule_timeout(group_id)

    async def save(self) -> None:
        await self.store.save(self.games)

    async def set_room_code(self, group_id: str, room_code: str) -> GameState:
        def operation():
            state = self._require_state(group_id)
            state.room_code = room_code
            return state

        return await self._mutate(group_id, operation)

    def close(self) -> None:
        for timer in self.timers.values():
            timer.cancel()
        self.timers.clear()

    async def create(
        self,
        group_id: str,
        user_id: str,
        name: str,
        speed: GameSpeed,
        mode: GameMode,
        seed: int | None = None,
        prepare=None,
    ):
        now = time.time()

        def operation():
            current = self.games.get(group_id)
            if current is not None and current.phase is not Phase.FINISHED:
                raise GameError("本群已经有一局得分沙拉")
            state = create_game(
                group_id,
                user_id,
                name,
                speed,
                mode,
                seed if seed is not None else int(now * 1000),
                now,
            )
            self.games[group_id] = state
            return state

        return await self._mutate(group_id, operation, prepare)

    async def join(self, group_id: str, user_id: str, name: str, prepare=None):
        return await self._state_mutation(
            group_id,
            lambda state: add_player(state, user_id, name, time.time()),
            prepare,
        )

    async def leave(self, group_id: str, user_id: str, prepare=None):
        return await self._state_mutation(
            group_id,
            lambda state: remove_player(state, user_id, time.time()),
            prepare,
        )

    async def request_swap(
        self,
        group_id: str,
        user_id: str,
        target_user_id: str,
        prepare=None,
    ):
        return await self._state_mutation(
            group_id,
            lambda state: request_player_swap(
                state,
                user_id,
                target_user_id,
                time.time(),
            ),
            prepare,
        )

    async def respond_swap(
        self,
        group_id: str,
        user_id: str,
        accept: bool,
        prepare=None,
    ):
        return await self._state_mutation(
            group_id,
            lambda state: respond_player_swap(state, user_id, accept, time.time()),
            prepare,
        )

    async def start(self, group_id: str, user_id: str, prepare=None):
        return await self._state_mutation(
            group_id,
            lambda state: start_game(state, user_id, time.time()),
            prepare,
        )

    async def take(self, group_id: str, user_id: str, args: list[Any], prepare=None):
        def action(state):
            now = time.time()
            if len(args) == 1 and type(args[0]) is int:
                take_score(state, user_id, args[0], now)
            elif len(args) == 2 and type(args[0]) is int and isinstance(args[1], tuple):
                take_score(state, user_id, args[0], now, args[1])
            elif args and all(isinstance(item, tuple) for item in args):
                take_characters(state, user_id, args, now)
            else:
                raise GameError("拿牌参数无效")

        return await self._state_mutation(group_id, action, prepare)

    async def flip(self, group_id: str, user_id: str, index: int, prepare=None):
        return await self._state_mutation(
            group_id,
            lambda state: flip_score(state, user_id, index, time.time()),
            prepare,
        )

    async def skill(self, group_id: str, user_id: str, args: list[Any], prepare=None):
        return await self._state_mutation(
            group_id,
            lambda state: use_skill(state, user_id, args, time.time()),
            prepare,
        )

    async def stop(
        self,
        group_id: str,
        user_id: str,
        is_admin: bool,
        prepare=None,
    ):
        return await self._state_mutation(
            group_id,
            lambda state: stop_game(state, user_id, is_admin, time.time()),
            prepare,
        )

    async def board_state(self, group_id: str) -> GameState:
        lock = self.locks.setdefault(group_id, asyncio.Lock())
        async with lock:
            return copy.deepcopy(self._require_state(group_id))

    async def rules_text(self, group_id: str | None = None) -> str:
        lines = [
            "MORE MORE JUMP！得分沙拉｜2–6 人｜官方 108 张卡牌",
            "快速和标准只改变牌量；普通模式使用官方基础规则，混合模式在其上加入 Center 与 Live Mission。",
            "三叠独立牌库按列补牌；空堆从最大牌堆拆出下半部分。每回合拿一张计分牌或两张角色牌。",
            "每回合最多翻一张计分牌，可在行动前或行动后翻；下一名玩家首次有效行动会关闭上一人的后置窗口。",
            "牌库与市场清空后结算十二类官方计分；同分时最后行动顺序较晚者优先。",
            "创建：创建/create/cr + 快速/quick/qk 或 标准/standard/std + 原版/classic/cl 或 混合/mix/mx",
            "房间：加入/join/j · 退出/leave/lv · 开始/start/st · 结束/stop/sp",
            "行动：拿/take/ta · 翻/flip/fl · 技能/skill/sk",
            "查看：桌面/board/bd · 规则/rules/rl",
            "示例：,sl cr qk cl · ,sl ta A · ,sl ta A1 B2 · ,sl fl 2 · ,sl sk",
            "详细帮助请发送 ,sl rl 查看",
        ]
        if group_id:
            lock = self.locks.setdefault(group_id, asyncio.Lock())
            async with lock:
                state = self.games.get(group_id)
                if state is not None and state.phase is Phase.PLAYING:
                    player = state.players[state.current_player]
                    if player.center is not None and not player.skill_used:
                        lines.append(f"当前 Center 技能：{skill_usage(player.center)}")
        return "\n\n".join(lines)

    async def _state_mutation(self, group_id, action, prepare):
        def operation():
            state = self._require_state(group_id)
            action(state)
            return state

        return await self._mutate(group_id, operation, prepare)

    async def _mutate(self, group_id, operation, prepare=None):
        lock = self.locks.setdefault(group_id, asyncio.Lock())
        async with lock:
            before_exists = group_id in self.games
            before = copy.deepcopy(self.games[group_id]) if before_exists else None
            before_turn_user_id = self._turn_user_id(before)
            try:
                result = operation()
                after_turn_user_id = self._turn_user_id(result)
                turn_user_id = (
                    after_turn_user_id
                    if after_turn_user_id != before_turn_user_id
                    else None
                )
                prepared = result
                if prepare is not None:
                    prepare_args = (
                        copy.deepcopy(result),
                        turn_user_id,
                    )
                    parameters = tuple(inspect.signature(prepare).parameters.values())
                    accepts_before = len(parameters) >= 3 or any(
                        parameter.kind is inspect.Parameter.VAR_POSITIONAL
                        for parameter in parameters
                    )
                    if accepts_before:
                        prepare_args += (copy.deepcopy(before) if before_exists else None,)
                    prepared = await run_sync(
                        prepare,
                        *prepare_args,
                    )
                if result.phase is Phase.FINISHED:
                    self.games.pop(group_id, None)
                await self.store.save(self.games)
            except Exception:
                if not before_exists:
                    self.games.pop(group_id, None)
                else:
                    self.games[group_id] = before
                raise
            self._schedule_timeout(group_id)
            return prepared

    @staticmethod
    def _turn_user_id(state: GameState | None) -> str | None:
        if state is None or state.phase is not Phase.PLAYING:
            return None
        return state.players[state.current_player].user_id

    def _require_state(self, group_id: str) -> GameState:
        state = self.games.get(group_id)
        if state is None or state.phase is Phase.FINISHED:
            raise GameError("本群当前没有得分沙拉游戏")
        return state

    def _schedule_timeout(self, group_id: str) -> None:
        timer = self.timers.pop(group_id, None)
        if timer is not None:
            timer.cancel()
        state = self.games.get(group_id)
        if state is None or state.phase is Phase.FINISHED:
            return
        elapsed = time.time() - state.updated_at
        delay = max(0.0, self._timeout_for(state) - elapsed)
        expected_state = state

        async def run():
            try:
                await asyncio.sleep(delay)
                await self._expire(group_id, expected_state)
            except asyncio.CancelledError:
                raise

        self.timers[group_id] = registry.create(
            run(),
            owner=f"airi_point_salad:{group_id}",
            key=group_id,
        )

    async def _expire(
        self,
        group_id: str,
        expected_state: GameState | None = None,
    ) -> None:
        lock = self.locks.setdefault(group_id, asyncio.Lock())
        async with lock:
            state = self.games.get(group_id)
            if state is None:
                return
            if expected_state is not None and state is not expected_state:
                return
            remaining = self._timeout_for(state) - (time.time() - state.updated_at)
            if remaining > 0:
                self._schedule_timeout(group_id)
                return
            phase = state.phase
            self.games.pop(group_id, None)
            self.timers.pop(group_id, None)
            try:
                await self.store.save(self.games)
            except Exception:
                self.games[group_id] = state
                async def retry():
                    try:
                        await asyncio.sleep(60)
                        await self._expire(group_id, state)
                    except asyncio.CancelledError:
                        raise

                self.timers[group_id] = registry.create(
                    retry(),
                    owner=f"airi_point_salad:{group_id}",
                    key=(group_id, "retry"),
                )
                raise
        if self.timeout_callback is not None:
            await self.timeout_callback(group_id, phase)

    @staticmethod
    def _timeout_for(state: GameState) -> int:
        return LOBBY_TIMEOUT if state.phase is Phase.LOBBY else GAME_TIMEOUT
