import time

from middlewared.test.integration.utils import call


def test_system_reboot():
    boot_id = call("system.boot_id")

    call("system.reboot", "Integration test")

    for i in range(180):
        try:
            new_boot_id = call("system.boot_id")
        except Exception:
            pass
        else:
            if new_boot_id == boot_id:
                break

        time.sleep(1)
    else:
        assert False, "System did not reboot"

    audit = call("audit.query", {
        "services": ["MIDDLEWARE"],
        "query-filters": [
            ["event", "=", "REBOOT"],
        ],
    })
    assert audit[-1]["event_data"] == {"reason": "Integration test"}
