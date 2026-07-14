import pytest

from assets.unlock_restart import (
    assert_started_only_after_all_deps_unlocked,
    encryption_props,
    marker_mock,
    model_mock,
    unlock,
)
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, mock, ssh


DEVICE_MODELS = {"DISK": "VMDiskDevice", "RAW": "VMRAWDevice", "CDROM": "VMCDROMDevice"}


def vm_entry(name, devices):
    # A single line of Python building a `VMEntry`, to be evaluated by `model_mock`. `devices` is a
    # list of `(dtype, path)` pairs.
    device_exprs = ", ".join(
        f"VMDeviceEntry.model_construct(id={i}, vm=1, order={i}, attributes="
        f"{DEVICE_MODELS[dtype]}.model_construct(dtype={dtype!r}, path={path!r}))"
        for i, (dtype, path) in enumerate(devices, start=1)
    )
    return f"VMEntry.model_construct(id=1, name={name!r}, autostart=True, devices=[{device_exprs}])"


def vm_status(state):
    return model_mock(f"VMStatus.model_construct(state={state!r})")


@pytest.mark.parametrize("zvol", [True, False])
def test_restart_vm_on_dataset_unlock(zvol):
    if zvol:
        data = {"type": "VOLUME", "volsize": 1048576}
    else:
        data = {}

    with dataset("test", {**data, **encryption_props()}) as ds:
        call("pool.dataset.lock", ds, job=True)

        if zvol:
            device = ("DISK", f"/dev/zvol/{ds}")
        else:
            device = ("RAW", f"/mnt/{ds}/child")

        with (
            mock("vm.query", declaration=model_mock(f"[{vm_entry('myvm', [device])}]")),
            mock("vm.status", declaration=vm_status("RUNNING")),
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

        entry = vm_entry(
            "split-vm",
            [("RAW", f"/mnt/{ds1}/disk.raw"), ("RAW", f"/mnt/{ds2}/disk.raw")],
        )
        with (
            mock("vm.query", declaration=model_mock(f"[{entry}]")),
            mock("vm.status", declaration=vm_status("STOPPED")),
            mock("vm.start", declaration=marker_mock("/tmp/split-vm-start")),
        ):
            assert_started_only_after_all_deps_unlocked("/tmp/split-vm-start", ds1, ds2)
