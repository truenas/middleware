import errno
import os

import pytest

from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.zfs_resource import zfs_resource
from middlewared.test.integration.utils import call, ssh

from auto_config import pool_name


def mounted(path: str) -> bool:
    rv = call("zfs.resource.list", {"paths": [path], "properties": ["mounted"]})
    return rv[0]["properties"]["mounted"]["value"] is True


def test_unmount_then_mount_roundtrip():
    with dataset("test_mnt_roundtrip") as ds:
        assert mounted(ds)
        call("zfs.resource.unmount", ds)
        assert not mounted(ds)
        call("zfs.resource.mount", ds)
        assert mounted(ds)


def test_unmount_lazy_then_mount():
    with dataset("test_mnt_lazy") as ds:
        call("zfs.resource.unmount", ds, None, False, False, True)
        assert not mounted(ds)
        call("zfs.resource.mount", ds)
        assert mounted(ds)


def test_unmount_force_while_busy():
    with dataset("test_mnt_force") as ds:
        ssh(f"touch /mnt/{ds}/file")
        call("zfs.resource.unmount", ds, None, False, True)
        assert not mounted(ds)
        call("zfs.resource.mount", ds)
        assert mounted(ds)


def test_unmount_and_mount_recursive():
    with dataset("test_mnt_rec") as parent:
        child = f"{parent}/child"
        call("pool.dataset.create", {"name": child})
        call("zfs.resource.unmount", parent, None, True)
        assert not mounted(parent)
        assert not mounted(child)

        call("zfs.resource.mount", parent, None, True)
        assert mounted(parent)
        assert mounted(child)


def test_mount_at_explicit_mountpoint():
    with dataset("test_mnt_explicit") as ds:
        alt = "/mnt/test_mnt_explicit_alt"
        call("zfs.resource.unmount", ds)
        ssh(f"mkdir -p {alt}")
        try:
            call("zfs.resource.mount", ds, alt)
            assert ssh(f"findmnt -n -o SOURCE {alt}").strip() == ds
        finally:
            call("zfs.resource.unmount", ds, alt)
            ssh(f"rmdir {alt}")
        call("zfs.resource.mount", ds)


def test_mount_with_mount_options():
    with dataset("test_mnt_options") as ds:
        call("zfs.resource.unmount", ds)
        call("zfs.resource.mount", ds, None, False, ["ro"])
        try:
            opts = ssh(f"findmnt -n -o OPTIONS /mnt/{ds}")
            assert "ro" in opts.split(",")
        finally:
            call("zfs.resource.unmount", ds)
            call("zfs.resource.mount", ds)


def test_mount_force_mounts_canmount_off():
    with dataset("test_mnt_canmount") as ds:
        call("zfs.resource.unmount", ds)
        ssh(f"zfs set canmount=off {ds}")
        call("zfs.resource.mount", ds, None, False, None, True)
        try:
            assert mounted(ds)
        finally:
            call("zfs.resource.unmount", ds)
            ssh(f"zfs set canmount=on {ds}")


def test_mount_nonexistent_raises_enoent():
    path = os.path.join(pool_name, "test_mnt_missing")
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.mount", path)
    assert ve.value.errmsg == f"{path!r} not found"
    assert ve.value.errno == errno.ENOENT


def test_mount_empty_filesystem_is_rejected():
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.mount", "")
    assert ve.value.attribute == "zfs.resource.mount"
    assert ve.value.errmsg == "'filesystem' key is required"


def test_unmount_nonexistent_raises_enoent():
    path = os.path.join(pool_name, "test_umnt_missing")
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.unmount", path)
    assert ve.value.errmsg == f"{path!r} not found"
    assert ve.value.errno == errno.ENOENT


def test_unmount_empty_filesystem_is_rejected():
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.unmount", "")
    assert ve.value.attribute == "zfs.resource.unmount"
    assert ve.value.errmsg == "'filesystem' key is required"


def test_unload_key_nonexistent_raises_enoent():
    path = os.path.join(pool_name, "test_unload_missing")
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.unload_key", path)
    assert ve.value.errmsg == f"{path!r} not found"
    assert ve.value.errno == errno.ENOENT


def test_unload_key_empty_filesystem_is_rejected():
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.unload_key", "")
    assert ve.value.attribute == "zfs.resource.unload_key"
    assert ve.value.errmsg == "'filesystem' key is required"


def keystatus(path: str) -> str:
    rv = call("zfs.resource.list", {"paths": [path], "properties": ["keystatus"]})
    return rv[0]["properties"]["keystatus"]["raw"]


def test_unmount_unloads_the_key_and_mount_loads_it_back():
    """An encryption root can drop and reload its key around a remount"""
    key = "a" * 64
    path = os.path.join(pool_name, "test_mnt_encrypted")
    keyfile = "/tmp/test_mnt_encrypted.key"
    with zfs_resource(path, {"encryption": {"key": key}}):
        try:
            ssh(f"printf '{key}' > {keyfile}")
            ssh(f"zfs set keylocation=file://{keyfile} {path}")

            call("zfs.resource.unmount", path, None, False, False, False, True)
            assert not mounted(path)
            assert keystatus(path) == "unavailable"

            call("zfs.resource.mount", path, None, False, None, False, True)
            assert mounted(path)
            assert keystatus(path) == "available"
        finally:
            ssh(f"rm -f {keyfile}")


def test_unload_key_drops_the_key_of_an_unmounted_encryption_root():
    key = "b" * 64
    path = os.path.join(pool_name, "test_unload_encrypted")
    with zfs_resource(path, {"encryption": {"key": key}}):
        assert keystatus(path) == "available"
        call("zfs.resource.unload_key", path, False, True)
        assert keystatus(path) == "unavailable"
        assert not mounted(path)
