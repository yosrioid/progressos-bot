import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from progressos_bot.schemas import Intent, Language, ParsedAction


class ParserEvaluationExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool = True
    intent: Intent | None = None
    language: Language | None = None
    payload_contains: dict[str, Any] = Field(default_factory=dict)


class ParserEvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    today: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    model_output: dict[str, Any]
    expected: ParserEvaluationExpectation


class ParserEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    passed: bool
    reason: str


class ParserEvaluationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    passed: int
    failed: int
    results: list[ParserEvaluationResult]


def load_evaluation_cases(path: Path) -> list[ParserEvaluationCase]:
    raw_cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_cases, list):
        raise ValueError("parser evaluation fixture must be a JSON array")
    return [ParserEvaluationCase.model_validate(raw_case) for raw_case in raw_cases]


def evaluate_cases(
    cases: list[ParserEvaluationCase],
    *,
    min_confidence: float = 0.75,
) -> ParserEvaluationSummary:
    results = [
        evaluate_case(case, min_confidence=min_confidence)
        for case in cases
    ]
    passed = sum(1 for result in results if result.passed)
    return ParserEvaluationSummary(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=results,
    )


def evaluate_case(
    case: ParserEvaluationCase,
    *,
    min_confidence: float = 0.75,
) -> ParserEvaluationResult:
    try:
        action = ParsedAction.model_validate(case.model_output)
    except ValidationError as exc:
        if not case.expected.valid:
            return ParserEvaluationResult(id=case.id, passed=True, reason="invalid as expected")
        return ParserEvaluationResult(id=case.id, passed=False, reason=str(exc))

    if not case.expected.valid:
        return ParserEvaluationResult(
            id=case.id,
            passed=False,
            reason="expected invalid output but validation passed",
        )
    if action.confidence < min_confidence:
        return ParserEvaluationResult(
            id=case.id,
            passed=False,
            reason=f"confidence {action.confidence:.2f} below {min_confidence:.2f}",
        )
    if case.expected.intent is not None and action.intent != case.expected.intent:
        return ParserEvaluationResult(
            id=case.id,
            passed=False,
            reason=f"expected intent {case.expected.intent}, got {action.intent}",
        )
    if case.expected.language is not None and action.language != case.expected.language:
        return ParserEvaluationResult(
            id=case.id,
            passed=False,
            reason=f"expected language {case.expected.language}, got {action.language}",
        )

    payload = action.model_dump(mode="json")["payload"]
    if not _contains_subset(payload, case.expected.payload_contains):
        return ParserEvaluationResult(
            id=case.id,
            passed=False,
            reason="payload did not contain expected fields",
        )

    return ParserEvaluationResult(id=case.id, passed=True, reason="ok")


def _contains_subset(value: object, expected: dict[str, Any]) -> bool:
    if not isinstance(value, dict):
        return False

    for key, expected_value in expected.items():
        if key not in value:
            return False
        actual_value = value[key]
        if isinstance(expected_value, dict):
            if not _contains_subset(actual_value, expected_value):
                return False
            continue
        if actual_value != expected_value:
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate offline parser output fixtures.")
    parser.add_argument("fixture", type=Path, help="Path to parser evaluation fixture JSON.")
    parser.add_argument("--min-confidence", type=float, default=0.75)
    args = parser.parse_args(argv)

    cases = load_evaluation_cases(args.fixture)
    summary = evaluate_cases(cases, min_confidence=args.min_confidence)
    print(summary.model_dump_json(indent=2))
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
