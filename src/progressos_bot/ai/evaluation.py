import argparse
import json
from pathlib import Path
from typing import Any, Literal

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
    risk_category: str = Field(default="general", min_length=1)
    message: str = Field(min_length=1)
    today: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    model_output: dict[str, Any]
    expected: ParserEvaluationExpectation


class ParserEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    passed: bool
    risk_category: str
    intent: str
    language: str
    failure_category: str | None = None
    reason: str


class ParserEvaluationBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = 0
    passed: int = 0
    failed: int = 0


class ParserEvaluationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    passed: int
    failed: int
    by_intent: dict[str, ParserEvaluationBreakdown]
    by_language: dict[str, ParserEvaluationBreakdown]
    by_risk_category: dict[str, ParserEvaluationBreakdown]
    by_failure_category: dict[str, int]
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
    results = [evaluate_case(case, min_confidence=min_confidence) for case in cases]
    passed = sum(1 for result in results if result.passed)
    return ParserEvaluationSummary(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        by_intent=_breakdown_by(results, key="intent"),
        by_language=_breakdown_by(results, key="language"),
        by_risk_category=_breakdown_by(results, key="risk_category"),
        by_failure_category=_failure_breakdown(results),
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
            return _result(
                case,
                passed=True,
                reason="invalid as expected",
            )
        return _result(
            case,
            passed=False,
            failure_category="validation_error",
            reason=str(exc),
        )

    if not case.expected.valid:
        return _result(
            case,
            passed=False,
            action=action,
            failure_category="unexpected_valid_output",
            reason="expected invalid output but validation passed",
        )
    if action.confidence < min_confidence:
        return _result(
            case,
            passed=False,
            action=action,
            failure_category="low_confidence",
            reason=f"confidence {action.confidence:.2f} below {min_confidence:.2f}",
        )
    if case.expected.intent is not None and action.intent != case.expected.intent:
        return _result(
            case,
            passed=False,
            action=action,
            failure_category="intent_mismatch",
            reason=f"expected intent {case.expected.intent}, got {action.intent}",
        )
    if case.expected.language is not None and action.language != case.expected.language:
        return _result(
            case,
            passed=False,
            action=action,
            failure_category="language_mismatch",
            reason=f"expected language {case.expected.language}, got {action.language}",
        )

    payload = action.model_dump(mode="json")["payload"]
    if not _contains_subset(payload, case.expected.payload_contains):
        return _result(
            case,
            passed=False,
            action=action,
            failure_category="payload_mismatch",
            reason="payload did not contain expected fields",
        )

    return _result(case, passed=True, action=action, reason="ok")


def _result(
    case: ParserEvaluationCase,
    *,
    passed: bool,
    reason: str,
    action: ParsedAction | None = None,
    failure_category: str | None = None,
) -> ParserEvaluationResult:
    return ParserEvaluationResult(
        id=case.id,
        passed=passed,
        risk_category=case.risk_category,
        intent=_result_intent(case, action),
        language=_result_language(case, action),
        failure_category=failure_category,
        reason=reason,
    )


def _result_intent(case: ParserEvaluationCase, action: ParsedAction | None) -> str:
    if case.expected.intent is not None:
        return case.expected.intent
    if action is not None:
        return action.intent
    return "unknown"


def _result_language(case: ParserEvaluationCase, action: ParsedAction | None) -> str:
    if case.expected.language is not None:
        return case.expected.language
    if action is not None:
        return action.language
    return "unknown"


def _breakdown_by(
    results: list[ParserEvaluationResult],
    *,
    key: Literal["intent", "language", "risk_category"],
) -> dict[str, ParserEvaluationBreakdown]:
    breakdown: dict[str, ParserEvaluationBreakdown] = {}
    for result in results:
        bucket_key = _breakdown_key(result, key)
        bucket = breakdown.setdefault(bucket_key, ParserEvaluationBreakdown())
        bucket.total += 1
        if result.passed:
            bucket.passed += 1
        else:
            bucket.failed += 1
    return breakdown


def _breakdown_key(
    result: ParserEvaluationResult,
    key: Literal["intent", "language", "risk_category"],
) -> str:
    if key == "intent":
        return result.intent
    if key == "language":
        return result.language
    return result.risk_category


def _failure_breakdown(results: list[ParserEvaluationResult]) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for result in results:
        if result.failure_category is None:
            continue
        breakdown[result.failure_category] = breakdown.get(result.failure_category, 0) + 1
    return breakdown


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
