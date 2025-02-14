from datetime import time
import re

from pydantic import HttpUrl

from .validators_.passwd_complexity import passwd_complexity_validator

__all__ = ["match_validator", "time_validator", "passwd_complexity_validator",]


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


def https_only_check(url: HttpUrl) -> str:
    if url.scheme != 'https':
        raise ValueError('URL scheme must be https')
    return str(url)
