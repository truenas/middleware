import contextlib
import errno
import pprint
import time

import pytest

from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.test.integration.assets.iscsi import iscsi_extent
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.unittest import RegexString

MiB = 1024**2
SETTLE = 5
HIDDEN_MESSAGE = (
    "has snapshots which have attachments being used. Before marking it as HIDDEN, remove attachment usages."
)


def volume(name, **data):
    return dataset(name, {"type": "VOLUME", "volsize": 64 * MiB, "volblocksize": "16K", "sparse": True, **data})


def wait_for_device(name):
    for _ in range(30):
        if ssh(f"test -e /dev/zvol/{name} && echo present || true").strip() == "present":
            return
        time.sleep(0.5)
    raise AssertionError(f"/dev/zvol/{name} never appeared")


@contextlib.contextmanager
def snapshot_extent(zvol):
    call("zfs.resource.set", {"path": zvol, "properties": {"snapdev": "visible"}})
    call("zfs.resource.snapshot.create", {"dataset": zvol, "name": "snap"})
    wait_for_device(f"{zvol}@snap")
    with iscsi_extent({"name": "zre_snapshot_extent", "type": "DISK", "disk": f"zvol/{zvol}@snap", "ro": True}):
        yield


def read(path, name):
    return call("zfs.resource.list", {"paths": [path], "properties": [name], "get_source": True})[0]["properties"][name]


@contextlib.contextmanager
def iscsitarget():
    call("service.control", "START", "iscsitarget", job=True)
    try:
        yield
    finally:
        call("service.control", "STOP", "iscsitarget", job=True)


def test_delegates_are_registered():
    assert set(call("zfs.resource.delegates")) == {"iscsi.extent", "nvmet.namespace", "smb.share", "vm.device"}


def test_acltype_change_under_smb_shares_is_rejected():
    with dataset("zre_smb_acltype", {"acltype": "POSIX", "aclmode": "DISCARD"}) as ds:
        with smb_share(f"/mnt/{ds}", "ZRE_SHARE_1"):
            with smb_share(f"/mnt/{ds}", "ZRE_SHARE_2"):
                with pytest.raises(ValidationErrors) as ve:
                    call("zfs.resource.set", {"path": ds, "properties": {"acltype": "off"}})

                assert ve.value.errors == [
                    ValidationError(
                        "zfs.resource.set.properties.acltype",
                        RegexString("This dataset is hosting SMB shares. .*"),
                        errno.EINVAL,
                    )
                ]
                assert "ZRE_SHARE_1, ZRE_SHARE_2" in ve.value.errors[0].errmsg


def test_acltype_no_op_under_smb_shares_is_accepted():
    with dataset("zre_smb_acltype_noop", {"acltype": "POSIX", "aclmode": "DISCARD"}) as ds:
        with smb_share(f"/mnt/{ds}", "ZRE_SHARE_1"):
            with smb_share(f"/mnt/{ds}", "ZRE_SHARE_2"):
                call("zfs.resource.set", {"path": ds, "properties": {"acltype": "posix"}})
                assert read(ds, "acltype")["raw"] == "posix"


def test_volsize_grow_resyncs_the_iscsi_extent_size():
    if call("iscsi.global.lio_enabled"):
        pytest.skip("reads the SCST device size")

    with volume("zre_iscsi_volsize") as zvol:
        with iscsi_extent({"name": "zre_volsize_extent", "type": "DISK", "disk": f"zvol/{zvol}"}):
            with iscsitarget():
                size = "/sys/kernel/scst_tgt/devices/zre_volsize_extent/size"
                assert int(ssh(f"cat {size}").split()[0]) == 64 * MiB

                call("zfs.resource.set", {"path": zvol, "properties": {"volsize": 128 * MiB}})

                assert int(ssh(f"cat {size}").split()[0]) == 128 * MiB


def test_readonly_on_an_extent_zvol_emits_one_changed_and_syncs_the_extent():
    with volume("zre_iscsi_readonly") as zvol:
        with iscsi_extent({"name": "zre_readonly_extent", "type": "DISK", "disk": f"zvol/{zvol}"}) as extent:
            assert extent["ro"] is False
            events = []

            def collect(mtype, **message):
                if message.get("id") == zvol:
                    events.append((mtype, message))

            with client() as c:
                c.subscribe("zfs.resource.list", collect, sync=True)
                call("zfs.resource.set", {"path": zvol, "properties": {"readonly": "on"}})
                time.sleep(SETTLE)

            assert [mtype for mtype, _ in events] == ["CHANGED"], pprint.pformat(events)
            assert call("iscsi.extent.get_instance", extent["id"])["ro"] is True


def test_hiding_snapshot_devices_backing_an_extent_is_rejected():
    with volume("zre_iscsi_snapdev") as zvol:
        with snapshot_extent(zvol):
            with pytest.raises(ValidationErrors) as ve:
                call("zfs.resource.set", {"path": zvol, "properties": {"snapdev": "hidden"}})

            assert ve.value.errors == [
                ValidationError("zfs.resource.set.properties.snapdev", f"{zvol!r} {HIDDEN_MESSAGE}", errno.EINVAL)
            ]


def test_inheriting_visible_snapdev_under_an_extent_is_accepted():
    with dataset("zre_snapdev_parent") as parent:
        call("zfs.resource.set", {"path": parent, "properties": {"snapdev": "visible"}})
        with volume("zre_snapdev_parent/zvol") as zvol:
            with snapshot_extent(zvol):
                call("zfs.resource.set", {"path": zvol, "inherit": ["snapdev"]})

                snapdev = read(zvol, "snapdev")
                assert snapdev["raw"] == "visible"
                assert snapdev["source"]["type"] == "INHERITED"
