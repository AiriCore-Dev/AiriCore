from pathlib import Path


def test_daily_check_handlers_do_not_use_credit_field_as_authority():
    root = Path("plugins/airi_daily_check")
    for path in root.rglob("*.py"):
        if path.name in {"constants.py", "persistence.py"}:
            continue
        source = path.read_text()
        assert "state.data[user_id]['credits']" not in source
        assert 'state.data[user_id]["credits"]' not in source

