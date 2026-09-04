import asyncio
import pickle

import pytest

from utils import credits


def setup_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(credits, "DATA_FILE", tmp_path / "credits.pk")
    monkeypatch.setattr(credits, "MIGRATION_MARKER", tmp_path / "migration_v1")
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


def test_legacy_migration_is_idempotent(tmp_path, monkeypatch):
    setup_ledger(tmp_path, monkeypatch)
    legacy = {"1001": {"credits": 80}, "1002": {"credits": 0}}
    asyncio.run(credits.migrate_legacy_accounts(legacy))
    asyncio.run(credits.migrate_legacy_accounts(legacy))
    assert asyncio.run(credits.get_balance("1001")) == 80
    with (tmp_path / "credits.pk").open("rb") as stream:
        assert pickle.load(stream) == {"1001": 80, "1002": 0}


def test_existing_global_balance_is_not_duplicated(tmp_path, monkeypatch):
    setup_ledger(tmp_path, monkeypatch)
    asyncio.run(credits.credit("1001", 30))
    asyncio.run(credits.migrate_legacy_accounts({"1001": {"credits": 80}}))
    assert asyncio.run(credits.get_balance("1001")) == 30


def test_negative_legacy_balance_is_preserved_but_cannot_be_debited(tmp_path, monkeypatch):
    setup_ledger(tmp_path, monkeypatch)
    asyncio.run(credits.migrate_legacy_accounts({"1001": {"credits": -20}}))
    assert asyncio.run(credits.get_balance("1001")) == -20
    with pytest.raises(credits.InsufficientCreditsError):
        asyncio.run(credits.debit("1001", 1))


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
