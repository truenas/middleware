from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls


def test_ntpserver_audit():
    """Changes to the NTP servers are audited by the address of the server they are made to."""
    payload = {"address": "127.0.0.1", "force": True}
    with expect_audit_method_calls(
        [
            {
                "method": "system.ntpserver.create",
                "params": [payload],
                "description": "NTP server create 127.0.0.1",
            }
        ]
    ):
        server = call("system.ntpserver.create", payload)

    try:
        payload = {"address": "127.0.0.2", "force": True}
        with expect_audit_method_calls(
            [
                {
                    "method": "system.ntpserver.update",
                    "params": [server["id"], payload],
                    "description": "NTP server update 127.0.0.1",
                }
            ]
        ):
            call("system.ntpserver.update", server["id"], payload)

        with expect_audit_method_calls(
            [
                {
                    "method": "system.ntpserver.delete",
                    "params": [server["id"]],
                    "description": "NTP server delete 127.0.0.2",
                }
            ]
        ):
            call("system.ntpserver.delete", server["id"])
    finally:
        if call("system.ntpserver.query", [["id", "=", server["id"]]]):
            call("system.ntpserver.delete", server["id"])
