from datetime import time
import re

from pydantic import HttpUrl

__all__ = ["match_validator", "time_validator", "https_only_check", "email_validator"]


def match_validator(pattern: re.Pattern, explanation: str | None = None):
    def validator(value: str):
        assert (value is None or pattern.match(value)), (explanation or f"Value does not match {pattern!r} pattern")
        return value

    return validator


def time_validator(value: str):
    """Always return in the format HH:MM."""
    try:
        hours, minutes = value.split(':')
    except ValueError:
        raise ValueError('Time should be in 24 hour format like "18:00"')

    try:
        time(int(hours), int(minutes))
    except TypeError:
        raise ValueError('Time should be in 24 hour format like "18:00"')

    # pad hours and minutes with zeros (e.g. "1:00" -> "01:00")
    # allows for easier time comparison since "9" > "10" but "09" < "10"
    return ':'.join(digits.rjust(2, '0') for digits in (hours, minutes))


def https_only_check(url: HttpUrl) -> str:
    if url.scheme != 'https':
        raise ValueError('URL scheme must be https')
    return str(url)


def email_validator(value: str):
    # https://www.rfc-editor.org/rfc/rfc5321#section-4.5.3.1.3
    # (subtract 2 because path portion of email is separated
    # by enclosing "<" which we cannot control)
    max_path = 254

    if not value:
        return value

    if len(value) > max_path:
        raise ValueError(f"Maximum length is {max_path} characters.")

    right_most_atsign = value.rfind("@")
    if right_most_atsign == -1:
        raise ValueError("Missing '@' symbol.")

    # The email validation/RFC debacle is a vortex of endless
    # despair. There have been erratas for the erratas to "fix"
    # the email address issues but it's still very much a source of
    # debate. It's actually gotten to a point where most interwebz
    # people claim that validating email addresses more than the
    # bare minimum is only harmful. I tend to agree with them because
    # each email server implementation follows their own set of rules.
    # This means NO MATTER WHAT WE DO, we're bound to still allow an
    # "invalid" email address depending on the email server being
    # used. It's better to be false-positive than false-negative here.
    # The only guaranteed way to "validate" an email address is to send
    # a test email to the given address.
    local_part = value[:right_most_atsign]
    if not local_part:
        raise ValueError("Missing local part of email string (part before the '@').")

    domain_part = value[right_most_atsign:]
    if domain_part == '@':
        raise ValueError("Missing domain part of email string (part after the '@').")

    return value
