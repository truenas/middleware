import time

import pytest
import requests

from middlewared.test.integration.utils import call, ssh, url


def test_system_general_ui_rollback():
    try:
        # Apply incorrect changes
        call("system.general.update", {"ui_port": 81, "rollback_timeout": 20, "ui_restart_delay": 3})

        # Wait for changes to be automatically applied
        time.sleep(10)

        # Ensure that changes were applied and the UI is now inaccessible
        with pytest.raises(requests.ConnectionError):
            requests.get(url(), timeout=10)

        # Additionally ensure that it is still working
        assert requests.get(url() + ":81", timeout=10).status_code == 200

        # Ensure that the check-in timeout is ticking back
        assert 3 <= int(ssh("midclt call system.general.checkin_waiting").strip()) < 10

        # Wait for changes to be automatically rolled back
        time.sleep(10)

        # Ensure that the UI is now accessible
        assert requests.get(url(), timeout=10).status_code == 200
    except Exception:
        # Bring things back to normal via SSH in case of any error
        ssh("midclt call system.general.update '{\"ui_port\": 80}'")
        ssh("midclt call system.general.ui_restart 0")
        time.sleep(10)
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
