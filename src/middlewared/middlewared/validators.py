import ipaddress
import re

from datetime import time
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class ShouldBe(Exception):
    def __init__(self, what):
        self.what = what


class Email:
    def __call__(self, value):
        try:
            validate_email(value)
        except ValidationError:
            raise ShouldBe("valid E-Mail address")


class Exact:
    def __init__(self, value):
        self.value = value

    def __call__(self, value):
        if value != self.value:
            raise ShouldBe(f"{self.value!r}")


class IpAddress:
    def __call__(self, value):
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise ShouldBe("valid IP address")


class Time:
    def __call__(self, value):
        try:
            hours, minutes = value.split(':')
        except ValueError:
            raise ShouldBe('Time should be in 24 hour format like "18:00"')
        else:
            try:
                time(int(hours), int(minutes))
            except TypeError:
                raise ShouldBe('Time should be in 24 hour format like "18:00"')
            except ValueError as v:
                raise ShouldBe(str(v))


class Match:
    def __init__(self, pattern, flags=0):
        self.pattern = pattern
        self.flags = flags

        self.regex = re.compile(pattern, flags)

    def __call__(self, value):
        if not self.regex.match(value):
            raise ShouldBe(f"{self.pattern}")

    def __deepcopy__(self, memo):
        return Match(self.pattern, self.flags)


class Or:
    def __init__(self, *validators):
        self.validators = validators

    def __call__(self, value):
        patterns = []

        for validator in self.validators:
            try:
                validator(value)
            except ShouldBe as e:
                patterns.append(e.what)
            else:
                return

        raise ShouldBe(" or ".join(patterns))


class Range:
    def __init__(self, min=None, max=None):
        self.min = min
        self.max = max

    def __call__(self, value):
        if value is None:
            return
        error = {
            (True, True): f"between {self.min} and {self.max}",
            (False, True): f"less or equal than {self.max}",
            (True, False): f"greater or equal than {self.min}",
            (False, False): "",
        }[self.min is not None, self.max is not None]

        if self.min is not None and value < self.min:
            raise ShouldBe(error)

        if self.max is not None and value > self.max:
            raise ShouldBe(error)
