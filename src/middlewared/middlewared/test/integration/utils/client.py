# -*- coding=utf-8 -*-
import contextlib
import os

import requests

from middlewared.client import Client

__all__ = ["client", "session", "url"]


@contextlib.contextmanager
def client(py_exceptions=True):
    if "NODE_A_IP" in os.environ:
        host = os.environ["NODE_A_IP"]
        password = os.environ["APIPASS"]
    else:
        host = os.environ["MIDDLEWARE_TEST_IP"]
        password = os.environ["MIDDLEWARE_TEST_PASSWORD"]

    with Client(f"ws://{host}/websocket", py_exceptions=py_exceptions) as c:
        c.call("auth.login", "root", password)
        yield c


@contextlib.contextmanager
def session():
    with requests.Session() as s:
        s.auth = ("root", os.environ["MIDDLEWARE_TEST_PASSWORD"])
        yield s


def url():
    return f"http://{os.environ['MIDDLEWARE_TEST_IP']}"
