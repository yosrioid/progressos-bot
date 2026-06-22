from progressos_bot.observability.metrics import InMemoryMetricsSink, NoopMetricsSink


def test_in_memory_metrics_sink_counts_by_name_and_labels() -> None:
    metrics = InMemoryMetricsSink()

    metrics.increment("capture_submit_total", outcome="success")
    metrics.increment("capture_submit_total", outcome="success")
    metrics.increment("capture_submit_total", outcome="missing_draft")

    assert metrics.count("capture_submit_total", outcome="success") == 2
    assert metrics.count("capture_submit_total", outcome="missing_draft") == 1
    assert metrics.count("capture_submit_total", outcome="validation_error") == 0


def test_noop_metrics_sink_accepts_counters_without_storing() -> None:
    metrics = NoopMetricsSink()

    metrics.increment("capture_parse_total", outcome="supported")
