import contextlib
import functools
import json
import uuid

import requests
import websocket

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.assets.crypto import imported_certificate
from middlewared.test.integration.utils import call, host, mock, poll

__all__ = ["webshare_share", "webshare_server", "webshare_session", "WebshareError"]

AUTH_PORT = 755
LINK_PORT = 756
TNC_CERTIFICATE = "truenas_connect"


@contextlib.contextmanager
def webshare_share(path, name, options=None):
    share = call("sharing.webshare.create", {"path": path, "name": name, **(options or {})})

    try:
        yield share
    finally:
        with contextlib.suppress(InstanceNotFound):
            call("sharing.webshare.delete", share["id"])


@contextlib.contextmanager
def truenas_connect_registered(certificate_id):
    """Report TrueNAS Connect as registered, without registering with the real service.

    `truenas-webshare-caddy-config` loads the certificates the proxies serve only for a system
    that is registered with TrueNAS Connect or holds an Enterprise license. A test runner is
    neither, so it answers `tn_connect.config` with a registered configuration instead.
    """
    # FIXME: Replace with proper TN Connect connection
    config = call("tn_connect.config") | {
        "enabled": True,
        "status": "CONFIGURED",
        "status_reason": "TrueNAS Connect is configured",
        "certificate": certificate_id,
        "tier": "FOUNDATION",
    }
    with mock("tn_connect.config", return_value=config):
        yield


@contextlib.contextmanager
def truenas_connect_certificate():
    """Yield the certificate the proxies serve, importing a self-signed one if TNC left none."""
    existing = call("certificate.query", [["name", "=", TNC_CERTIFICATE]])
    if existing:
        yield existing[0]
        return

    with imported_certificate(TNC_CERTIFICATE) as certificate:
        yield certificate


@contextlib.contextmanager
def webshare_server():
    """Run the Webshare services (auth, its proxy and the link service) against a fake registration.

    Yields once both ports answer, so a test can log in and download right away.
    """
    with truenas_connect_certificate() as certificate:
        with truenas_connect_registered(certificate["id"]):
            call("service.control", "START", "webshare", job=True)
            try:
                _wait_for_health()
                yield
            finally:
                call("service.control", "STOP", "webshare", job=True)


def _health(port, path):
    try:
        return requests.get(f"https://{host().ip}:{port}{path}", verify=False, timeout=10).status_code
    except requests.RequestException as e:
        return e


def _wait_for_health():
    for port, path in ((AUTH_PORT, "/webshare/health"), (LINK_PORT, "/health")):
        poll(
            functools.partial(_health, port, path),
            condition=lambda value: value == 200,
            timeout=60,
            message=f"Webshare is not serving on port {port}",
        )


class WebshareError(Exception):
    """A JSON-RPC error answer from the Webshare auth service or the file manager."""

    def __init__(self, error):
        self.error = error
        self.code = error.get("code")
        self.message = error.get("message")
        self.data = error.get("data") or {}
        super().__init__(error)


class WebshareSession:
    """A logged-in file manager session, which speaks JSON-RPC over its own websocket."""

    def __init__(self, websocket_):
        self.websocket = websocket_

    def call(self, method, params=None):
        call_id = str(uuid.uuid4())
        self.websocket.send(json.dumps({"jsonrpc": "2.0", "id": call_id, "method": method, "params": params or {}}))
        while True:
            _opcode, message = self.websocket.recv_data()
            answer = json.loads(message.decode())
            if answer.get("id") == call_id:
                break

        if "error" in answer:
            raise WebshareError(answer["error"])

        return answer["result"]

    def shares(self):
        return {share["name"]: share for share in self.call("shares.list")["shares"]}


@contextlib.contextmanager
def webshare_session(username, password):
    """Log `username` in and yield the file manager session that Webshare starts for them.

    A session keeps the share configuration it was started with, so a test that changes a share
    must open a new session to see the change.
    """
    auth = _connect("/webshare/ws")
    try:
        login = WebshareSession(auth).call("login", {"username": username, "password": password})
        session = _connect(login["websocket_url"], login["auth_token"])
        try:
            yield WebshareSession(session)
        finally:
            session.close()
    finally:
        auth.close()


def _connect(path, auth_token=None):
    header = {}
    if auth_token:
        header["Cookie"] = f"truenas_auth_token={auth_token}"

    return poll(
        lambda: _try_connect(f"wss://{host().ip}:{AUTH_PORT}{path}", header),
        condition=lambda value: not isinstance(value, Exception),
        timeout=60,
        message=f"Unable to establish a websocket connection with {path}",
    )


def _try_connect(url, header):
    try:
        return websocket.create_connection(url, header=header, sslopt={"cert_reqs": 0}, timeout=30)
    except (ConnectionRefusedError, OSError, websocket.WebSocketException) as e:
        return e
