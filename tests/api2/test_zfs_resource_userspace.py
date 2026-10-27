import errno

import pytest
from auto_config import pool_name
from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call

UID = 4000
GID = 4001


def userspace(path, types=("user", "group")):
    rows = call("zfs.resource.userspace.list", {"paths": [path], "types": list(types)})
    return {(row["type"], row["xid"]): row for row in rows}


def test_set_and_list_user_and_group_limits():
    with dataset("userspace_round_trip") as ds:
        call(
            "zfs.resource.userspace.set",
            {
                "path": ds,
                "quotas": [
                    {"type": "user", "xid": UID, "quota": "10M", "objquota": 100},
                    {"type": "group", "xid": GID, "quota": 20 * 1024 * 1024},
                ],
            },
        )
        rows = userspace(ds)
        assert rows[("user", UID)] == {
            "dataset": ds,
            "type": "user",
            "xid": UID,
            "used": 0,
            "quota": 10 * 1024 * 1024,
            "objused": 0,
            "objquota": 100,
        }
        assert (rows[("group", GID)]["quota"], rows[("group", GID)]["objquota"]) == (20 * 1024 * 1024, 0)


def test_null_leaves_the_other_limit_unchanged():
    with dataset("userspace_null") as ds:
        call("zfs.resource.userspace.set", {"path": ds, "quotas": [{"type": "user", "xid": UID, "quota": "1M"}]})
        call("zfs.resource.userspace.set", {"path": ds, "quotas": [{"type": "user", "xid": UID, "objquota": 50}]})
        row = userspace(ds, ["user"])[("user", UID)]
        assert (row["quota"], row["objquota"]) == (1024 * 1024, 50)


@pytest.mark.parametrize("removal", [0, "none"])
def test_zero_or_none_removes_a_limit(removal):
    with dataset("userspace_remove") as ds:
        call(
            "zfs.resource.userspace.set",
            {"path": ds, "quotas": [{"type": "user", "xid": UID, "quota": "1M", "objquota": 50}]},
        )
        call(
            "zfs.resource.userspace.set",
            {"path": ds, "quotas": [{"type": "user", "xid": UID, "quota": removal, "objquota": removal}]},
        )
        assert ("user", UID) not in userspace(ds, ["user"])


def test_missing_path_is_skipped_by_list_and_refused_by_set():
    path = f"{pool_name}/userspace_does_not_exist"
    assert call("zfs.resource.userspace.list", {"paths": [path], "types": ["user"]}) == []
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.userspace.set", {"path": path, "quotas": [{"type": "user", "xid": UID, "quota": "1M"}]})
    assert (ve.value.attribute, ve.value.errno) == ("zfs.resource.userspace.set.path", errno.ENOENT)


def test_volume_is_refused():
    with dataset("userspace_zvol", {"type": "VOLUME", "volsize": 1024 * 1024 * 16, "sparse": True}) as zvol:
        with pytest.raises(ValidationError) as ve:
            call("zfs.resource.userspace.list", {"paths": [zvol], "types": ["user"]})
        assert (ve.value.attribute, ve.value.errno) == ("zfs.resource.userspace.list", errno.EINVAL)
        with pytest.raises(ValidationError) as ve:
            call("zfs.resource.userspace.set", {"path": zvol, "quotas": [{"type": "user", "xid": UID, "quota": "1M"}]})
        assert (ve.value.attribute, ve.value.errno) == ("zfs.resource.userspace.set.path", errno.EINVAL)


def test_snapshot_path_is_refused():
    with dataset("userspace_snap") as ds:
        with snapshot(ds, "snap") as snap:
            with pytest.raises(ValidationError) as ve:
                call("zfs.resource.userspace.list", {"paths": [snap], "types": ["user"]})
            assert (ve.value.attribute, ve.value.errno) == ("zfs.resource.userspace.list", errno.EINVAL)
            with pytest.raises(ValidationError) as ve:
                call(
                    "zfs.resource.userspace.set",
                    {"path": snap, "quotas": [{"type": "user", "xid": UID, "quota": "1M"}]},
                )
            assert (ve.value.attribute, ve.value.errno) == ("zfs.resource.userspace.set.path", errno.EINVAL)


def test_protected_path_is_readable_but_not_writable():
    call("zfs.resource.userspace.list", {"paths": ["boot-pool"], "types": ["user"]})
    with pytest.raises(ValidationError) as ve:
        call(
            "zfs.resource.userspace.set",
            {"path": "boot-pool", "quotas": [{"type": "user", "xid": UID, "quota": "1M"}]},
        )
    assert (ve.value.attribute, ve.value.errno) == ("zfs.resource.userspace.set.path", errno.EACCES)


@pytest.mark.parametrize("type_", ["user", "group"])
def test_id_zero_is_refused(type_):
    with dataset("userspace_id_zero") as ds:
        with pytest.raises(ValidationError) as ve:
            call("zfs.resource.userspace.set", {"path": ds, "quotas": [{"type": type_, "xid": 0, "quota": "1M"}]})
        assert ve.value.attribute == "zfs.resource.userspace.set.quotas.0.xid"
        assert ve.value.errmsg == f"Quotas cannot be set on {type_} id 0."


def test_locked_filesystem_is_refused_by_list():
    encryption = {
        "encryption": True,
        "inherit_encryption": False,
        "encryption_options": {"generate_key": False, "passphrase": "12345678"},
    }
    with dataset("userspace_locked", encryption) as ds:
        call("pool.dataset.lock", ds, job=True)
        with pytest.raises(ValidationError) as ve:
            call("zfs.resource.userspace.list", {"paths": [ds], "types": ["user"]})
        assert (ve.value.attribute, ve.value.errno) == ("zfs.resource.userspace.list", errno.EACCES)
