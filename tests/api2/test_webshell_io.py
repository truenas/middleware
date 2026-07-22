import json
import time

import websocket

from middlewared.test.integration.utils import call, websocket_url


def _recv_until(ws, predicate, timeout=30):
    """Collect shell frames until predicate(buffer) is true or timeout."""
    buf = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _, data = ws.recv_data()
        except websocket.WebSocketTimeoutException:
            continue
        if isinstance(data, str):
            data = data.encode()
        buf += data
        if predicate(buf):
            return buf
    raise AssertionError(f"timed out waiting for shell output; got {buf!r}")


def test_host_shell_io_roundtrip():
    """The reader thread must survive the transient pty EIO window during
    login(1) startup (vhangup + reopen) and forward shell output, and the
    writer thread must deliver input to the shell."""
    token = call("auth.generate_token", 300, {}, True)
    ws = websocket.create_connection(websocket_url() + "/websocket/shell")
    try:
        ws.settimeout(10)
        ws.send(json.dumps({"token": token}))
        _, msg = ws.recv_data()
        resp = json.loads(msg.decode())
        assert resp["msg"] == "connected", resp

        # Output arriving after "connected" proves the reader survived the
        # EIO window; a dead reader shows a blank terminal forever.
        _recv_until(ws, lambda buf: buf.strip() != b"")

        # Round-trip: input written to the pty must come back as output
        # (tty echo and command output).
        marker = "WEBSHELL_IO_ROUNDTRIP"
        ws.send_binary(f"echo {marker}\n".encode())
        _recv_until(ws, lambda buf: marker.encode() in buf)
    finally:
        ws.close()
