from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol


class MetricsSink(Protocol):
    def increment(self, name: str, **labels: str) -> None: ...


class NoopMetricsSink:
    def increment(self, name: str, **labels: str) -> None:
        del name, labels


@dataclass
class InMemoryMetricsSink:
    counters: Counter[tuple[str, tuple[tuple[str, str], ...]]] = field(default_factory=Counter)

    def increment(self, name: str, **labels: str) -> None:
        normalized_labels = tuple(sorted(labels.items()))
        self.counters[(name, normalized_labels)] += 1

    def count(self, name: str, **labels: str) -> int:
        normalized_labels = tuple(sorted(labels.items()))
        return self.counters[(name, normalized_labels)]
