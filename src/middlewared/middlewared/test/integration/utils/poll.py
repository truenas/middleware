# -*- coding=utf-8 -*-
import time

__all__ = ["poll"]


def poll(func, *, condition=bool, timeout, message, interval=1):
    """Call `func` every `interval` seconds until `condition` accepts its return value.

    :param func: callable that produces the value to check.
    :param condition: callable that accepts the produced value and returns whether it is the one
        being waited for. By default, waits for any truthy value.
    :param timeout: total number of seconds to wait.
    :param message: error message for the timeout failure.
    :param interval: number of seconds to sleep between calls.
    :return: the first accepted value.
    :raises AssertionError: `condition` did not accept any value within `timeout` seconds (the
        error message includes the last produced value, for diagnostics).
    """
    deadline = time.monotonic() + timeout
    while True:
        value = func()
        if condition(value):
            return value

        if time.monotonic() >= deadline:
            raise AssertionError(f"{message} (waited {timeout} seconds, last value = {value!r})")

        time.sleep(interval)
