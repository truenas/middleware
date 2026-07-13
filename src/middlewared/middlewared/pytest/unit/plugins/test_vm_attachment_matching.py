import pytest

from middlewared.plugins.vm.attachments import VMFSAttachmentDelegate
from middlewared.pytest.unit.middleware import Middleware


def disk(dtype, path):
    return {"attributes": {"dtype": dtype, "path": path}}


@pytest.mark.parametrize(
    "device, expected",
    (
        # zvol-backed disks are normalized from /dev/zvol/<ds> to /mnt/<ds>
        (disk("DISK", "/dev/zvol/tank/vm-disk"), "/mnt/tank/vm-disk"),
        (disk("RAW", "/mnt/tank/vm/disk.img"), "/mnt/tank/vm/disk.img"),
        (disk("CDROM", "/mnt/tank/os.iso"), "/mnt/tank/os.iso"),
        # not disk-backed / no usable path
        (disk("NIC", "/dev/whatever"), None),
        (disk("DISPLAY", None), None),
        (disk("DISK", None), None),
        (disk("DISK", ""), None),
    ),
)
def test_device_disk_path(device, expected):
    delegate = VMFSAttachmentDelegate(Middleware())
    assert delegate.device_disk_path(device) == expected


def test_disk_paths_keeps_only_disk_and_raw():
    delegate = VMFSAttachmentDelegate(Middleware())
    vm = {
        "devices": [
            disk("DISK", "/dev/zvol/tank/a"),
            disk("RAW", "/mnt/tank/b.img"),
            disk("CDROM", "/mnt/tank/c.iso"),  # removable, excluded
            disk("NIC", "/dev/net"),  # not storage, excluded
        ],
    }
    assert delegate.disk_paths(vm) == ["/mnt/tank/a", "/mnt/tank/b.img"]


@pytest.mark.asyncio
async def test_vm_on_paths_matches_in_a_single_is_child_call():
    m = Middleware()
    calls = []

    def fake_is_child(child, parent):
        calls.append((child, parent))
        return True

    m["filesystem.is_child"] = fake_is_child
    delegate = VMFSAttachmentDelegate(m)
    vm = {"devices": [disk("DISK", "/dev/zvol/tank/a"), disk("RAW", "/mnt/tank/b.img")]}

    assert await delegate.vm_on_paths(vm, {"/mnt/tank"}) is True
    # One call, with both disks and both paths passed as lists (is_child does the product)
    assert calls == [(["/mnt/tank/a", "/mnt/tank/b.img"], ["/mnt/tank"])]


@pytest.mark.asyncio
async def test_vm_on_paths_no_disks_does_not_call_is_child():
    m = Middleware()

    def fail_is_child(*args):
        raise AssertionError("filesystem.is_child should not be called when the VM has no disks")

    m["filesystem.is_child"] = fail_is_child
    delegate = VMFSAttachmentDelegate(m)

    assert await delegate.vm_on_paths({"devices": [disk("NIC", "/dev/net")]}, {"/mnt/tank"}) is False


@pytest.mark.asyncio
async def test_storage_locked_only_considers_disk_and_raw():
    m = Middleware()
    locked = set()
    m["pool.dataset.path_in_locked_datasets"] = lambda path: path in locked
    delegate = VMFSAttachmentDelegate(m)
    vm = {"devices": [disk("DISK", "/mnt/tank/a"), disk("RAW", "/mnt/other/b.img")]}

    assert await delegate.storage_locked(vm) is False

    locked.add("/mnt/other/b.img")
    assert await delegate.storage_locked(vm) is True

    # A locked CDROM (removable) must not block the VM from starting
    cdrom_vm = {"devices": [disk("CDROM", "/mnt/other/b.img")]}
    assert await delegate.storage_locked(cdrom_vm) is False
