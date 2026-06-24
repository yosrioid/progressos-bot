import re
from collections.abc import Mapping

SECRET_FIELD_PATTERN = re.compile(
    r"(api[_-]?key|authorization|bearer|secret|token|webhook[_-]?secret)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERN = re.compile(
    r"(?i)([A-Za-z0-9_]*token[A-Za-z0-9_]*=)[^,\s]+|"
    r"(bearer\s+)(?![A-Za-z0-9_]*token[A-Za-z0-9_]*=)[A-Za-z0-9._~+/-]+=*"
)
REDACTED = "[redacted]"


def redact_text(value: str) -> str:
    return SECRET_VALUE_PATTERN.sub(_replace_secret_value, value)


def redact_mapping(values: Mapping[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in values.items():
        if SECRET_FIELD_PATTERN.search(key):
            redacted[key] = REDACTED
            continue
        if isinstance(value, str):
            redacted[key] = redact_text(value)
            continue
        redacted[key] = value
    return redacted


def _replace_secret_value(match: re.Match[str]) -> str:
    if match.group(1):
        return f"{match.group(1)}{REDACTED}"
    if match.group(2):
        return f"{match.group(2)}{REDACTED}"
    return REDACTED
