from typing import Any


def parser_response_format(*, strict: bool) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "progressos_parser_response",
            "strict": strict,
            "schema": parser_response_json_schema(),
        },
    }


def parser_response_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "intent",
            "confidence",
            "language",
            "payload",
            "user_confirmation_text",
        ],
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "create_task",
                    "create_blocker",
                    "log_work",
                    "log_daily_progress",
                    "capture_learning",
                    "unsupported",
                ],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "language": {"type": "string", "enum": ["id", "en", "unknown"]},
            "payload": {
                "anyOf": [
                    _create_task_payload_schema(),
                    _create_blocker_payload_schema(),
                    _log_work_payload_schema(),
                    _log_daily_progress_payload_schema(),
                    _capture_learning_payload_schema(),
                    _unsupported_payload_schema(),
                ]
            },
            "user_confirmation_text": {
                "type": "string",
                "minLength": 5,
                "maxLength": 500,
            },
        },
    }


def _nullable_string(*, max_length: int) -> dict[str, Any]:
    return {"type": ["string", "null"], "maxLength": max_length}


def _nullable_date() -> dict[str, Any]:
    return {"type": ["string", "null"], "pattern": r"^\d{4}-\d{2}-\d{2}$"}


def _priority_schema() -> dict[str, Any]:
    return {"type": "string", "enum": ["low", "medium", "high", "urgent"]}


def _object_schema(
    *,
    required: list[str],
    properties: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def _create_task_payload_schema() -> dict[str, Any]:
    return _object_schema(
        required=["title", "description", "due_date", "priority"],
        properties={
            "title": {"type": "string", "minLength": 3, "maxLength": 180},
            "description": _nullable_string(max_length=2000),
            "due_date": _nullable_date(),
            "priority": _priority_schema(),
        },
    )


def _create_blocker_payload_schema() -> dict[str, Any]:
    return _object_schema(
        required=["title", "description", "severity"],
        properties={
            "title": {"type": "string", "minLength": 3, "maxLength": 180},
            "description": _nullable_string(max_length=2000),
            "severity": _priority_schema(),
        },
    )


def _log_work_payload_schema() -> dict[str, Any]:
    return _object_schema(
        required=[
            "title",
            "description",
            "date",
            "duration_minutes",
            "project_name",
        ],
        properties={
            "title": {"type": "string", "minLength": 3, "maxLength": 180},
            "description": _nullable_string(max_length=2000),
            "date": _nullable_date(),
            "duration_minutes": {"type": "integer", "minimum": 1, "maximum": 10000},
            "project_name": _nullable_string(max_length=120),
        },
    )


def _log_daily_progress_payload_schema() -> dict[str, Any]:
    return _object_schema(
        required=["title", "description", "date", "project_name"],
        properties={
            "title": {"type": "string", "minLength": 3, "maxLength": 180},
            "description": _nullable_string(max_length=2000),
            "date": _nullable_date(),
            "project_name": _nullable_string(max_length=120),
        },
    )


def _capture_learning_payload_schema() -> dict[str, Any]:
    return _object_schema(
        required=["title", "description", "date", "project_name"],
        properties={
            "title": {"type": "string", "minLength": 3, "maxLength": 180},
            "description": _nullable_string(max_length=2000),
            "date": _nullable_date(),
            "project_name": _nullable_string(max_length=120),
        },
    )


def _unsupported_payload_schema() -> dict[str, Any]:
    return _object_schema(
        required=["reason"],
        properties={
            "reason": {"type": "string", "minLength": 3, "maxLength": 300},
        },
    )
