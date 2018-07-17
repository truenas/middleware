import ipaddress
import re

from datetime import time
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class Email:
    def __call__(self, value):
        try:
            validate_email(value)
        except ValidationError:
            raise ValueError("Not a valid E-Mail address")


class Exact:
    def __init__(self, value):
        self.value = value

    def __call__(self, value):
        if value != self.value:
            raise ValueError(f"Should be {self.value!r}")


class IpAddress:
    def __call__(self, value):
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise ValueError("Not a valid IP address")


class Time:
    def __call__(self, value):
        try:
            hours, minutes = value.split(':')
        except ValueError:
            raise ValueError('Time should be in 24 hour format like "18:00"')
        else:
            try:
                time(int(hours), int(minutes))
            except TypeError:
                raise ValueError('Time should be in 24 hour format like "18:00"')


class Match:
    def __init__(self, pattern, flags=0, explanation=None):
        self.pattern = pattern
        self.flags = flags
        self.explanation = explanation

        self.regex = re.compile(pattern, flags)

    def __call__(self, value):
        if not self.regex.match(value):
            raise ValueError(self.explanation or f"Does not match {self.pattern}")

    def __deepcopy__(self, memo):
        return Match(self.pattern, self.flags)


class Or:
    def __init__(self, *validators):
        self.validators = validators

    def __call__(self, value):
        errors = []

        for validator in self.validators:
            try:
                validator(value)
            except ValueError as e:
                errors.append(str(e))
            else:
                return

        raise ValueError(" or ".join(errors))


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
            raise ValueError(f"Should be {error}")

        if self.max is not None and value > self.max:
            raise ValueError(f"Should be {error}")


class Port(Range):
    def __init__(self):
        super().__init__(min=1, max=65535)


class Unique:
    def __call__(self, value):
        for item in value:
            if value.count(item) > 1:
                raise ValueError(f"Duplicate values are not allowed: {item!r}")
