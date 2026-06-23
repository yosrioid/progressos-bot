import json
from pathlib import Path

from progressos_bot.ai.evaluation import (
    ParserEvaluationCase,
    evaluate_case,
    evaluate_cases,
    load_evaluation_cases,
    main,
)


def test_parser_evaluation_fixture_passes() -> None:
    cases = load_evaluation_cases(Path("tests/fixtures/parser_evaluation.json"))

    summary = evaluate_cases(cases)

    assert summary.total == 5
    assert summary.failed == 0
    assert summary.by_intent["create_task"].passed == 1
    assert summary.by_intent["log_work"].passed == 1
    assert summary.by_intent["unsupported"].passed == 2
    assert summary.by_language["id"].passed == 2
    assert summary.by_language["en"].passed == 2


def test_parser_evaluation_reports_wrong_intent() -> None:
    case = ParserEvaluationCase.model_validate(
        {
            "id": "wrong-intent",
            "message": "buat task follow up invoice",
            "today": "2026-06-23",
            "model_output": {
                "intent": "unsupported",
                "confidence": 0.9,
                "language": "id",
                "payload": {"reason": "Tidak didukung."},
                "user_confirmation_text": "Input ini belum didukung.",
            },
            "expected": {"intent": "create_task"},
        }
    )

    result = evaluate_case(case)

    assert result.passed is False
    assert result.intent == "create_task"
    assert result.language == "id"
    assert result.failure_category == "intent_mismatch"
    assert "expected intent create_task" in result.reason


def test_parser_evaluation_summary_counts_failure_categories() -> None:
    case = ParserEvaluationCase.model_validate(
        {
            "id": "wrong-payload",
            "message": "buat task follow up invoice",
            "today": "2026-06-23",
            "model_output": {
                "intent": "create_task",
                "confidence": 0.9,
                "language": "id",
                "payload": {
                    "title": "Follow up invoice",
                    "description": None,
                    "due_date": None,
                    "priority": "medium",
                },
                "user_confirmation_text": "Buat task Follow up invoice?",
            },
            "expected": {
                "intent": "create_task",
                "language": "id",
                "payload_contains": {"priority": "urgent"},
            },
        }
    )

    summary = evaluate_cases([case])

    assert summary.failed == 1
    assert summary.by_intent["create_task"].failed == 1
    assert summary.by_language["id"].failed == 1
    assert summary.by_failure_category == {"payload_mismatch": 1}


def test_parser_evaluation_cli_returns_zero_for_passing_fixture(
    tmp_path: Path,
    capsys: object,
) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "id": "unsupported",
                    "message": "hapus semua data",
                    "today": "2026-06-23",
                    "model_output": {
                        "intent": "unsupported",
                        "confidence": 0.9,
                        "language": "id",
                        "payload": {"reason": "Permintaan tidak didukung."},
                        "user_confirmation_text": "Input ini belum didukung.",
                    },
                    "expected": {"intent": "unsupported"},
                }
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main([str(fixture)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"failed": 0' in captured.out
    assert '"by_intent"' in captured.out
    assert '"by_language"' in captured.out
