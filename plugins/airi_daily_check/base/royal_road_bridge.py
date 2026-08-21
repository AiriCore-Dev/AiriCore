from __future__ import annotations

import asyncio
import os
import pickle
import tempfile
from pathlib import Path

from . import state
from .persistence import DATA_FILE, _atomic_dump, _save_lock


_settlement_ids: set[str] = set()
_bridge_lock = asyncio.Lock()
_receipt_path = Path(DATA_FILE).with_name("royal_road_settlements.pk")


def _load_receipts() -> set[str]:
    try:
        with _receipt_path.open("rb") as stream:
            value = pickle.load(stream)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return set(value)
    except Exception:
        return set()
    return set()


def _save_receipts(receipts: set[str]) -> None:
    _receipt_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=str(_receipt_path.parent), prefix=".royal-road-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            pickle.dump(sorted(receipts), stream, protocol=pickle.HIGHEST_PROTOCOL)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, _receipt_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


async def apply_royal_road_credit(user_id: str, amount: int, settlement_id: str) -> dict:
    user_id = str(user_id).strip()
    settlement_id = str(settlement_id).strip()
    if not settlement_id or len(settlement_id) > 160:
        raise ValueError("结算凭证无效")
    if isinstance(amount, bool) or not isinstance(amount, int) or not 0 <= amount <= 10000:
        raise ValueError("结算积分超出范围")
    async with _bridge_lock:
        if not _settlement_ids:
            _settlement_ids.update(await asyncio.to_thread(_load_receipts))
        if settlement_id in _settlement_ids:
            return {"status": "duplicate", "amount": amount}
        async with _save_lock:
            account = state.data.get(user_id)
            if account is None:
                _settlement_ids.add(settlement_id)
                await asyncio.to_thread(_save_receipts, _settlement_ids)
                return {"status": "unregistered", "amount": amount}
            account["credits"] = int(account.get("credits", 0)) + amount
            await asyncio.to_thread(_atomic_dump, DATA_FILE, state.data)
            _settlement_ids.add(settlement_id)
            await asyncio.to_thread(_save_receipts, _settlement_ids)
            return {"status": "applied", "amount": amount}
