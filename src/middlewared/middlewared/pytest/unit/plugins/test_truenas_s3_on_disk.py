"""The bucket row middleware keeps on a bucket's dataset: the whole of
what `sharing.s3.recover` reads. Anything it cannot read whole reads as
absent."""

import errno
import json
import os

import pytest

from middlewared.plugins.truenas_s3.on_disk import (
    CONFIG_BACKUP,
    CONFIG_VERSION,
    LATCH_XATTR,
    SIDE_TREE,
    has_latch,
    read_config_backup,
    write_config_backup,
)

ROW = {
    "name": "backups",
    "dataset": "tank/s3/backups",
    "enabled": True,
    "owner_uid": 3001,
    "grants": [{"principal_type": "EVERYONE", "xid": None, "access": "READONLY"}],
    "permissions_model": "S3",
    "object_ownership": "BUCKET_OWNER_ENFORCED",
    "versioning": "SUSPENDED",
    "snapshot_versions": [],
    "snapshot_versions_max": 64,
    "multipart_etag": "COMPOSITE",
    "object_lock": False,
    "object_lock_default_mode": None,
    "object_lock_default_days": None,
    "audit": None,
    "audit_overflow": None,
}


def test_the_backup_round_trips_through_the_side_tree(tmp_path):
    mount = str(tmp_path)
    assert read_config_backup(mount) is None, "a dataset with no side tree holds no backup"

    write_config_backup(mount, ROW)
    side = tmp_path / SIDE_TREE
    assert side.is_dir()
    # registration refuses a side tree owned by anyone but the daemon
    assert side.stat().st_mode & 0o7777 == 0o700
    assert (side / CONFIG_BACKUP).stat().st_mode & 0o7777 == 0o600

    assert read_config_backup(mount) == {**ROW, "version_number": CONFIG_VERSION}


def test_the_backup_is_rewritten_in_place(tmp_path):
    mount = str(tmp_path)
    write_config_backup(mount, ROW)
    write_config_backup(mount, {**ROW, "name": "renamed"})
    assert read_config_backup(mount)["name"] == "renamed"
    assert os.listdir(tmp_path / SIDE_TREE) == [CONFIG_BACKUP], "no temporary file is left behind"


def test_an_existing_side_tree_is_used_as_found(tmp_path):
    # registration made it, and its contents are the S3 service's
    side = tmp_path / SIDE_TREE
    side.mkdir(mode=0o700)
    (side / "h1").mkdir()
    write_config_backup(str(tmp_path), ROW)
    assert sorted(os.listdir(side)) == [CONFIG_BACKUP, "h1"]


@pytest.mark.parametrize(
    "raw",
    [
        "{not json",
        '["a list"]',
        json.dumps({**ROW, "version_number": CONFIG_VERSION + 1}),
        json.dumps(ROW),
    ],
)
def test_a_backup_this_version_cannot_read_whole_reads_as_absent(tmp_path, raw):
    side = tmp_path / SIDE_TREE
    side.mkdir(mode=0o700)
    (side / CONFIG_BACKUP).write_text(raw)
    assert read_config_backup(str(tmp_path)) is None


def test_the_object_lock_latch_is_read_for_its_presence(tmp_path, monkeypatch):
    store: dict[str, bytes] = {}

    def fgetxattr(fd, name):
        try:
            return store[name]
        except KeyError:
            raise OSError(errno.ENODATA, "No data available")

    monkeypatch.setattr("truenas_os.fgetxattr", fgetxattr)
    assert has_latch(str(tmp_path)) is False
    # whatever it holds: the record is the S3 service's to decode
    store[LATCH_XATTR] = b"\x00"
    assert has_latch(str(tmp_path)) is True


def test_a_mount_point_that_is_not_there_holds_no_latch(tmp_path):
    # a dataset that is not mounted, which `force_disable_versioning`
    # reaches whenever ZFS reports a mount point for one
    assert has_latch(str(tmp_path / "not-mounted")) is False
    not_a_directory = tmp_path / "file"
    not_a_directory.write_text("")
    assert has_latch(str(not_a_directory)) is False


def test_a_latch_read_that_is_not_enodata_raises(tmp_path, monkeypatch):
    def fgetxattr(fd, name):
        raise OSError(errno.EIO, "I/O error")

    monkeypatch.setattr("truenas_os.fgetxattr", fgetxattr)
    # absence must not be guessed: it would disarm the latch
    with pytest.raises(OSError):
        has_latch(str(tmp_path))
