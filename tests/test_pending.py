from datetime import UTC, datetime, timedelta

from progressos_bot.pending import InMemoryPendingActionStore
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
