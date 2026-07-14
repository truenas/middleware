import pytest

from middlewared.api.current import (
    VMCDROMDevice,
    VMDeviceEntry,
    VMDiskDevice,
    VMEntry,
    VMNICDevice,
    VMRAWDevice,
    VMStatus,
)
from middlewared.plugins.vm.attachments import VMFSAttachmentDelegate
from middlewared.pytest.unit.middleware import Middleware

ATTRIBUTES = {
    "DISK": VMDiskDevice,
    "RAW": VMRAWDevice,
    "CDROM": VMCDROMDevice,
    "NIC": VMNICDevice,
}


def device(dtype, **attributes):
    return VMDeviceEntry.model_construct(
        id=1, vm=1, order=1, attributes=ATTRIBUTES[dtype].model_construct(dtype=dtype, **attributes)
    )


def disk(dtype, path):
    return device(dtype, path=path)


def vm(devices, state="STOPPED"):
    return VMEntry.model_construct(id=1, name="myvm", devices=devices, status=VMStatus.model_construct(state=state))


@pytest.mark.parametrize(
    "dev, expected",
    (
        # zvol-backed disks are normalized from /dev/zvol/<ds> to /mnt/<ds>
        (disk("DISK", "/dev/zvol/tank/vm-disk"), "/mnt/tank/vm-disk"),
        (disk("RAW", "/mnt/tank/vm/disk.img"), "/mnt/tank/vm/disk.img"),
        (disk("CDROM", "/mnt/tank/os.iso"), "/mnt/tank/os.iso"),
        # not disk-backed / no usable path
        (device("NIC"), None),
        (disk("DISK", None), None),
        (disk("DISK", ""), None),
    ),
)
def test_device_disk_path(dev, expected):
    delegate = VMFSAttachmentDelegate(Middleware())
    assert delegate.device_disk_path(dev) == expected


def test_disk_paths_keeps_only_disk_and_raw():
    delegate = VMFSAttachmentDelegate(Middleware())
    assert delegate.disk_paths(
        vm(
            [
                disk("DISK", "/dev/zvol/tank/a"),
                disk("RAW", "/mnt/tank/b.img"),
                disk("CDROM", "/mnt/tank/c.iso"),  # removable, excluded
                device("NIC"),  # not storage, excluded
            ]
        )
    ) == ["/mnt/tank/a", "/mnt/tank/b.img"]


@pytest.mark.asyncio
async def test_vm_on_paths_matches_in_a_single_is_child_call():
    m = Middleware()
    calls = []

    def fake_is_child(child, parent):
        calls.append((child, parent))
        return True

    m["filesystem.is_child"] = fake_is_child
    delegate = VMFSAttachmentDelegate(m)

    assert (
        await delegate.vm_on_paths(
            vm([disk("DISK", "/dev/zvol/tank/a"), disk("RAW", "/mnt/tank/b.img")]), {"/mnt/tank"}
        )
        is True
    )
    # One call, with both disks and both paths passed as lists (is_child does the product)
    assert calls == [(["/mnt/tank/a", "/mnt/tank/b.img"], ["/mnt/tank"])]


@pytest.mark.asyncio
async def test_vm_on_paths_no_disks_does_not_call_is_child():
    m = Middleware()

    def fail_is_child(*args):
        raise AssertionError("filesystem.is_child should not be called when the VM has no disks")

    m["filesystem.is_child"] = fail_is_child
    delegate = VMFSAttachmentDelegate(m)

    assert await delegate.vm_on_paths(vm([device("NIC")]), {"/mnt/tank"}) is False


@pytest.mark.asyncio
async def test_storage_locked_only_considers_disk_and_raw():
    m = Middleware()
    locked = set()
    m["pool.dataset.path_in_locked_datasets"] = lambda path: path in locked
    delegate = VMFSAttachmentDelegate(m)
    test_vm = vm([disk("DISK", "/mnt/tank/a"), disk("RAW", "/mnt/other/b.img")])

    assert await delegate.storage_locked(test_vm) is False

    locked.add("/mnt/other/b.img")
    assert await delegate.storage_locked(test_vm) is True

    # A locked CDROM (removable) must not block the VM from starting
    assert await delegate.storage_locked(vm([disk("CDROM", "/mnt/other/b.img")])) is False


class StopJob:
    error = None

    async def wait(self, *args, **kwargs):
        return None


class StartOnUnlockDriver:
    """Drives `start_on_unlock` against a single autostart VM, recording the actions it takes."""

    def __init__(self, state, devices=None, locked_paths=()):
        self.actions: list[str] = []
        self.vm = vm(devices or [disk("RAW", "/mnt/tank/ds/disk.img")], state=state)
        self.middleware = Middleware()
        self.middleware["filesystem.is_child"] = lambda child, parent: True
        self.middleware["pool.dataset.path_in_locked_datasets"] = lambda path: path in locked_paths
        self.middleware.services.vm.query = lambda *args: [self.vm]
        self.middleware.services.vm.status = lambda *args: self.vm.status
        self.middleware.services.vm.start = self._record("start")
        self.middleware.services.vm.stop = self._record("stop")
        self.delegate = VMFSAttachmentDelegate(self.middleware)

    def _record(self, action):
        def record(*args):
            self.actions.append(action)
            return StopJob()

        return record

    async def run(self):
        await self.delegate.start_on_unlock([({"name": "tank/ds", "type": "FILESYSTEM"}, "/mnt/tank/ds")])
        return self.actions


@pytest.mark.asyncio
async def test_start_on_unlock_starts_stopped_vm():
    assert await StartOnUnlockDriver("STOPPED").run() == ["start"]


@pytest.mark.asyncio
async def test_start_on_unlock_bounces_running_vm():
    # A running VM is stopped first so that it comes back up on the freshly mounted storage
    assert await StartOnUnlockDriver("RUNNING").run() == ["stop", "start"]


@pytest.mark.asyncio
async def test_start_on_unlock_leaves_suspended_vm_paused():
    assert await StartOnUnlockDriver("SUSPENDED").run() == []


@pytest.mark.asyncio
async def test_start_on_unlock_defers_while_another_disk_is_locked():
    # Both disks are needed, so the VM must not boot while the second one's dataset is still locked
    assert (
        await StartOnUnlockDriver(
            "STOPPED",
            devices=[disk("RAW", "/mnt/tank/ds/disk.img"), disk("RAW", "/mnt/other/disk.img")],
            locked_paths=("/mnt/other/disk.img",),
        ).run()
        == []
    )


@pytest.mark.asyncio
async def test_start_on_unlock_ignores_vm_not_on_unlocked_paths():
    driver = StartOnUnlockDriver("STOPPED")
    driver.middleware["filesystem.is_child"] = lambda child, parent: False
    assert await driver.run() == []
