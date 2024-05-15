from unittest.mock import ANY

from middlewared.test.integration.utils import call, mock


def test_vmware_state_lifetime():
    vmsnapobj = {
        "hostname": "host",
        "username": "user",
        "password": "pass",
    }
    with mock("vmware.validate_data", return_value=None):
        vmware = call("vmware.create", {
            "datastore": "ds",
            "filesystem": "fs",
            **vmsnapobj,
        })
        try:
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
        finally:
            call("vmware.delete", vmware["id"])
