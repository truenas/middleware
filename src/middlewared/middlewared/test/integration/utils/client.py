# -*- coding=utf-8 -*-
import contextlib
import os

import requests

from middlewared.client import Client

__all__ = ["client", "host", "session", "url"]


@contextlib.contextmanager
def client(py_exceptions=True):
    if "NODE_A_IP" in os.environ:
        password = os.environ["APIPASS"]
    else:
        password = os.environ["MIDDLEWARE_TEST_PASSWORD"]

    with Client(f"ws://{host()}/websocket", py_exceptions=py_exceptions) as c:
        c.call("auth.login", "root", password)
        yield c


def host():
    if "NODE_A_IP" in os.environ:
        return os.environ["NODE_A_IP"]
    else:
        return os.environ["MIDDLEWARE_TEST_IP"]


@contextlib.contextmanager
def session():
    with requests.Session() as s:
        s.auth = ("root", os.environ["MIDDLEWARE_TEST_PASSWORD"])
        yield s


def url():
    return f"http://{host()}"
