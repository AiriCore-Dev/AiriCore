from __future__ import annotations

import asyncio
import os
import pickle
import tempfile
from pathlib import Path

from utils import credits


_settlement_ids: dict[str, dict] = {}
_bridge_lock = asyncio.Lock()
_receipt_path = Path(credits.DATA_FILE).with_name("royal_road_settlements.pk")


def _load_receipts() -> dict[str, dict]:
    try:
        with _receipt_path.open("rb") as stream:
            value = pickle.load(stream)
    except FileNotFoundError:
        return {}
    except Exception as exc:
        raise RuntimeError("王道结算凭证损坏，已停止入账") from exc
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return {item: {"status": "applied"} for item in value}
    if not isinstance(value, dict):
        raise RuntimeError("王道结算凭证结构无效，已停止入账")
    for key, record in value.items():
        if not isinstance(key, str) or not isinstance(record, dict) or record.get("status") not in {"pending", "applied"}:
            raise RuntimeError("王道结算凭证结构无效，已停止入账")
    return value


def _save_receipts(receipts: dict[str, dict]) -> None:
    _receipt_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=str(_receipt_path.parent), prefix=".royal-road-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            pickle.dump(receipts, stream, protocol=pickle.HIGHEST_PROTOCOL)
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
        record = _settlement_ids.get(settlement_id)
        if record is not None and record.get("status") == "applied":
            return {"status": "duplicate", "amount": amount}
        if not await credits.has_account(user_id):
            return {"status": "unregistered", "amount": amount}
        current = await credits.get_balance(user_id)
        if record is not None:
            if record.get("user_id") != user_id or record.get("amount") != amount:
                raise RuntimeError("王道结算凭证与待处理事务不匹配")
            before = int(record["before"])
            after = int(record["after"])
            if current == after:
                applied = {**record, "status": "applied"}
                receipts = {**_settlement_ids, settlement_id: applied}
                await asyncio.to_thread(_save_receipts, receipts)
                _settlement_ids.clear()
                _settlement_ids.update(receipts)
                return {"status": "duplicate", "amount": amount}
            if current != before:
                raise RuntimeError("王道结算待处理事务需要人工核对")
        else:
            before = current
            after = current + amount
            record = {"status": "pending", "user_id": user_id, "amount": amount, "before": before, "after": after}
            receipts = {**_settlement_ids, settlement_id: record}
            await asyncio.to_thread(_save_receipts, receipts)
            _settlement_ids.clear()
            _settlement_ids.update(receipts)
        if amount:
            await credits.credit(user_id, amount)
        applied = {**record, "status": "applied"}
        receipts = {**_settlement_ids, settlement_id: applied}
        await asyncio.to_thread(_save_receipts, receipts)
        _settlement_ids.clear()
        _settlement_ids.update(receipts)
        return {"status": "applied", "amount": amount}
