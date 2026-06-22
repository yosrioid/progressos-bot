from dataclasses import dataclass, field

import pytest

from progressos_bot.core.read_commands import ReadCommandFlow
from progressos_bot.observability.metrics import InMemoryMetricsSink
from progressos_bot.schemas import (
    ProgressOSDashboardResponse,
    ProgressOSKanbanResponse,
    ProgressOSLearningStatsResponse,
    ProgressOSOverdueResponse,
    ProgressOSSearchResponse,
    ProgressOSStandupResponse,
)


@dataclass
class FakeProgressOSReadClient:
    calls: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)

    async def get_standup(self) -> ProgressOSStandupResponse:
        self.calls.append("standup")
        return ProgressOSStandupResponse(message="Standup kosong", items=[])

    async def get_dashboard(self) -> ProgressOSDashboardResponse:
        self.calls.append("dashboard")
        return ProgressOSDashboardResponse(message="Dashboard siap")

    async def search(self, query: str) -> ProgressOSSearchResponse:
        self.calls.append("search")
        self.search_queries.append(query)
        return ProgressOSSearchResponse(message="Hasil pencarian", results=[])

    async def get_overdue(self) -> ProgressOSOverdueResponse:
        self.calls.append("overdue")
        return ProgressOSOverdueResponse(message="Tidak ada overdue", tasks=[])

    async def get_kanban(self) -> ProgressOSKanbanResponse:
        self.calls.append("kanban")
        return ProgressOSKanbanResponse(message="Kanban kosong")

    async def get_learning_stats(self) -> ProgressOSLearningStatsResponse:
        self.calls.append("learning_stats")
        return ProgressOSLearningStatsResponse(message="Belum ada learning")


@pytest.mark.asyncio
async def test_read_command_flow_returns_standup_message_without_telegram_classes() -> None:
    client = FakeProgressOSReadClient()
    metrics = InMemoryMetricsSink()
    flow = ReadCommandFlow(
        progressos=client,
        correlation_id_factory=lambda: "corr-read",
        metrics=metrics,
    )

    result = await flow.standup()

    assert result.user_message == "Standup kosong"
    assert result.correlation_id == "corr-read"
    assert client.calls == ["standup"]
    assert metrics.count("read_command_total", command="standup", outcome="success") == 1


@pytest.mark.asyncio
async def test_read_command_flow_passes_search_query() -> None:
    client = FakeProgressOSReadClient()
    flow = ReadCommandFlow(progressos=client)

    result = await flow.search(query="invoice")

    assert result.user_message == "Hasil pencarian"
    assert client.calls == ["search"]
    assert client.search_queries == ["invoice"]


@pytest.mark.asyncio
async def test_read_command_flow_wraps_remaining_read_commands() -> None:
    client = FakeProgressOSReadClient()
    flow = ReadCommandFlow(progressos=client)

    dashboard = await flow.dashboard()
    overdue = await flow.overdue()
    kanban = await flow.kanban()
    learning_stats = await flow.learning_stats()

    assert dashboard.user_message == "Dashboard siap"
    assert overdue.user_message == "Tidak ada overdue"
    assert kanban.user_message == "Kanban kosong"
    assert learning_stats.user_message == "Belum ada learning"
    assert client.calls == ["dashboard", "overdue", "kanban", "learning_stats"]
