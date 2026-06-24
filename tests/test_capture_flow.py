from dataclasses import dataclass, field

import pytest

from progressos_bot.core.capture_flow import CaptureFlow
from progressos_bot.observability.metrics import InMemoryMetricsSink
from progressos_bot.pending import InMemoryPendingActionStore
from progressos_bot.schemas import (
    ParsedAction,
    ProgressOSActionRequest,
    ProgressOSActionResponse,
)


def make_action(intent: str = "create_task") -> ParsedAction:
    if intent == "unsupported":
        return ParsedAction.model_validate(
            {
                "intent": "unsupported",
                "confidence": 0.91,
                "language": "id",
                "payload": {"reason": "Tidak didukung"},
                "user_confirmation_text": "Input ini belum didukung.",
            }
        )

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


def make_blocker_action() -> ParsedAction:
    return ParsedAction.model_validate(
        {
            "intent": "create_blocker",
            "confidence": 0.94,
            "language": "id",
            "payload": {
                "title": "Blocked by missing API token",
                "description": "Butuh token API sebelum deploy.",
                "severity": "high",
            },
            "user_confirmation_text": "Catat blocker missing API token?",
        }
    )


@dataclass
class FakeParser:
    action: ParsedAction
    parsed_messages: list[str] = field(default_factory=list)

    async def parse(self, message: str) -> ParsedAction:
        self.parsed_messages.append(message)
        return self.action


@dataclass
class FakeProgressOS:
    submitted_requests: list[ProgressOSActionRequest] = field(default_factory=list)

    async def submit_action(self, request: ProgressOSActionRequest) -> ProgressOSActionResponse:
        self.submitted_requests.append(request)
        return ProgressOSActionResponse(message="Capture tersimpan.", record_path="/tasks/1")


def make_flow(
    *,
    action: ParsedAction | None = None,
    progressos: FakeProgressOS | None = None,
    enabled_intents: set[str] | None = None,
    max_input_chars: int = 2000,
) -> tuple[CaptureFlow, FakeParser, FakeProgressOS]:
    parser = FakeParser(action=action or make_action())
    client = progressos or FakeProgressOS()
    flow = CaptureFlow(
        parser=parser,
        progressos=client,
        pending=InMemoryPendingActionStore(ttl_seconds=60),
        correlation_id_factory=lambda: "corr-capture",
        enabled_intents=enabled_intents,
        max_input_chars=max_input_chars,
    )
    return flow, parser, client


def make_flow_with_metrics(
    *,
    action: ParsedAction | None = None,
) -> tuple[CaptureFlow, InMemoryMetricsSink]:
    metrics = InMemoryMetricsSink()
    parser = FakeParser(action=action or make_action())
    flow = CaptureFlow(
        parser=parser,
        progressos=FakeProgressOS(),
        pending=InMemoryPendingActionStore(ttl_seconds=60),
        correlation_id_factory=lambda: "corr-capture",
        metrics=metrics,
    )
    return flow, metrics


@pytest.mark.asyncio
async def test_begin_capture_stores_supported_action_without_telegram_classes() -> None:
    flow, parser, _client = make_flow()

    result = await flow.begin_capture(
        user_key="telegram:123",
        original_text="buat task follow up invoice client A",
    )

    assert result.status == "confirmation_required"
    assert result.user_message == "Buat task Follow up invoice client A?"
    assert result.correlation_id == "corr-capture"
    assert parser.parsed_messages == ["buat task follow up invoice client A"]


@pytest.mark.asyncio
async def test_capture_flow_records_supported_parse_and_confirmation_metrics() -> None:
    flow, metrics = make_flow_with_metrics()

    await flow.begin_capture(
        user_key="telegram:123",
        original_text="buat task follow up invoice client A",
    )

    assert metrics.count("capture_parse_total", outcome="supported") == 1
    assert metrics.count("capture_confirmation_total", outcome="requested") == 1


@pytest.mark.asyncio
async def test_begin_capture_rejects_too_long_input_before_parser() -> None:
    flow, parser, client = make_flow(max_input_chars=10)

    result = await flow.begin_capture(
        user_key="telegram:123",
        original_text="x" * 11,
    )
    submitted = await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert result.status == "unsupported"
    assert result.user_message == "Input terlalu panjang. Maksimal 10 karakter."
    assert parser.parsed_messages == []
    assert submitted.submitted is False
    assert client.submitted_requests == []


@pytest.mark.asyncio
async def test_capture_flow_records_too_long_input_metric() -> None:
    metrics = InMemoryMetricsSink()
    parser = FakeParser(action=make_action())
    flow = CaptureFlow(
        parser=parser,
        progressos=FakeProgressOS(),
        pending=InMemoryPendingActionStore(ttl_seconds=60),
        correlation_id_factory=lambda: "corr-capture",
        metrics=metrics,
        max_input_chars=10,
    )

    await flow.begin_capture(
        user_key="telegram:123",
        original_text="x" * 11,
    )

    assert parser.parsed_messages == []
    assert metrics.count("capture_parse_total", outcome="input_too_long") == 1
    assert metrics.count("capture_confirmation_total", outcome="requested") == 0


