import errno
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from middlewared.api.current import VMDiskDevice
from middlewared.plugins.vm import vm_device_convert
from middlewared.plugins.vm.vm_device_convert import validate_convert_disk_image, validate_convert_zvol
from middlewared.service import CallError
from middlewared.service_exception import ValidationError

SCHEMA = "vm.device.convert.destination"


# validate_convert_disk_image checks the destination directory, not its parent


def _disk_image_context(dip, sp, source):
    """Mock context whose filesystem.stat/statfs answer only for `dip` and `sp`.

    Any stat of a different path (e.g. the grandparent `/mnt`) trips an
    AssertionError, which is exactly the off-by-one regression we are guarding.
    """

    def fake_call_sync(method, path):
        if method == "filesystem.stat":
            if path == dip:
                # zvol -> image: the destination file need not exist yet.
                raise CallError(f"{dip} does not exist", errno.ENOENT)
            if path == sp:
                return SimpleNamespace(type="DIRECTORY", realpath=sp, uid=0, gid=0)
            raise AssertionError(f"unexpected filesystem.stat of {path!r}")
        if method == "filesystem.statfs":
            assert path == sp, f"statfs should target {sp!r}, got {path!r}"
            return SimpleNamespace(source=source)
        raise AssertionError(f"unexpected call {method!r}")

    context = Mock()
    context.middleware.call_sync = Mock(side_effect=fake_call_sync)
    context.logger = Mock()
    return context


def test_zvol_to_image_pool_root_destination_is_allowed():
    # /mnt/tank/foo.qcow2 must validate the pool dir /mnt/tank, not the boot-pool /mnt.
    dip, sp = "/mnt/tank/foo.qcow2", "/mnt/tank"
    context = _disk_image_context(dip, sp, source="tank")

    assert validate_convert_disk_image(context, dip, SCHEMA, converting_from_image_to_zvol=False) is None

    stat_paths = [c.args[1] for c in context.middleware.call_sync.call_args_list if c.args[0] == "filesystem.stat"]
    assert sp in stat_paths
    assert "/mnt" not in stat_paths  # the grandparent must never be checked


def test_zvol_to_image_internal_dataset_destination_is_rejected():
    # /mnt/tank/ix-apps/foo.qcow2 sits in an internal dataset and must be rejected,
    # which the old grandparent check (statting /mnt/tank) would have missed.
    dip, sp = "/mnt/tank/ix-apps/foo.qcow2", "/mnt/tank/ix-apps"
    context = _disk_image_context(dip, sp, source="tank/ix-apps")

    with pytest.raises(ValidationError) as exc:
        validate_convert_disk_image(context, dip, SCHEMA, converting_from_image_to_zvol=False)
    assert exc.value.errno == errno.EACCES


# validate_convert_zvol blocks conversion of any active VM's zvol


def _zvol_context(state):
    zv = [{"type": "VOLUME", "name": "tank/foo", "properties": {"volsize": {"value": 1024**3}}}]
    device = SimpleNamespace(attributes=VMDiskDevice(dtype="DISK", path="/dev/zvol/tank/foo"), vm=1)
    vm = SimpleNamespace(name="myvm", status=SimpleNamespace(state=state))

    context = Mock()

    def fake_call_sync2(target, *args, **kwargs):
        if target is context.s.zfs.resource.query_impl:
            return zv
        if target is context.s.vm.device.query:
            return [device]
        if target is context.s.vm.get_instance:
            return vm
        raise AssertionError(f"unexpected call_sync2 target: {target!r}")

    context.call_sync2 = Mock(side_effect=fake_call_sync2)
    context.logger = Mock()
    return context


@pytest.mark.parametrize("state", ["RUNNING", "SUSPENDED"])
def test_convert_zvol_blocked_for_active_vm(state):
    context = _zvol_context(state)
    with patch.object(vm_device_convert.os.path, "exists", return_value=True):
        with pytest.raises(ValidationError) as exc:
            validate_convert_zvol(context, "/dev/zvol/tank/foo", SCHEMA)
    assert exc.value.errno == errno.EBUSY
    assert state.lower() in exc.value.errmsg


def test_convert_zvol_allowed_for_stopped_vm():
    context = _zvol_context("STOPPED")
    with patch.object(vm_device_convert.os.path, "exists", return_value=True):
        zv, ntp = validate_convert_zvol(context, "/dev/zvol/tank/foo", SCHEMA)
    assert zv["type"] == "VOLUME"
    assert ntp == "/dev/zvol/tank/foo"
