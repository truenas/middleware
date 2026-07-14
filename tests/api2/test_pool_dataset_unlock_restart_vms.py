import pytest

from assets.unlock_restart import (
    assert_started_only_after_all_deps_unlocked,
    encryption_props,
    marker_mock,
    unlock,
)
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, mock, ssh


@pytest.mark.parametrize("zvol", [True, False])
def test_restart_vm_on_dataset_unlock(zvol):
    if zvol:
        data = {"type": "VOLUME", "volsize": 1048576}
    else:
        data = {}

    with dataset("test", {**data, **encryption_props()}) as ds:
        call("pool.dataset.lock", ds, job=True)

        if zvol:
            device = {"attributes": {"path": f"/dev/zvol/{ds}", "dtype": "DISK"}}
        else:
            device = {"attributes": {"path": f"/mnt/{ds}/child", "dtype": "RAW"}}

        with (
            mock("vm.query", return_value=[{"id": 1, "devices": [device]}]),
            mock("vm.status", return_value={"state": "RUNNING"}),
            mock("vm.stop", declaration=marker_mock("/tmp/test-vm-stop")),
            mock("vm.start", declaration=marker_mock("/tmp/test-vm-start")),
        ):
            ssh("rm -f /tmp/test-vm-stop /tmp/test-vm-start")
            unlock(ds)
            call("filesystem.stat", "/tmp/test-vm-stop")
            call("filesystem.stat", "/tmp/test-vm-start")


def test_vm_not_started_until_all_encrypted_storage_unlocked():
    # A VM with disks on two independently-encrypted datasets must not be started until BOTH are
    # unlocked -- booting with a still-locked disk would present missing storage to the guest.
    with (
        dataset("vroot", encryption_props()) as ds1,
        dataset("vdata", encryption_props()) as ds2,
    ):
        call("pool.dataset.lock", ds1, job=True)
        call("pool.dataset.lock", ds2, job=True)

        vm = {
            "id": 1,
            "name": "split-vm",
            "devices": [
                {"attributes": {"dtype": "RAW", "path": f"/mnt/{ds1}/disk.raw"}},
                {"attributes": {"dtype": "RAW", "path": f"/mnt/{ds2}/disk.raw"}},
            ],
        }
        with (
            mock("vm.query", return_value=[vm]),
            mock("vm.status", return_value={"state": "STOPPED"}),
            mock("vm.start", declaration=marker_mock("/tmp/split-vm-start")),
        ):
            assert_started_only_after_all_deps_unlocked("/tmp/split-vm-start", ds1, ds2)
