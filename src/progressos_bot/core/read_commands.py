from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from progressos_bot.observability.correlation import CorrelationIdFactory
from progressos_bot.observability.metrics import MetricsSink, NoopMetricsSink
from progressos_bot.schemas import (
    ProgressOSDashboardResponse,
    ProgressOSKanbanResponse,
    ProgressOSLearningStatsResponse,
    ProgressOSOverdueResponse,
    ProgressOSSearchResponse,
    ProgressOSStandupResponse,
)


class ProgressOSReadClient(Protocol):
    async def get_standup(self) -> ProgressOSStandupResponse: ...

    async def get_dashboard(self) -> ProgressOSDashboardResponse: ...

    async def search(self, query: str) -> ProgressOSSearchResponse: ...

    async def get_overdue(self) -> ProgressOSOverdueResponse: ...

    async def get_kanban(self) -> ProgressOSKanbanResponse: ...

    async def get_learning_stats(self) -> ProgressOSLearningStatsResponse: ...


@dataclass(frozen=True)
class ReadCommandResult:
    user_message: str
    correlation_id: str


class ReadCommandFlow:
    def __init__(
        self,
        *,
        progressos: ProgressOSReadClient,
        correlation_id_factory: Callable[[], str] | None = None,
        metrics: MetricsSink | None = None,
    ) -> None:
        self._progressos = progressos
        self._new_correlation_id = correlation_id_factory or CorrelationIdFactory().new
        self._metrics = metrics or NoopMetricsSink()

    async def standup(self) -> ReadCommandResult:
        response = await self._progressos.get_standup()
        self._metrics.increment("read_command_total", command="standup", outcome="success")
        return ReadCommandResult(
            user_message=response.to_user_message(),
            correlation_id=self._new_correlation_id(),
        )

    async def dashboard(self) -> ReadCommandResult:
        response = await self._progressos.get_dashboard()
        self._metrics.increment("read_command_total", command="dashboard", outcome="success")
        return ReadCommandResult(
            user_message=response.to_user_message(),
            correlation_id=self._new_correlation_id(),
        )

    async def search(self, *, query: str) -> ReadCommandResult:
        response = await self._progressos.search(query)
        self._metrics.increment("read_command_total", command="search", outcome="success")
        return ReadCommandResult(
            user_message=response.to_user_message(),
            correlation_id=self._new_correlation_id(),
        )

    async def overdue(self) -> ReadCommandResult:
        response = await self._progressos.get_overdue()
        self._metrics.increment("read_command_total", command="overdue", outcome="success")
        return ReadCommandResult(
            user_message=response.to_user_message(),
            correlation_id=self._new_correlation_id(),
        )

    async def kanban(self) -> ReadCommandResult:
        response = await self._progressos.get_kanban()
        self._metrics.increment("read_command_total", command="kanban", outcome="success")
        return ReadCommandResult(
            user_message=response.to_user_message(),
            correlation_id=self._new_correlation_id(),
        )

    async def learning_stats(self) -> ReadCommandResult:
        response = await self._progressos.get_learning_stats()
        self._metrics.increment(
            "read_command_total",
            command="learning_stats",
            outcome="success",
        )
        return ReadCommandResult(
            user_message=response.to_user_message(),
            correlation_id=self._new_correlation_id(),
        )
