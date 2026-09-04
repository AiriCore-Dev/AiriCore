import asyncio

import nonebot

from utils import credits

nonebot.init()

from plugins.airi_llm import plan


def test_purchase_plan_uses_global_credit_balance(tmp_path, monkeypatch):
    monkeypatch.setattr(credits, "DATA_FILE", tmp_path / "credits.pk")
    monkeypatch.setattr(credits, "MIGRATION_MARKER", tmp_path / "migration_v1")
    asyncio.run(credits.reset_for_tests())
    asyncio.run(credits.credit("1001", 2000))
    result = asyncio.run(plan.purchase_plan_with_credits("1001", {}, "12345", "日卡"))
    assert result.cost == 2000
    assert asyncio.run(credits.get_balance("1001")) == 0
