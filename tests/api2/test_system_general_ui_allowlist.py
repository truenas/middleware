import socket
import time

import requests
import websocket

from middlewared.test.integration.utils import call, host, mock, ssh, url, websocket_url


def test_system_general_ui_allowlist():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((host().ip, 1))  # connect() for UDP doesn't send packets
    local_ip = s.getsockname()[0]

    with mock("vm.query", return_value=[
        {"id": 1, "name": ""},
    ]):
        with mock("vm.device.query", return_value=[
            {"id": 1, "attributes": {"bind": "127.0.0.1", "port": 1, "web_port": 1}, "vm": 1}
        ]):
            try:
                protected_endpoints = (
                    "/_download",
                    "/_upload",
                    "/_plugins",
                    "/api/docs",
                    "/api/v2.0",
                    "/progress",
                    "/vm/display/1",
                )
                protected_ws_endpoints = (
                    ("/websocket", '{"msg": "connect", "version": "1"}'),
                    ("/websocket/shell", '{"token": "invalid"}'),
                )

                # Ensure we are testing endpoints that do not give 403 by default
                for endpoint in protected_endpoints:
                    r = requests.get(url() + endpoint, timeout=10)
                    assert r.status_code != 403
                for endpoint, message in protected_ws_endpoints:
                    ws = websocket.create_connection(websocket_url() + endpoint)
                    ws.send(message)
                    resp_opcode, msg = ws.recv_data()
                    assert resp_opcode == 1, msg

                # Set `ui_allowlist` to IP we are using
                call("system.general.update", {"ui_allowlist":  [local_ip]})
                call("system.general.ui_restart", 0)
                time.sleep(10)

                # Check everything still works
                for endpoint in protected_endpoints:
                    r = requests.get(url() + endpoint, timeout=10)
                    assert r.status_code != 403
                for endpoint, message in protected_ws_endpoints:
                    ws = websocket.create_connection(websocket_url() + endpoint)
                    ws.send(message)
                    resp_opcode, msg = ws.recv_data()
                    assert resp_opcode == 1, msg

                # Set it to an invalid IP
                call("system.general.update", {"ui_allowlist": ["8.8.8.8"]})
                call("system.general.ui_restart", 0)
                time.sleep(10)

                # Ensure we are still able to open the UI
                r = requests.get(url(), timeout=10)
                assert r.status_code == 200

                # Ensure that we can't access API
                for endpoint in protected_endpoints:
                    r = requests.get(url() + endpoint, timeout=10)
                    assert r.status_code == 403, (endpoint, r.text)
                for endpoint, message in protected_ws_endpoints:
                    ws = websocket.create_connection(websocket_url() + endpoint)
                    ws.send(message)
                    resp_opcode, msg = ws.recv_data()
                    assert resp_opcode == 8, msg
                    assert msg[2:].decode("utf-8") == "You are not allowed to access this resource"
            finally:
                # We are not allowed to access API, bring things back to normal via SSH
                ssh("midclt call system.general.update '{\"ui_allowlist\": []}'")
                ssh("midclt call system.general.ui_restart 0")
                time.sleep(10)
