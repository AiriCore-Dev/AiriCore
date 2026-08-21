from __future__ import annotations

import asyncio

from plugins.airi_daily_check.base.royal_road_bridge import apply_royal_road_credit


class SettlementService:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._records: dict[str, dict] = {}

    async def settle(self, user_id: str, total_emblems: int, settlement_id: str) -> dict:
        if total_emblems < 0:
            raise ValueError("累计徽记不能为负")
        amount = min(total_emblems // 10, 10000)
        async with self._lock:
            record = self._records.setdefault(str(user_id), {"total_emblems": total_emblems, "amount": amount, "settlement_id": settlement_id, "status": "pending"})
            if record["status"] == "applied":
                return dict(record)
            result = await apply_royal_road_credit(str(user_id), amount, settlement_id)
            record["status"] = result["status"]
            return {**record, **result}


settlement_service = SettlementService()
