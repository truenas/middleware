# -*- coding=utf-8 -*-
import contextlib
import os

from middlewared.client import Client

__all__ = ["client"]


@contextlib.contextmanager
def client():
    with Client(f"ws://{os.environ['MIDDLEWARE_TEST_IP']}/websocket", py_exceptions=True) as c:
        c.call("auth.login", "root", os.environ["MIDDLEWARE_TEST_PASSWORD"])
        yield c
