import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from progressos_bot.schemas import ParsedAction


@dataclass(frozen=True)
class PendingAction:
    original_text: str
    parsed_action: ParsedAction
    expires_at: datetime


class PendingActionStore(Protocol):
    def put(self, user_key: str, original_text: str, parsed_action: ParsedAction) -> None: ...

    def discard(self, user_key: str) -> None: ...

    def pop(self, user_key: str) -> PendingAction | None: ...


class InMemoryPendingActionStore:
    def __init__(
        self,
        *,
        ttl_seconds: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._ttl = timedelta(seconds=max(1, ttl_seconds))
        self._clock = clock or self._utc_now
        self._pending: dict[str, PendingAction] = {}

    def put(self, user_key: str, original_text: str, parsed_action: ParsedAction) -> None:
        self._pending[user_key] = PendingAction(
            original_text=original_text,
            parsed_action=parsed_action,
            expires_at=self._now() + self._ttl,
        )

    def discard(self, user_key: str) -> None:
        self._pending.pop(user_key, None)

    def pop(self, user_key: str) -> PendingAction | None:
        pending = self._pending.pop(user_key, None)
        if pending is None:
            return None
        if pending.expires_at <= self._now():
            return None
        return pending

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)


class SQLitePendingActionStore:
    def __init__(
        self,
        *,
        path: str,
        ttl_seconds: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        store_path = Path(path).expanduser()
        self._path = str(store_path)
        self._ttl = timedelta(seconds=max(1, ttl_seconds))
        self._clock = clock or self._utc_now
        store_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def put(self, user_key: str, original_text: str, parsed_action: ParsedAction) -> None:
        expires_at = self._now() + self._ttl
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pending_actions (
                    user_key,
                    original_text,
                    parsed_action_json,
                    expires_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(user_key) DO UPDATE SET
                    original_text = excluded.original_text,
                    parsed_action_json = excluded.parsed_action_json,
                    expires_at = excluded.expires_at
                """,
                (
                    user_key,
                    original_text,
                    parsed_action.model_dump_json(),
                    self._format_datetime(expires_at),
                ),
            )

    def discard(self, user_key: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM pending_actions WHERE user_key = ?", (user_key,))

    def pop(self, user_key: str) -> PendingAction | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT original_text, parsed_action_json, expires_at
                FROM pending_actions
                WHERE user_key = ?
                """,
                (user_key,),
            ).fetchone()
            connection.execute("DELETE FROM pending_actions WHERE user_key = ?", (user_key,))

        if row is None:
            return None

        expires_at = self._parse_datetime(row["expires_at"])
        if expires_at <= self._now():
            return None

        return PendingAction(
            original_text=row["original_text"],
            parsed_action=ParsedAction.model_validate_json(row["parsed_action_json"]),
            expires_at=expires_at,
        )

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_actions (
                    user_key TEXT PRIMARY KEY,
                    original_text TEXT NOT NULL,
                    parsed_action_json TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
