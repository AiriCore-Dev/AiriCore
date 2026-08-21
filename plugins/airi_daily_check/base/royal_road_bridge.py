from __future__ import annotations

import asyncio

from . import state
from .persistence import _save_lock


_settlement_ids: set[str] = set()
_bridge_lock = asyncio.Lock()


async def apply_royal_road_credit(user_id: str, amount: int, settlement_id: str) -> dict:
    user_id = str(user_id).strip()
    settlement_id = str(settlement_id).strip()
    if not settlement_id or len(settlement_id) > 160:
        raise ValueError("结算凭证无效")
    if isinstance(amount, bool) or not isinstance(amount, int) or not 0 <= amount <= 10000:
        raise ValueError("结算积分超出范围")
    async with _bridge_lock:
        if settlement_id in _settlement_ids:
            return {"status": "duplicate", "amount": amount}
        async with _save_lock:
            account = state.data.get(user_id)
            if account is None:
                _settlement_ids.add(settlement_id)
                return {"status": "unregistered", "amount": amount}
            account["credits"] = int(account.get("credits", 0)) + amount
            _settlement_ids.add(settlement_id)
            return {"status": "applied", "amount": amount}
