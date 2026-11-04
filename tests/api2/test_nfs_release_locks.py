"""
NFS clients' locks and open state keep files on a dataset open after its shares are gone, so unmounting it fails
with EBUSY. `nfs.release_dataset_filesystems` runs before `pool.dataset.delete`, `pool.dataset.lock` and
`pool.export` unmount. The NFS client here is the TrueNAS host itself, through a loopback mount, as in the other NFS
tests. Each NFSv3 test first runs its operation with the release mocked away, to show the EBUSY it fixes.
"""

import base64
import contextlib
import time

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.nfs import nfs_server
from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.utils import call, mock, ssh
from middlewared.test.integration.utils.client import truenas_server

from auto_config import password, user
from protocols import SSH_NFS, nfs_share
from truenas_api_client import ClientException

MOUNTPOINT = "/mnt/testnfs"
LOCKED_FILE = f"{MOUNTPOINT}/locked.dat"
# the client is root on the host, and must stay root on the export to write
MAPROOT = {"maproot_user": "root", "maproot_group": "root"}
ENCRYPTED = {
    "encryption": True,
    "inherit_encryption": False,
    "encryption_options": {"generate_key": False, "passphrase": "12345678"},
}
HOLDER = "/tmp/nfs_lock_holder.py"
# holds a write lock on the file until killed
HOLDER_SCRIPT = """
import fcntl, os, signal, sys
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o644)
fcntl.lockf(fd, fcntl.LOCK_EX)
print("LOCK_HELD", flush=True)
signal.pause()
"""


@pytest.fixture(scope="module", autouse=True)
def nfs():
    with nfs_server():
        yield


def loopback_mount(path, vers):
    return SSH_NFS(
        truenas_server.ip, path, vers=vers, user=user, password=password, ip=truenas_server.ip, localpath=MOUNTPOINT
    )


@contextlib.contextmanager
def lock_holder(path=LOCKED_FILE):
    """
    A process on the host that holds a write lock on `path` of the NFS mount for as long as the block runs. The
    first lock after an NFS start waits for the grace period to end.
    """
    script = base64.b64encode(HOLDER_SCRIPT.encode()).decode()
    ssh(f"echo {script} | base64 -d > {HOLDER}")
    pid = ssh(f"nohup python3 {HOLDER} {path} > {HOLDER}.log 2>&1 & echo $!").strip()
    try:
        for _ in range(120):
            if "LOCK_HELD" in ssh(f"cat {HOLDER}.log"):
                break
            time.sleep(1)
        else:
            raise RuntimeError(f"the lock was not taken: {ssh(f'cat {HOLDER}.log')}")
        yield
    finally:
        ssh(f"kill {pid}; for i in $(seq 100); do kill -0 {pid} 2>/dev/null || break; sleep 0.1; done", check=False)
        ssh(f"rm -f {HOLDER} {HOLDER}.log", check=False)


@contextlib.contextmanager
def no_delegations():
    """Without a delegation an NFSv4 client takes its locks on the server; with one it keeps them to itself."""
    ssh("sysctl -w fs.leases-enable=0")
    try:
        yield
    finally:
        ssh("sysctl -w fs.leases-enable=1")


def nfs4_lock_states():
    return ssh("cat /proc/fs/nfsd/clients/*/states 2>/dev/null || true").count("type: lock")


@contextlib.contextmanager
def raises_busy():
    """The unmount fails with EZFS_BUSY. A runner without libzfs gets it as a ClientException."""
    with pytest.raises((CallError, ClientException)) as e:
        yield
    assert "busy" in str(e.value).lower(), e.value


def test_nfsv3_lock_released_before_dataset_delete():
    """
    An NFSv3 client holds a write lock, its share is deleted, then the client's process exits: the unlock is
    refused with a stale file handle and lockd keeps the file open, so the dataset cannot be unmounted.
    """
    with dataset("nfs_release_delete") as ds, nfs_share(f"/mnt/{ds}", MAPROOT) as share_id:
        with loopback_mount(f"/mnt/{ds}", vers=3), lock_holder():
            call("sharing.nfs.delete", share_id)

        with mock("nfs.release_dataset_filesystems", return_value=[]):
            with raises_busy():
                call("pool.dataset.delete", ds, {"recursive": True})

        call("pool.dataset.delete", ds, {"recursive": True})


def test_nfsv3_lock_released_before_dataset_lock():
    """Locking an encrypted dataset stops its share and unmounts it while an NFSv3 client holds a lock."""
    with dataset("nfs_release_lock", ENCRYPTED) as ds, nfs_share(f"/mnt/{ds}", MAPROOT):
        with loopback_mount(f"/mnt/{ds}", vers=3), lock_holder():
            with mock("nfs.release_dataset_filesystems", return_value=[]):
                with raises_busy():
                    call("pool.dataset.lock", ds, job=True)

            call("pool.dataset.lock", ds, job=True)
            assert call("pool.dataset.get_instance", ds)["locked"]


def test_nfsv3_lock_released_before_pool_export():
    """The same stale lock on a dataset of another pool, which is then exported and destroyed."""
    with another_pool() as pool, dataset("nfs_release_export", pool=pool["name"]) as ds:
        with nfs_share(f"/mnt/{ds}", MAPROOT) as share_id:
            with loopback_mount(f"/mnt/{ds}", vers=3), lock_holder():
                call("sharing.nfs.delete", share_id)

            with mock("nfs.release_dataset_filesystems", return_value=[]):
                with raises_busy():
                    call("pool.export", pool["id"], {"destroy": True}, job=True)

            call("pool.export", pool["id"], {"destroy": True}, job=True)


def test_nfsv4_lock_holder_is_left_alone():
    """
    nfsd can only revoke an NFSv4 byte-range lock, and a revoked lock may crash the server once its filesystem is
    gone. While an NFSv4 client holds one, nothing on the dataset is released: the delete fails with EBUSY, the log
    names the client, and the lock survives. The state outlives the client; restarting NFS clears it.
    """
    with dataset("nfs_release_v4") as ds, nfs_share(f"/mnt/{ds}", MAPROOT) as share_id:
        with no_delegations(), loopback_mount(f"/mnt/{ds}", vers=4.2), lock_holder():
            assert nfs4_lock_states() == 1
            call("sharing.nfs.delete", share_id)

            with raises_busy():
                call("pool.dataset.delete", ds, {"recursive": True})
            assert nfs4_lock_states() == 1
            log = ssh("grep 'hold byte-range locks' /var/log/middlewared.log | tail -1")
            assert f"{ds}: NFSv4 clients {truenas_server.ip}:" in log, log
            assert "the NFS service restarts" in log, log

        assert nfs4_lock_states() == 1
        call("service.control", "RESTART", "nfs", job=True)
        call("pool.dataset.delete", ds, {"recursive": True})
