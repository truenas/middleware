from unittest.mock import ANY

import pytest

from middlewared.test.integration.utils import call, mock


vmsnapobj = {
    "hostname": "host",
    "username": "user",
    "password": "pass",
}

@pytest.fixture(scope="function")
def vmware():
    with mock("vmware.validate_data", return_value=None):
        vmware = call("vmware.create", {
            "datastore": "ds",
            "filesystem": "fs",
            **vmsnapobj,
        })
        try:
            yield vmware
        finally:
            call("vmware.delete", vmware["id"])


def test_vmware_state_lifetime(vmware):
    assert vmware["state"] == {"state": "PENDING"}

    call("vmware.alert_vmware_login_failed", vmsnapobj, "Unknown error")
    vmware = call("vmware.get_instance", vmware["id"])
    assert vmware["state"] == {"state": "ERROR", "error": "Unknown error", "datetime": ANY}

    call("vmware.delete_vmware_login_failed_alert", vmsnapobj)
    vmware = call("vmware.get_instance", vmware["id"])
    assert vmware["state"] == {"state": "SUCCESS", "datetime": ANY}

    call("vmware.update", vmware["id"], {})
    vmware = call("vmware.get_instance", vmware["id"])
    assert vmware["state"] == {"state": "PENDING"}


def test_vmware_network_activity(vmware):
    with mock("network.general.can_perform_activity", return_value=False):
        call("vmware.snapshot_begin", "fs", False)

        vmware = call("vmware.get_instance", vmware["id"])
        assert vmware["state"] == {"state": "BLOCKED", "datetime": ANY}
