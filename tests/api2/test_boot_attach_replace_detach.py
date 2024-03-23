import pytest

from middlewared.test.integration.utils import call
from auto_config import ha

pytestmark = pytest.mark.boot


if not ha:
    # the HA VMs only have 1 extra disk at time
    # of writing this. QE is aware and is working
    # on adding more disks to them so in the meantime
    # we have to skip this test since it will fail
    # 100% of the time on HA VMs.

    @pytest.mark.timeout(600)
    def test_boot_attach_replace_detach():
        existing_disks = call("boot.get_disks")
        assert len(existing_disks) == 1

        unused = call("disk.get_unused")
        to_attach = unused[0]["name"]
        replace_with = unused[1]["name"]

        # Attach a disk and wait for resilver to finish
        call("boot.attach", to_attach, job=True)
        while True:
            state = call("boot.get_state")
            if not (
                state["scan"] and
                state["scan"]["function"] == "RESILVER" and
                state["scan"]["state"] == "SCANNING"
            ):
                break

        assert state["topology"]["data"][0]["type"] == "MIRROR"

        assert state["topology"]["data"][0]["children"][0]["status"] == "ONLINE"

        to_replace = state["topology"]["data"][0]["children"][1]["name"]
        assert to_replace.startswith(to_attach)
        assert state["topology"]["data"][0]["children"][1]["status"] == "ONLINE"

        # Replace newly attached disk
        call("boot.replace", to_replace, replace_with, job=True)
        # Resilver is a part of replace routine
        state = call("boot.get_state")

        assert state["topology"]["data"][0]["type"] == "MIRROR"

        assert state["topology"]["data"][0]["children"][0]["status"] == "ONLINE"

        to_detach = state["topology"]["data"][0]["children"][1]["name"]
        assert to_detach.startswith(replace_with)
        assert state["topology"]["data"][0]["children"][1]["status"] == "ONLINE"

        # Detach replaced disk, returning the pool to its initial state
        call("boot.detach", to_detach)

        assert len(call("boot.get_disks")) == 1
