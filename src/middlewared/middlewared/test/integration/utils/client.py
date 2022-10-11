# -*- coding=utf-8 -*-
import contextlib
import os

import requests

from middlewared.client import Client, ValidationErrors  #noqa
from middlewared.client.utils import undefined

__all__ = ["client", "host", "session", "url", "ValidationErrors", "websocket_url"]


@contextlib.contextmanager
def client(*, auth=undefined, py_exceptions=True, log_py_exceptions=True):
    if auth is undefined:
        if "NODE_A_IP" in os.environ:
            password = os.environ["APIPASS"]
        else:
            password = os.environ["MIDDLEWARE_TEST_PASSWORD"]

        auth = ("root", password)

    with Client(f"ws://{host()}/websocket", py_exceptions=py_exceptions, log_py_exceptions=log_py_exceptions) as c:
        if auth is not None:
            c.call("auth.login", *auth)
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


def websocket_url():
    return f"ws://{host()}"
