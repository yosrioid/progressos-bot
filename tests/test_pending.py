from datetime import UTC, datetime, timedelta

from progressos_bot.pending import InMemoryPendingActionStore, SQLitePendingActionStore
from progressos_bot.schemas import ParsedAction


def make_action() -> ParsedAction:
    return ParsedAction.model_validate(
        {
            "intent": "create_task",
            "confidence": 0.91,
            "language": "id",
            "payload": {
                "title": "Follow up invoice client A",
                "description": "Kirim invoice ulang",
                "due_date": "2026-06-21",
                "priority": "high",
            },
            "user_confirmation_text": "Buat task Follow up invoice client A?",
        }
    )


def test_pending_action_store_returns_active_pending_action() -> None:
    now = datetime(2026, 6, 22, 9, 15, tzinfo=UTC)
    store = InMemoryPendingActionStore(ttl_seconds=60, clock=lambda: now)
    action = make_action()

    store.put("123", "buat task follow up invoice client A", action)
    pending = store.pop("123")

    assert pending is not None
    assert pending.original_text == "buat task follow up invoice client A"
    assert pending.parsed_action == action
    assert pending.expires_at == now + timedelta(seconds=60)
    assert store.pop("123") is None


def test_pending_action_store_drops_expired_pending_action() -> None:
    current_time = datetime(2026, 6, 22, 9, 15, tzinfo=UTC)

    def clock() -> datetime:
        return current_time

    store = InMemoryPendingActionStore(ttl_seconds=60, clock=clock)
    store.put("123", "buat task follow up invoice client A", make_action())
    current_time = current_time + timedelta(seconds=61)

    assert store.pop("123") is None


def test_pending_action_store_discards_pending_action() -> None:
    store = InMemoryPendingActionStore(
        ttl_seconds=60,
        clock=lambda: datetime(2026, 6, 22, 9, 15, tzinfo=UTC),
    )
    store.put("123", "buat task follow up invoice client A", make_action())

    store.discard("123")

    assert store.pop("123") is None


def test_sqlite_pending_action_store_rehydrates_pending_action(tmp_path) -> None:
    now = datetime(2026, 6, 22, 9, 15, tzinfo=UTC)
    path = tmp_path / "pending.sqlite3"
    action = make_action()
    first_store = SQLitePendingActionStore(
        path=str(path),
        ttl_seconds=60,
        clock=lambda: now,
    )
    first_store.put("123", "buat task follow up invoice client A", action)

    second_store = SQLitePendingActionStore(
        path=str(path),
        ttl_seconds=60,
        clock=lambda: now + timedelta(seconds=30),
    )
    pending = second_store.pop("123")

    assert pending is not None
    assert pending.original_text == "buat task follow up invoice client A"
    assert pending.parsed_action == action
    assert pending.expires_at == now + timedelta(seconds=60)
    assert second_store.pop("123") is None


def test_sqlite_pending_action_store_drops_expired_pending_action(tmp_path) -> None:
    now = datetime(2026, 6, 22, 9, 15, tzinfo=UTC)
    path = tmp_path / "pending.sqlite3"
    first_store = SQLitePendingActionStore(
        path=str(path),
        ttl_seconds=60,
        clock=lambda: now,
    )
    first_store.put("123", "buat task follow up invoice client A", make_action())

    second_store = SQLitePendingActionStore(
        path=str(path),
        ttl_seconds=60,
        clock=lambda: now + timedelta(seconds=61),
    )

    assert second_store.pop("123") is None
    assert second_store.pop("123") is None
