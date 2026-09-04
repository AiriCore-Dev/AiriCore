from __future__ import annotations

import asyncio
import math
import os
import pickle
import tempfile
from dataclasses import dataclass
from pathlib import Path


DATA_FILE = Path("data/credits/data.pk")
MIGRATION_MARKER = Path("data/credits/migration_v1")


class CreditsError(RuntimeError):
    pass


class CreditsStorageError(CreditsError):
    pass


class InvalidCreditAmountError(ValueError):
    pass


class InsufficientCreditsError(CreditsError):
    pass


@dataclass(frozen=True)
class TransferResult:
    from_user_id: str
    to_user_id: str
    amount: int
    fee: int
    sender_balance: int
    receiver_balance: int


_balances: dict[str, int] = {}
_loaded_file: Path | None = None
_load_failed = False
_lock = asyncio.Lock()


def normalize_user_id(user_id: str) -> str:
    value = str(user_id).strip()
    if not value:
        raise ValueError("用户 ID 不能为空")
    return value


def _validate_amount(amount: int) -> int:
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise InvalidCreditAmountError("积分金额必须是正整数")
    return amount


def _atomic_dump(path: Path, value: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            pickle.dump(value, stream, protocol=pickle.HIGHEST_PROTOCOL)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _read_file(path: Path) -> dict[str, int]:
    with path.open("rb") as stream:
        raw = pickle.load(stream)
    if not isinstance(raw, dict):
        raise ValueError("积分账本结构异常")
    result = {}
    for user_id, balance in raw.items():
        try:
            normalized = normalize_user_id(user_id)
            if isinstance(balance, bool):
                raise ValueError
            result[normalized] = int(balance)
        except (TypeError, ValueError, OverflowError):
            continue
    return result


def _load_locked() -> None:
    global _loaded_file, _load_failed
    path = Path(DATA_FILE)
    if _loaded_file == path:
        if _load_failed:
            raise CreditsStorageError("积分账本读取失败，已停止写入")
        return
    _balances.clear()
    _loaded_file = path
    _load_failed = False
    if not path.exists():
        return
    try:
        _balances.update(_read_file(path))
    except Exception as exc:
        try:
            os.replace(path, path.with_name(path.name + ".corrupt"))
        except OSError:
            pass
        _load_failed = True
        raise CreditsStorageError("积分账本读取失败，已停止写入") from exc


async def _persist_locked() -> None:
    if _load_failed:
        raise CreditsStorageError("积分账本读取失败，已停止写入")
    snapshot = dict(_balances)
    await asyncio.to_thread(_atomic_dump, Path(DATA_FILE), snapshot)


async def get_balance(user_id: str) -> int:
    normalized = normalize_user_id(user_id)
    async with _lock:
        _load_locked()
        return int(_balances.get(normalized, 0))


async def has_account(user_id: str) -> bool:
    normalized = normalize_user_id(user_id)
    async with _lock:
        _load_locked()
        return normalized in _balances


async def credit(user_id: str, amount: int) -> int:
    normalized = normalize_user_id(user_id)
    amount = _validate_amount(amount)
    async with _lock:
        _load_locked()
        before = dict(_balances)
        _balances[normalized] = int(_balances.get(normalized, 0)) + amount
        try:
            await _persist_locked()
        except Exception:
            _balances.clear()
            _balances.update(before)
            raise
        return _balances[normalized]


async def debit(user_id: str, amount: int) -> int:
    normalized = normalize_user_id(user_id)
    amount = _validate_amount(amount)
    async with _lock:
        _load_locked()
        current = int(_balances.get(normalized, 0))
        if current < amount:
            raise InsufficientCreditsError("积分余额不足")
        before = dict(_balances)
        _balances[normalized] = current - amount
        try:
            await _persist_locked()
        except Exception:
            _balances.clear()
            _balances.update(before)
            raise
        return _balances[normalized]


async def transfer(
    from_user_id: str,
    to_user_id: str,
    amount: int,
    fee_rate: float = 0.1,
) -> TransferResult:
    sender = normalize_user_id(from_user_id)
    receiver = normalize_user_id(to_user_id)
    amount = _validate_amount(amount)
    if sender == receiver:
        raise ValueError("不能给自己转账")
    if isinstance(fee_rate, bool) or not isinstance(fee_rate, (int, float)) or fee_rate < 0:
        raise ValueError("手续费比例无效")
    fee = math.ceil(amount * float(fee_rate))
    total = amount + fee
    async with _lock:
        _load_locked()
        sender_balance = int(_balances.get(sender, 0))
        if sender_balance < total:
            raise InsufficientCreditsError("积分余额不足")
        before = dict(_balances)
        _balances[sender] = sender_balance - total
        _balances[receiver] = int(_balances.get(receiver, 0)) + amount
        try:
            await _persist_locked()
        except Exception:
            _balances.clear()
            _balances.update(before)
            raise
        return TransferResult(
            from_user_id=sender,
            to_user_id=receiver,
            amount=amount,
            fee=fee,
            sender_balance=_balances[sender],
            receiver_balance=_balances[receiver],
        )


async def migrate_legacy_accounts(legacy_accounts: dict) -> None:
    if not isinstance(legacy_accounts, dict):
        return
    async with _lock:
        _load_locked()
        if Path(MIGRATION_MARKER).exists():
            return
        before = dict(_balances)
        for user_id, account in legacy_accounts.items():
            if not isinstance(account, dict):
                continue
            try:
                normalized = normalize_user_id(user_id)
                old_balance = account.get("credits", 0)
                if isinstance(old_balance, bool):
                    continue
                old_balance = int(old_balance)
            except (TypeError, ValueError, OverflowError):
                continue
            if normalized not in _balances:
                _balances[normalized] = old_balance
        try:
            await _persist_locked()
            marker = Path(MIGRATION_MARKER)
            marker.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(marker.touch)
        except Exception:
            _balances.clear()
            _balances.update(before)
            raise


async def flush() -> None:
    async with _lock:
        _load_locked()
        if not Path(DATA_FILE).exists():
            await _persist_locked()


async def reset_for_tests() -> None:
    global _loaded_file, _load_failed
    async with _lock:
        _balances.clear()
        _loaded_file = None
        _load_failed = False
