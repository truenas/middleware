import socket
import time

import requests

from middlewared.test.integration.utils import call, host, ssh, url


def test_system_general_ui_allowlist():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((host(), 1))  # connect() for UDP doesn't send packets
    local_ip = s.getsockname()[0]

    try:
        protected_endpoints = (
            "/_download",
            "/_upload",
            "/_plugins",
            "/api/docs",
            "/api/v2.0",
            "/progress",
            "/vm/display",
            "/websocket",
        )

        # Ensure we are testing endpoints that do not give 403 by default
        for endpoint in protected_endpoints:
            r = requests.get(url() + endpoint, timeout=10)
            assert r.status_code != 403

        # Set `ui_allowlist` to IP we are using
        call("system.general.update", {"ui_allowlist":  [local_ip]})
        call("system.general.ui_restart", 0)
        time.sleep(10)

        # Check everything still works
        for endpoint in protected_endpoints:
            r = requests.get(url() + endpoint, timeout=10)
            assert r.status_code != 403

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
            assert r.status_code == 403
    finally:
        # We are not allowed to access API, bring things back to normal via SSH
        ssh("midclt call system.general.update '{\"ui_allowlist\": []}'")
        ssh("midclt call system.general.ui_restart 0")
        time.sleep(10)
