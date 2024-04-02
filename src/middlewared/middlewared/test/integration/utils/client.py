# -*- coding=utf-8 -*-
import contextlib
import os
import socket

import requests

from .pytest import fail
from middlewared.client import Client
from middlewared.client.utils import undefined

__all__ = ["client", "host", "host_websocket_uri", "password", "session", "url", "websocket_url"]
IS_HA = os.environ.get('SERVER_TYPE') == 'ENTERPRISE_HA'


@contextlib.contextmanager
def client(*, auth=undefined, auth_required=True, py_exceptions=True, log_py_exceptions=True, host_ip=None):
    if auth is undefined:
        auth = ("root", password())

    uri = host_websocket_uri(host_ip)
    try:
        with Client(uri, py_exceptions=py_exceptions, log_py_exceptions=log_py_exceptions) as c:
            if auth is not None:
                logged_in = c.call("auth.login", *auth)
                if auth_required:
                    assert logged_in
            yield c
    except socket.timeout as e:
        fail(f'socket timeout on URI: {uri!r} HOST_IP: {host_ip!r}')


def host():
    if "NODE_A_IP" in os.environ:
        # this is not to be confused with HA systems
        # as it should only be set on NON-HA environments
        return os.environ["NODE_A_IP"]
    elif IS_HA:
        return os.environ["virtual_ip"]
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
