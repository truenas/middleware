import time

import pytest
from functions import http_get
from urllib.error import URLError

from middlewared.test.integration.utils import call, ssh, url


# Sometimes, nginx is restarted 10 seconds after we make `system.general.update` call:
# [2025/02/14 09:58:10] Starting integration test test_system_general_ui_rollback
# Feb 14 09:58:18 Stopping nginx.service - A high performance web server and a reverse proxy server...
# Feb 14 09:58:23 nginx.service: Stopping timed out. Terminating.
# That breaks our tight timings (we reasonably expect nginx to be restarted `ui_restart_delay` seconds after we make
# the call).
# I was not able to reproduce this locally. This issue won't affect the production systems (once in a while UI will
# take N more seconds to restart).
# We can make set `rollback_timeout` to 60 (as we do in production), but that'll increase the test run time in every run
# It's better to just re-run the test once in a while.
@pytest.mark.flaky(reruns=5, reruns_delay=30)
def test_system_general_ui_rollback():
    try:
        # Apply incorrect changes
        call("system.general.update", {"ui_port": 81, "rollback_timeout": 20, "ui_restart_delay": 3})

        # Wait for changes to be automatically applied
        time.sleep(10)

        # Ensure that changes were applied and the UI is now inaccessible
        with pytest.raises((URLError, ConnectionError)):
            http_get(url(), timeout=10)

        # Additionally ensure that it is still working
        assert http_get(url() + ":81", timeout=10).status_code == 200

        # Ensure that the check-in timeout is ticking back
        assert 3 <= int(ssh("midclt call system.general.checkin_waiting").strip()) < 10

        # Wait for changes to be automatically rolled back
        time.sleep(15)

        # Ensure that the UI is now accessible
        assert http_get(url(), timeout=10).status_code == 200
    except Exception:
        # Bring things back to normal via SSH in case of any error
        ssh("midclt call system.general.update '{\"ui_port\": 80}'")
        ssh("midclt call system.general.ui_restart 0")
        time.sleep(20)
        raise


def test_system_general_ui_checkin():
    try:
        # Apply incorrect changes
        call("system.general.update", {"ui_port": 81, "rollback_timeout": 20, "ui_restart_delay": 3})

        # Wait for changes to be automatically applied
        time.sleep(10)

        # Check-in our new settings
        assert ssh("midclt call system.general.checkin")

        # Checking should not be pending anymore
        assert ssh("midclt call system.general.checkin_waiting").strip() == "null"
    finally:
        # Bring things back to normal via SSH
        ssh("midclt call system.general.update '{\"ui_port\": 80}'")
        ssh("midclt call system.general.ui_restart 0")
        time.sleep(10)
