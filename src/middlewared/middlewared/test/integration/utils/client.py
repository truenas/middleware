# -*- coding=utf-8 -*-
import contextlib
import logging
import os

import requests

from middlewared.client import Client
from middlewared.client.utils import undefined

__all__ = ["client", "host", "host_websocket_uri", "password", "session", "url", "websocket_url", "PersistentCtx"]

logger = logging.getLogger(__name__)

class PersistentClient(Client):
    authenticated = False

    def call(self, method, *args, **kwargs):
        if method.startswith('auth.login') and self.authenticated:
            raise ValueError(
                'Login related endpoint used with persistent handle. '
                'Temporary client context should be created by setting `auth=<cred>` as '
                'a keyword argument for the client() call. Alternatively, the test developer '
                'may decide to import PersistentCtx from this module and call '
                'PersistentCtx.setup method in order to replace the persistent client connection.'
            )

        return super().call(method, *args, **kwargs)


class ClientCtx:
    conn = None

    def setup(self, *, auth=undefined, auth_required=True, py_exceptions=True, log_py_exceptions=True, host_ip=None):
        """
        Test developer may directly call this method after importing PersistentCtx
        in order to replcate the PersistentClient connection with one using different
        credentials or target IP address. Note that such changes will impact subsequent
        tests and so developers should either document this clearly or properly
        clean up after themselves.
        """
        if auth is None:
            raise ValueError('Authentication is required for client context wrapper')

        elif auth is undefined:
            auth = ("root", password())

        if self.conn is not None:
            self.conn.close()
            self.conn = None

        self.conn = PersistentClient(
            host_websocket_uri(host_ip),
            py_exceptions=py_exceptions,
            log_py_exceptions=log_py_exceptions
        )

        try:
            logged_in = self.conn.call("auth.login", *auth)
            if auth_required:
                assert logged_in

            self.conn.authenticated = True
        except Exception:
            self.conn.close()
            self.conn = None
            raise

        return self.conn

    def get_or_setup(self, *args, **kwargs):
        if self.conn:
            try:
                self.conn.ping()
                return self.conn
            except Exception:
                logger.warning("Persistent websocket connection died. Reconnecting.")
                pass

        return self.setup(*args, **kwargs)


PersistentCtx = ClientCtx()


@contextlib.contextmanager
def client(*, auth=undefined, auth_required=True, py_exceptions=True, log_py_exceptions=True, host_ip=None):
    if auth is undefined and host_ip is None and auth_required:
        yield PersistentCtx.get_or_setup()
        return

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
