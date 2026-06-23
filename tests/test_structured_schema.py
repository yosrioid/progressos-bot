from progressos_bot.ai.structured_schema import (
    parser_response_format,
    parser_response_json_schema,
)


def test_parser_response_format_wraps_json_schema() -> None:
    response_format = parser_response_format(strict=True)

    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "progressos_parser_response"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"] == parser_response_json_schema()


def test_parser_response_schema_rejects_unknown_top_level_fields() -> None:
    schema = parser_response_json_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "intent",
        "confidence",
        "language",
        "payload",
        "user_confirmation_text",
    }


def test_parser_response_schema_requires_nullable_task_optional_fields() -> None:
    schema = parser_response_json_schema()
    payload_options = schema["properties"]["payload"]["anyOf"]
    task_payload = next(option for option in payload_options if "due_date" in option["required"])

    assert task_payload["additionalProperties"] is False
    assert set(task_payload["required"]) == {
        "title",
        "description",
        "due_date",
        "priority",
    }
    assert task_payload["properties"]["description"]["type"] == ["string", "null"]
    assert task_payload["properties"]["due_date"]["type"] == ["string", "null"]