@pytest.mark.asyncio
async def test_begin_capture_returns_unsupported_without_pending_submit() -> None:
    flow, _parser, client = make_flow(action=make_action("unsupported"))

    result = await flow.begin_capture(
        user_key="telegram:123",
        original_text="hapus semua task",
    )
    submitted = await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert result.status == "unsupported"
    assert result.user_message == "Input ini belum didukung."
    assert submitted.submitted is False
    assert submitted.user_message == "Tidak ada draft aktif atau draft sudah kedaluwarsa."
    assert client.submitted_requests == []


@pytest.mark.asyncio
async def test_begin_capture_rejects_disabled_intent_without_pending_submit() -> None:
    flow, _parser, client = make_flow(enabled_intents={"log_work"})

    result = await flow.begin_capture(
        user_key="telegram:123",
        original_text="buat task follow up invoice client A",
    )
    submitted = await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert result.status == "unsupported"
    assert result.user_message == "Intent create_task sedang dinonaktifkan admin."
    assert submitted.submitted is False
    assert submitted.user_message == "Tidak ada draft aktif atau draft sudah kedaluwarsa."
    assert client.submitted_requests == []


@pytest.mark.asyncio
async def test_model_output_cannot_enable_disabled_intent() -> None:
    flow, parser, client = make_flow(
        action=make_blocker_action(),
        enabled_intents={"create_task"},
    )

    result = await flow.begin_capture(
        user_key="telegram:123",
        original_text="catat blocker deploy karena token API belum ada",
    )
    submitted = await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert parser.parsed_messages == ["catat blocker deploy karena token API belum ada"]
    assert result.status == "unsupported"
    assert result.user_message == "Intent create_blocker sedang dinonaktifkan admin."
    assert submitted.submitted is False
    assert submitted.user_message == "Tidak ada draft aktif atau draft sudah kedaluwarsa."
    assert client.submitted_requests == []


@pytest.mark.asyncio
async def test_capture_flow_records_unsupported_and_missing_draft_metrics() -> None:
    flow, metrics = make_flow_with_metrics(action=make_action("unsupported"))

    await flow.begin_capture(
        user_key="telegram:123",
        original_text="hapus semua task",
    )
    await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert metrics.count("capture_parse_total", outcome="unsupported") == 1
    assert metrics.count("capture_submit_total", outcome="missing_draft") == 1


@pytest.mark.asyncio
async def test_capture_flow_records_disabled_intent_metric() -> None:
    metrics = InMemoryMetricsSink()
    parser = FakeParser(action=make_action())
    flow = CaptureFlow(
        parser=parser,
        progressos=FakeProgressOS(),
        pending=InMemoryPendingActionStore(ttl_seconds=60),
        correlation_id_factory=lambda: "corr-capture",
        metrics=metrics,
        enabled_intents={"log_work"},
    )

    await flow.begin_capture(
        user_key="telegram:123",
        original_text="buat task follow up invoice client A",
    )

    assert metrics.count("capture_parse_total", outcome="disabled") == 1
    assert metrics.count("capture_confirmation_total", outcome="requested") == 0


@pytest.mark.asyncio
async def test_submit_confirmed_capture_sends_pending_action_to_progressos() -> None:
    flow, _parser, client = make_flow()
    await flow.begin_capture(
        user_key="telegram:123",
        original_text="buat task follow up invoice client A",
    )

    result = await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert result.submitted is True
    assert result.correlation_id == "corr-capture"
    assert result.user_message == "Capture tersimpan.\nLokasi: /tasks/1"
    assert len(client.submitted_requests) == 1
    request = client.submitted_requests[0]
    assert request.source == "telegram"
    assert request.source_user_id == "123"
    assert request.source_chat_id == "456"
    assert request.progressos_user_id == "77"
    assert request.original_text == "buat task follow up invoice client A"


@pytest.mark.asyncio
async def test_capture_flow_records_submit_success_metric() -> None:
    flow, metrics = make_flow_with_metrics()
    await flow.begin_capture(
        user_key="telegram:123",
        original_text="buat task follow up invoice client A",
    )

    await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert metrics.count("capture_submit_total", outcome="success") == 1


@pytest.mark.asyncio
async def test_cancel_capture_discards_pending_action() -> None:
    flow, _parser, client = make_flow()
    await flow.begin_capture(
        user_key="telegram:123",
        original_text="buat task follow up invoice client A",
    )

    flow.cancel_capture(user_key="telegram:123")
    result = await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert result.submitted is False
    assert result.user_message == "Tidak ada draft aktif atau draft sudah kedaluwarsa."
    assert client.submitted_requests == []


@pytest.mark.asyncio
async def test_cancel_capture_records_metric() -> None:
    flow, metrics = make_flow_with_metrics()

    flow.cancel_capture(user_key="telegram:123")

    assert metrics.count("capture_confirmation_total", outcome="cancelled") == 1
