import time
from contextlib import contextmanager

from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.client import truenas_server

ROLLBACK = 20
UI_DELAY = 3
ORIG_PORT = 80
NEW_PORT = 81


def fallback_ui_fix():
    """Fix the UI port settings using SSH in case an
    unexpected failure is met or we just want to reset
    our changes"""
    ssh(f"midclt call system.general.update '{{\"ui_port\": {ORIG_PORT}}}'")
    ssh("midclt call system.general.ui_restart 0")
    time.sleep(5)


@contextmanager
def client_with_timeout(host_ip=None, tries=30):
    for _ in range(tries):
        try:
            with client(host_ip=host_ip) as c:
                assert c.call("core.ping") == "pong"
                yield c
                break
        except ConnectionRefusedError:
            time.sleep(1)
    else:
        assert False, "Could not connect to client."


def test_system_general_ui_rollback():
    """This tests the following:
        1. change the port the nginx service binds to (our UI)
        2. ensure communication with the API on the original port failsinal port fails
        3. ensure communication with the API on the new port succeeds
        4. check the time left before the changes are rolled back
        5. sleep that amount of time (plus a few seconds for a buffer)
        6. ensure communication with the API on the original port succeeds
        7. if any above steps fail, revert the UI port settings via ssh"""
    try:
        # Step 1
        call(
            "system.general.update",
            {"ui_port": NEW_PORT, "rollback_timeout": ROLLBACK, "ui_restart_delay": UI_DELAY}
        )

        # Step 2
        try:
            assert call("core.ping") != "pong"
        except Exception:
            pass

        # Step 3
        with client_with_timeout(host_ip=f"{truenas_server.ip}:{NEW_PORT}") as c:
            rollback_left = c.call("system.general.checkin_waiting")
            # Step 4
            assert rollback_left < ROLLBACK

        # Step 5
        time.sleep(rollback_left + 5)
        # Step 6
        assert call("core.ping") == "pong"
    except Exception:
        # Step 7
        fallback_ui_fix()
        raise


def test_system_general_ui_checkin():
    """This tests the following:
        1. change the port the nginx service binds to (our UI)
        2. immediately checkin the UI port changes
        3. ensure we don't have a checkin pending
        4. revert any UI port settings via ssh"""
    try:
        # Step 1
        call(
            "system.general.update",
            {"ui_port": NEW_PORT, "rollback_timeout": ROLLBACK, "ui_restart_delay": UI_DELAY}
        )

        # Step 2
        with client_with_timeout(host_ip=f"{truenas_server.ip}:{NEW_PORT}") as c:
            # Step 3
            c.call("system.general.checkin")
            # Step 4
            assert c.call("system.general.checkin_waiting") is None
    finally:
        fallback_ui_fix()
