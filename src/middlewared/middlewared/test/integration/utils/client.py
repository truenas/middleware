import contextlib
import errno
import os
import logging
import socket

import requests

from middlewared.service_exception import CallError
from truenas_api_client import Client
from truenas_api_client.utils import undefined

from .pytest import fail

__all__ = ["client", "host", "host_websocket_uri", "password", "session", "url", "websocket_url"]

logger = logging.getLogger(__name__)

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

    def __init__(self):
        self._ip = None
        self._nodea_ip = None
        self._nodeb_ip = None
        self._server_type = None
        self._client = None

    @property
    def ip(self) -> str | None:
        """
        default target IP address for TrueNAS server

        Will be virtual IP on TrueNAS HA but otherwise set through the
        `MIDDLEWARE_TEST_IP` environmental variable in non-HA case.
        """
        return self._ip

    @ip.setter
    def ip(self, new_ip: str):
        """ set new IP and clear client connection """
        self._ip = new_ip
        if self._client:
            self._client.close()
            self._client = None

    @property
    def nodea_ip(self) -> str | None:
        """ IP address of first storage controller on HA. Will be `None` if not HA """
        return self._nodea_ip

    @nodea_ip.setter
    def nodea_ip(self, ip: str):
        self._nodea_ip = ip

    @property
    def nodeb_ip(self) -> str | None:
        """ IP address of second storage controller on HA. Will be `None` if not HA """
        return self._nodeb_ip

    @nodeb_ip.setter
    def nodeb_ip(self, ip: str):
        self._nodeb_ip = ip

    @property
    def server_type(self) -> str | None:
        """
        Server type of target TrueNAS server

        Returns
            str - 'ENTERPRISE_HA' or 'STANDARD'
            None - not configured
        """
        return self._server_type

    @server_type.setter
    def server_type(self, server_type: str):
        if server_type not in ('ENTERPRISE_HA', 'STANDARD'):
            raise ValueError(f'{server_type}: unknown server type')

        self._server_type = server_type

    @property
    def client(self) -> Client:
        """ websocket client connection to target TrueNAS server """
        if self._client is not None:
            try:
                self._client.ping()
                return self._client
            except Exception as e:
                logger.warning('Re-connecting test client due to %r', e)
                # failed liveness check, perhaps server rebooted
                # if target is truly broken we'll pick up error
                # when trying to establish a new client connection
                self._client.close()
                self._client = None

        # Has to be called in order for `truenas_server` global variable to be correctly initialized when
        # running `runtest.py` with a single test name
        host()

        if (addr := self.ip) is None:
            raise RuntimeError('IP is not set')

        uri = host_websocket_uri(addr)
        cl = Client(uri, py_exceptions=True, log_py_exceptions=True)
        try:
            cl.call('auth.login', 'root', password())
        except Exception:
            cl.close()
            raise

        self._client = cl
        return self._client

    def ha_ips(self) -> dict:
        if self.server_type == 'STANDARD':
            raise ValueError('Not an HA server')

        elif self.server_type is None:
            raise RuntimeError('TrueNAS server object not initialized')

        failover_node = self.client.call('failover.node')
        if failover_node not in ('A', 'B'):
            raise RuntimeError(f'{failover_node}: unexpected failover node')

        if failover_node == 'A':
            active_controller = self.nodea_ip
            standby_controller = self.nodeb_ip
        else:
            active_controller = self.nodeb_ip
            standby_controller = self.nodea_ip

        assert all((active_controller, standby_controller)), 'Unable to determine both HA controller IP addresses'
        return {
            'active': active_controller,
            'standby': standby_controller
        }


truenas_server = TrueNAS_Server()


@contextlib.contextmanager
def client(*, auth=undefined, auth_required=True, py_exceptions=True, log_py_exceptions=True, host_ip=None):
    if auth is undefined:
        auth = ("root", password())

    uri = host_websocket_uri(host_ip)
    try:
        with Client(uri, py_exceptions=py_exceptions, log_py_exceptions=log_py_exceptions) as c:
            if auth is not None:
                try:
                    logged_in = c.call("auth.login", *auth)
                except CallError as e:
                    if e.errno == errno.EBUSY and e.errmsg == 'Rate Limit Exceeded':
                        # our "roles" tests (specifically common_checks() function)
                        # isn't designed very well since it's generating random users
                        # for every unique test_* function in every test file....
                        # TODO: we should probably fix that issue at some point but
                        # this is easiest path forward to not cause a bunch of roles
                        # related tests to trip on our rate limiting functionality
                        truenas_server.client.call("rate.limit.cache_clear")
                        logged_in = c.call("auth.login", *auth)
                    else:
                        raise
                if auth_required:
                    assert logged_in
            yield c
    except socket.timeout:
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
    return f"ws://{host_ip or host().ip}/api/current"


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
