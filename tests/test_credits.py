import asyncio

import pytest

from utils import credits


def setup_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(credits, "DATA_FILE", tmp_path / "credits.pk")
    asyncio.run(credits.reset_for_tests())


def test_credit_service_shares_balance_across_calls(tmp_path, monkeypatch):
    setup_ledger(tmp_path, monkeypatch)
    assert asyncio.run(credits.get_balance("1001")) == 0
    assert asyncio.run(credits.credit("1001", 120)) == 120
    assert asyncio.run(credits.get_balance("1001")) == 120


def test_debit_rejects_insufficient_balance(tmp_path, monkeypatch):
    setup_ledger(tmp_path, monkeypatch)
    with pytest.raises(credits.InsufficientCreditsError):
        asyncio.run(credits.debit("1001", 1))


def test_transfer_updates_both_users_and_charges_fee(tmp_path, monkeypatch):
    setup_ledger(tmp_path, monkeypatch)
    asyncio.run(credits.credit("1001", 200))
    result = asyncio.run(credits.transfer("1001", "1002", 100))
    assert result.amount == 100
    assert result.fee == 10
    assert result.sender_balance == 90
    assert asyncio.run(credits.get_balance("1002")) == 100


def test_failed_persist_rolls_back_balance(tmp_path, monkeypatch):
    setup_ledger(tmp_path, monkeypatch)
    original = credits._atomic_dump

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(credits, "_atomic_dump", fail)
    with pytest.raises(OSError):
        asyncio.run(credits.credit("1001", 20))
    assert asyncio.run(credits.get_balance("1001")) == 0
    monkeypatch.setattr(credits, "_atomic_dump", original)
