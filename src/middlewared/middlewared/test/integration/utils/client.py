# -*- coding=utf-8 -*-
import contextlib
import os

import requests

from middlewared.client import Client

__all__ = ["client", "session", "url"]


@contextlib.contextmanager
def client():
    with Client(f"ws://{os.environ['MIDDLEWARE_TEST_IP']}/websocket", py_exceptions=True) as c:
        c.call("auth.login", "root", os.environ["MIDDLEWARE_TEST_PASSWORD"])
        yield c


@contextlib.contextmanager
def session():
    with requests.Session() as s:
        s.auth = ("root", os.environ["MIDDLEWARE_TEST_PASSWORD"])
        yield s


def url():
    return f"http://{os.environ['MIDDLEWARE_TEST_IP']}"
