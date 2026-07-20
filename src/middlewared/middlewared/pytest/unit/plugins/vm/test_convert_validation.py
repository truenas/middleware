import errno
from unittest.mock import Mock, patch

import pytest

from middlewared.plugins.vm import vm_devices
from middlewared.plugins.vm.vm_devices import VMDeviceService
from middlewared.service import CallError
from middlewared.service_exception import ValidationError

SCHEMA = "vm.device.convert.destination"


# validate_convert_disk_image checks the destination directory, not its parent


def _disk_image_service(dip, sp, source):
    """Mock service whose filesystem.stat/statfs answer only for `dip` and `sp`.

    Any stat of a different path (e.g. the grandparent `/mnt`) trips an
    AssertionError, which is exactly the off-by-one regression we are guarding.
    """

    def fake_call_sync(method, path):
        if method == "filesystem.stat":
            if path == dip:
                # zvol -> image: the destination file need not exist yet.
                raise CallError(f"{dip} does not exist", errno.ENOENT)
            if path == sp:
                return {"type": "DIRECTORY", "realpath": sp, "uid": 0, "gid": 0}
            raise AssertionError(f"unexpected filesystem.stat of {path!r}")
        if method == "filesystem.statfs":
            assert path == sp, f"statfs should target {sp!r}, got {path!r}"
            return {"source": source}
        raise AssertionError(f"unexpected call {method!r}")

    svc = Mock()
    svc.middleware.call_sync = Mock(side_effect=fake_call_sync)
    svc.logger = Mock()
    return svc


def test_zvol_to_image_pool_root_destination_is_allowed():
    # /mnt/tank/foo.qcow2 must validate the pool dir /mnt/tank, not the boot-pool /mnt.
    dip, sp = "/mnt/tank/foo.qcow2", "/mnt/tank"
    svc = _disk_image_service(dip, sp, source="tank")

    assert VMDeviceService.validate_convert_disk_image(svc, dip, SCHEMA, converting_from_image_to_zvol=False) is None

    stat_paths = [c.args[1] for c in svc.middleware.call_sync.call_args_list if c.args[0] == "filesystem.stat"]
    assert sp in stat_paths
    assert "/mnt" not in stat_paths  # the grandparent must never be checked


def test_zvol_to_image_internal_dataset_destination_is_rejected():
    # /mnt/tank/ix-apps/foo.qcow2 sits in an internal dataset and must be rejected,
    # which the old grandparent check (statting /mnt/tank) would have missed.
    dip, sp = "/mnt/tank/ix-apps/foo.qcow2", "/mnt/tank/ix-apps"
    svc = _disk_image_service(dip, sp, source="tank/ix-apps")

    with pytest.raises(ValidationError) as exc:
        VMDeviceService.validate_convert_disk_image(svc, dip, SCHEMA, converting_from_image_to_zvol=False)
    assert exc.value.errno == errno.EACCES


# validate_convert_zvol blocks conversion of any active VM's zvol


def _zvol_service(state):
    zv = [{"type": "VOLUME", "name": "tank/foo", "properties": {"volsize": {"value": 1024**3}}}]
    device = {"attributes": {"dtype": "DISK", "path": "/dev/zvol/tank/foo"}, "vm": 1}
    vm = {"name": "myvm", "status": {"state": state}}

    svc = Mock()

    def fake_call_sync2(target, *args, **kwargs):
        if target is svc.s.zfs.resource.query_impl:
            return zv
        raise AssertionError(f"unexpected call_sync2 target: {target!r}")

    def fake_call_sync(method, *args, **kwargs):
        if method == "vm.device.query":
            return [device]
        if method == "vm.get_instance":
            return vm
        raise AssertionError(f"unexpected call_sync {method!r}")

    svc.call_sync2 = Mock(side_effect=fake_call_sync2)
    svc.middleware.call_sync = Mock(side_effect=fake_call_sync)
    svc.logger = Mock()
    return svc


@pytest.mark.parametrize("state", ["RUNNING", "SUSPENDED"])
def test_convert_zvol_blocked_for_active_vm(state):
    svc = _zvol_service(state)
    with patch.object(vm_devices.os.path, "exists", return_value=True):
        with pytest.raises(ValidationError) as exc:
            VMDeviceService.validate_convert_zvol(svc, "/dev/zvol/tank/foo", SCHEMA)
    assert exc.value.errno == errno.EBUSY
    assert state.lower() in exc.value.errmsg


def test_convert_zvol_allowed_for_stopped_vm():
    svc = _zvol_service("STOPPED")
    with patch.object(vm_devices.os.path, "exists", return_value=True):
        zv, ntp = VMDeviceService.validate_convert_zvol(svc, "/dev/zvol/tank/foo", SCHEMA)
    assert zv["type"] == "VOLUME"
    assert ntp == "/dev/zvol/tank/foo"
