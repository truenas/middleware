import errno

import pytest
from auto_config import pool_name

from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import _4_disk_raidz2_topology, another_pool, dataset
from middlewared.test.integration.utils import call, ssh


def test_recommended_zvol_blocksize_raidz2_pool():
    with another_pool(topology=_4_disk_raidz2_topology) as pool:
        assert call("zfs.resource.recommended_zvol_blocksize", pool["name"]) == "16K"


def test_recommended_zvol_blocksize_nonexistent_pool():
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.recommended_zvol_blocksize", "nonexistent_pool")

    assert ve.value.attribute == "zfs.resource.recommended_zvol_blocksize.pool"
    assert ve.value.errmsg == "'nonexistent_pool' does not exist"
    assert ve.value.errno == errno.ENOENT


def test_zfs_resource_processes_idle_dataset():
    """A dataset nothing is holding open reports no processes, through either namespace."""
    with dataset("test_processes_idle") as ds:
        assert call("zfs.resource.processes", ds) == []
        assert call("pool.dataset.processes", ds) == []


def test_zfs_resource_processes_volume():
    """A volume is scanned as a block device."""
    with dataset("test_processes_zvol", {"type": "VOLUME", "volsize": 100 * 1024 * 1024}) as zvol:
        assert call("zfs.resource.processes", zvol) == []


def test_zfs_resource_processes_holder_is_reported():
    """A process holding a file on the dataset open is reported with its pid."""
    with dataset("test_processes_held") as ds:
        ssh(f"touch /mnt/{ds}/holdme")
        pid = int(ssh(f"( tail -f /mnt/{ds}/holdme >/dev/null 2>&1 & echo $! )").strip())
        try:
            assert pid in [p["pid"] for p in call("zfs.resource.processes", ds)]
        finally:
            ssh(f"kill {pid}")


def test_zfs_resource_processes_locked_dataset():
    """A locked dataset reports no processes rather than failing."""
    encrypted = f"{pool_name}/test_processes_locked"
    call(
        "pool.dataset.create",
        {
            "name": encrypted,
            "encryption": True,
            "inherit_encryption": False,
            "encryption_options": {"passphrase": "abcd1234"},
        },
    )
    try:
        call("pool.dataset.lock", encrypted, job=True)
        assert call("zfs.resource.processes", encrypted) == []
    finally:
        call("pool.dataset.delete", encrypted, {"recursive": True})
