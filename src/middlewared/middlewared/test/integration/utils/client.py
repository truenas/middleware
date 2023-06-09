# -*- coding=utf-8 -*-
import contextlib
import os

import requests

from middlewared.client import Client
from middlewared.client.utils import undefined

__all__ = ["client", "host", "host_websocket_uri", "password", "session", "url", "websocket_url"]


@contextlib.contextmanager
def client(*, auth=undefined, auth_required=True, py_exceptions=True, log_py_exceptions=True, host_ip=None):
    if auth is undefined:
        auth = ("root", password())

    with Client(host_websocket_uri(host_ip), py_exceptions=py_exceptions, log_py_exceptions=log_py_exceptions) as c:
        if auth is not None:
            logged_in = c.call("auth.login", *auth)
            if auth_required:
                assert logged_in
        yield c


def host():
    if "NODE_A_IP" in os.environ:
        return os.environ["NODE_A_IP"]
    else:
        return os.environ["MIDDLEWARE_TEST_IP"]


def host_websocket_uri(host_ip=None):
    return f"ws://{host_ip or host()}/websocket"


def password():
    if "NODE_A_IP" in os.environ:
        return os.environ["APIPASS"]
    else:
        return os.environ["MIDDLEWARE_TEST_PASSWORD"]


@contextlib.contextmanager
def session():
    with requests.Session() as s:
        s.auth = ("root", os.environ["MIDDLEWARE_TEST_PASSWORD"])
        yield s


def url():
    return f"http://{host()}"


def websocket_url():
    return f"ws://{host()}"
