from datetime import time
import re


def match_validator(pattern: re.Pattern, explanation: str | None = None):
    def validator(value: str):
        assert (value is None or pattern.match(value)), (explanation or f"Value does not match {pattern!r} pattern")
        return value

    return validator


def time_validator(value: str):
    try:
        hours, minutes = value.split(':')
    except ValueError:
        raise ValueError('Time should be in 24 hour format like "18:00"')
    else:
        try:
            time(int(hours), int(minutes))
        except TypeError:
            raise ValueError('Time should be in 24 hour format like "18:00"')
    return value
