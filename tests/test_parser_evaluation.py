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
    assert "expected intent create_task" in result.reason


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
