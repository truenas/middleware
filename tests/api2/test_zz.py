# These tests need to be executing at the very last stage of the testing process as they semi-break the system
# in different ways.
from middlewared.test.integration.utils import call


def test_failover_reboot_add_reason():
    info = call("failover.reboot.info")
    assert not info["this_node"]["reboot_required"]
    assert info["this_node"]["reboot_required_reasons"] == []

    call("failover.reboot.add_reason", "test", "Test reason.")

    info = call("failover.reboot.info")
    assert info["this_node"]["reboot_required"]
    assert info["this_node"]["reboot_required_reasons"] == ["Test reason."]
