# -*- coding=utf-8 -*-
import contextlib
import os
import socket
import types

import requests

from truenas_api_client import Client
from truenas_api_client.utils import undefined

from .pytest import fail

__all__ = ["client", "host", "host_websocket_uri", "password", "session", "url", "websocket_url"]
"""
truenas_server object is used by both websocket client and REST client for determining which
server to access for API calls. For HA, the `ip` attribute should be set to the virtual IP
of the truenas server.
"""
truenas_server = types.SimpleNamespace(ip=None, nodea_ip=None, nodeb_ip=None, server_type=None)


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
    if truenas_server.ip:
        return truenas_server

    # Initialize our settings. At this point on HA servers, the VIP is not available
    truenas_server.server_type = os.environ['SERVER_TYPE']

    # Some older test runners have old python
    if truenas_server.server_type == 'ENTERPRISE_HA':
        if "USE_VIP" in os.environ and os.environ["USE_VIP"] == "yes":
            truenas_server.ip = os.environ["virtual_ip"]
        else:
            truenas_server.ip = os.environ["controller1_ip"]
        truenas_server.nodea_ip = os.environ["controller1_ip"]
        truenas_server.nodeb_ip = os.environ["controller2_ip"]
    else:
        truenas_server.ip = os.environ["MIDDLEWARE_TEST_IP"]

    return truenas_server


def host_websocket_uri(host_ip=None):
    return f"ws://{host_ip or host().ip}/websocket"


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
    return f"http://{host().ip}"


def websocket_url():
    return f"ws://{host().ip}"
