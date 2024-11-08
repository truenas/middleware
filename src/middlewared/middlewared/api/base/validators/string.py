import re

__all__ = ["match_validator"]


def match_validator(pattern: re.Pattern, explanation: str | None = None):
    def validator(value: str):
        assert (value is None or pattern.match(value)), (explanation or f"Value does not match {pattern!r} pattern")

    return validator
