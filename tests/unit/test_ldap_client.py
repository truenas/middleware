import socket
import threading
import time

import ldap
import pytest

from middlewared.utils.directoryservices.constants import DSCredType
from middlewared.utils.directoryservices.ldap_client import LDAPClient

LDAP_OP_BIND_REQUEST = 0x60
LDAP_OP_SEARCH_REQUEST = 0x63
TIMEOUT = 1


class SilentLdapServer:
    """
    Fake LDAP server that replies only to bind requests. To the client, it is the
    same as a server that became unreachable after the bind.
    """

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.url = f"ldap://127.0.0.1:{self.sock.getsockname()[1]}"
        self.clients = []
        self.requests = []  # protocol op tags
        self.lock = threading.Lock()
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return

            with self.lock:
                self.clients.append(conn)

            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        buf = b""
        while True:
            try:
                data = conn.recv(4096)
            except OSError:
                return

            if not data:
                return

            buf += data
            while (pdu := self._next_pdu(buf)) is not None:
                total, body = pdu
                self._handle_message(conn, buf[body:total])
                buf = buf[total:]

    @staticmethod
    def _next_pdu(buf):
        """
        Return (total length, contents offset) of the first LDAPMessage in buf.
        Return None if the message is not complete.
        """
        if len(buf) < 2:
            return None

        length = buf[1]
        offset = 2
        if length & 0x80:
            nbytes = length & 0x7F
            if len(buf) < offset + nbytes:
                return None

            length = int.from_bytes(buf[offset : offset + nbytes], "big")
            offset += nbytes

        if len(buf) < offset + length:
            return None

        return offset + length, offset

    def _handle_message(self, conn, msg):
        # LDAPMessage ::= SEQUENCE { messageID INTEGER, protocolOp CHOICE { ... } }
        # The client sends message IDs less than 128, so the INTEGER is 02 01 <id>.
        assert msg[0] == 0x02 and msg[1] == 0x01
        msgid = msg[2]
        op = msg[3]
        with self.lock:
            self.requests.append(op)

        if op == LDAP_OP_BIND_REQUEST:
            # BindResponse { resultCode success, matchedDN '', diagnosticMessage '' }
            conn.sendall(bytes([0x30, 0x0C, 0x02, 0x01, msgid, 0x61, 0x07, 0x0A, 0x01, 0x00, 0x04, 0x00, 0x04, 0x00]))

    def count(self, op):
        with self.lock:
            return self.requests.count(op)

    def wait_for(self, op, n, deadline=5):
        end = time.monotonic() + deadline
        while time.monotonic() < end:
            if self.count(op) >= n:
                return True

            time.sleep(0.05)

        return False

    def close(self):
        self.sock.close()
        with self.lock:
            clients, self.clients = self.clients, []

        for conn in clients:
            conn.close()


@pytest.fixture
def server():
    srv = SilentLdapServer()
    try:
        yield srv
    finally:
        srv.close()


def client_config(server):
    return {
        "server_urls": [server.url],
        "basedn": "",
        "credential": {"credential_type": DSCredType.LDAP_ANONYMOUS},
        "validate_certificates": False,
        "starttls": False,
        "timeout": TIMEOUT,
    }


def test_timeouts_are_set_on_the_handle(server):
    client = LDAPClient()
    client.open(client_config(server))
    try:
        assert client._handle.get_option(ldap.OPT_NETWORK_TIMEOUT) == TIMEOUT
        assert client._handle.get_option(ldap.OPT_TIMEOUT) == TIMEOUT
    finally:
        client.close()


def test_search_times_out_when_server_stops_answering(server):
    client = LDAPClient()
    start = time.monotonic()
    try:
        with pytest.raises(ldap.TIMEOUT):
            client.search(client_config(server), "", ldap.SCOPE_BASE, "(objectclass=*)")

        elapsed = time.monotonic() - start
        # The expected time is two search timeouts and one reconnect.
        assert elapsed < 10 * TIMEOUT

        # The client tries the search again only one time, on a new connection.
        assert server.wait_for(LDAP_OP_BIND_REQUEST, 2)
        assert server.wait_for(LDAP_OP_SEARCH_REQUEST, 2)
        assert server.count(LDAP_OP_BIND_REQUEST) == 2
        assert server.count(LDAP_OP_SEARCH_REQUEST) == 2
    finally:
        client.close()
