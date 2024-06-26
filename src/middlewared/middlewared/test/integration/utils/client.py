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
class TrueNAS_Server:
    __slots__ = (
        '_ip',
        '_nodea_ip',
        '_nodeb_ip',
        '_server_type',
        '_client',
    )

    @property
    def ip(self):
        return self._ip

    @ip.setter
    def ip(self, new_ip: str):
        """ set new IP and clear client connection """
        self._ip = new_ip
        if self._client:
            self._client.close()
            self._client = None

    @property
    def nodea_ip(self):
        return self._nodea_ip

    @nodea_ip.setter
    def nodea_ip(self, ip: str):
        self._nodea_ip = ip

    @property
    def nodeb_ip(self):
        return self._nodeb_ip

    @nodea_ip.setter
    def nodeb_ip(self, ip: str):
        self._nodeb_ip = ip

    @property
    def server_type(self):
        return self._server_type

    @server_type.setter
    def server_type(self, server_type):
        self._server_type = server_type

    @property
    def client(self):
        if self._client is not None:
            return self._client

        if (addr := self.ip) is None:
            raise RuntimeError('IP is not set')

        uri = host_websocket_uri(addr)
        cl = Client(uri, py_exceptions=True, lo_py_exceptions=True)
        try:
            cl.call('auth.login', 'root', password())
        except Exception:
            cl.close()
            raise

        self._client = cl
        return self._client


truenas_server = TrueNAS_Server()


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
