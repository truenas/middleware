from config import SPACES_MEMBERS
from contextlib import contextmanager
from middlewared.test.integration.utils import host_websocket_uri
from middlewared.test.integration.utils.client import Client


def client_impl(*, auth, py_exceptions=True, log_py_exceptions=True, host_ip=None):
    c = Client(host_websocket_uri(host_ip), py_exceptions=True, log_py_exceptions=True)
    logged_in = c.call("auth.login", *auth)
    assert logged_in
    return c


@contextmanager
def spaces_connections():
    c = [(client_impl(auth=(m.username, m.password), host_ip=m.ip), m) for m in SPACES_MEMBERS]

    try:
        yield c
    finally:
        for cl, member in c:

            cl.close()
