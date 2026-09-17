import pytest
from auto_config import pool_name

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh


@pytest.mark.parametrize(
    "method,args",
    [
        ("checksum_choices", ()),
        ("compression_choices", ()),
        ("recordsize_choices", (pool_name,)),
        ("recommended_zvol_blocksize", (pool_name,)),
    ],
)
def test_zfs_resource_info_matches_pool_dataset(method, args):
    """The relocated methods and the `pool.dataset` shims over them answer identically."""
    assert call(f"zfs.resource.{method}", *args) == call(f"pool.dataset.{method}", *args)


def test_zfs_resource_processes_idle_dataset():
    """A dataset nothing is holding open reports no processes, through either namespace."""
    with dataset("test_processes_idle") as ds:
        assert call("zfs.resource.processes", ds) == []
        assert call("pool.dataset.processes", ds) == []


def test_zfs_resource_processes_volume():
    """A volume is scanned as a block device, not as a mountpoint under /mnt."""
    with dataset("test_processes_zvol", {"type": "VOLUME", "volsize": 100 * 1024 * 1024}) as zvol:
        assert call("zfs.resource.processes", zvol) == []


def holder(path):
    """Start a background process holding `path` open and return its pid."""
    pid = ssh(f"( tail -f {path} >/dev/null 2>&1 & echo $! )").strip()
    return int(pid)


def test_zfs_resource_processes_unmounted_ignores_parent():
    """An unmounted child does not inherit the processes of whatever is mounted above it."""
    with dataset("test_processes_parent") as parent:
        with dataset("test_processes_parent/child") as child:
            ssh(f"touch /mnt/{parent}/holdme")
            pid = holder(f"/mnt/{parent}/holdme")
            try:
                ssh(f"zfs unmount {child}")
                try:
                    assert call("zfs.resource.processes", child) == []
                    assert pid in [p["pid"] for p in call("zfs.resource.processes", parent)]
                finally:
                    ssh(f"zfs mount {child}")
            finally:
                ssh(f"kill {pid}")


def test_zfs_resource_processes_includes_descendants():
    """A process holding a child dataset open shows up on the parent."""
    with dataset("test_processes_tree") as parent:
        with dataset("test_processes_tree/child") as child:
            ssh(f"touch /mnt/{child}/holdme")
            pid = holder(f"/mnt/{child}/holdme")
            try:
                assert pid in [p["pid"] for p in call("zfs.resource.processes", parent)]
            finally:
                ssh(f"kill {pid}")
