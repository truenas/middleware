"""
NFS clients' locks and open state keep files on a dataset open after its shares are gone, so unmounting it fails
with EBUSY. `nfs.release_dataset_filesystems` runs before `pool.dataset.delete`, `pool.dataset.lock` and
`pool.export` unmount. The NFS client is the TrueNAS host itself, through a loopback kernel mount: NFSv3 locks need
the kernel's NLM client. Before the call under test, each test checks that the server still holds the client's
lock, so it fails rather than passes once the scenario no longer pins the dataset.
"""

import base64
import contextlib
import os

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, poll, ssh
from middlewared.test.integration.utils.client import password, truenas_server

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
# Holds a write lock on the file until killed. It has to be a write lock: to unlock it the server opens the file
# again, which fails once its export is gone.
HOLDER_SCRIPT = """
import fcntl, os, signal, sys
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o644)
fcntl.lockf(fd, fcntl.LOCK_EX)
print("LOCK_HELD", flush=True)
signal.pause()
"""


def loopback_mount(path, vers):
    return SSH_NFS(
        truenas_server.ip,
        path,
        vers=vers,
        user="root",
        password=password(),
        ip=truenas_server.ip,
        localpath=MOUNTPOINT,
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
        poll(
            lambda: ssh(f"cat {HOLDER}.log"),
            condition=lambda out: "LOCK_HELD" in out,
            timeout=120,
            message="the lock was not taken",
        )
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


@contextlib.contextmanager
def share_disabled(share_id):
    """The share is not exported for as long as the block runs."""
    call("sharing.nfs.update", share_id, {"enabled": False})
    try:
        yield
    finally:
        call("sharing.nfs.update", share_id, {"enabled": True})


def device(ds):
    """The device of dataset `ds` as the kernel prints it in /proc/locks and in nfsd's client states."""
    dev = call("filesystem.stat", f"/mnt/{ds}")["dev"]
    return f"{os.major(dev):02x}:{os.minor(dev):02x}:"


def server_locks(ds):
    """The locks the server holds on the filesystem of `ds`. lockd takes an NFSv3 client's locks there."""
    needle = f" {device(ds)}"
    return [line for line in ssh("cat /proc/locks").splitlines() if needle in line]


def nfs4_lock_states(ds):
    """The NFSv4 lock stateids nfsd holds on the filesystem of `ds`."""
    needle = f'type: lock, superblock: "{device(ds)}'
    states = ssh("cat /proc/fs/nfsd/clients/*/states 2>/dev/null || true")
    return [line for line in states.splitlines() if needle in line]


@contextlib.contextmanager
def raises_busy():
    """The unmount fails with EZFS_BUSY. A runner without libzfs gets it as a ClientException."""
    with pytest.raises((CallError, ClientException)) as e:
        yield
    assert "busy" in str(e.value).lower(), e.value


def test_nfsv3_lock_released_before_dataset_delete(start_nfs, nfs_dataset):
    """
    An NFSv3 client holds a write lock, its share is deleted, then the client's process exits: the unlock is
    refused with a stale file handle and the server keeps the lock, and with it the file open.
    """
    with nfs_dataset("nfs_release_delete") as ds:
        with nfs_share(f"/mnt/{ds}", MAPROOT) as share_id:
            with loopback_mount(f"/mnt/{ds}", vers=3), lock_holder():
                call("sharing.nfs.delete", share_id)

        assert server_locks(ds), "the server no longer holds the lock its client could not release"
        call("pool.dataset.delete", ds, {"recursive": True})


def test_nfsv3_lock_released_before_dataset_lock(start_nfs, nfs_dataset):
    """Locking an encrypted dataset stops its share and unmounts it while an NFSv3 client holds a lock on it."""
    with nfs_dataset("nfs_release_lock", ENCRYPTED) as ds, nfs_share(f"/mnt/{ds}", MAPROOT):
        with loopback_mount(f"/mnt/{ds}", vers=3), lock_holder():
            assert server_locks(ds), "the server does not hold the client's lock"
            call("pool.dataset.lock", ds, job=True)
            assert call("pool.dataset.get_instance", ds)["locked"]


def test_nfsv3_lock_released_before_pool_export(start_nfs):
    """The same stale lock on a dataset of another pool, which is then exported and destroyed."""
    with another_pool() as other:
        ds = f"{other['name']}/nfs_release_export"
        call("pool.dataset.create", {"name": ds})
        with nfs_share(f"/mnt/{ds}", MAPROOT) as share_id:
            with loopback_mount(f"/mnt/{ds}", vers=3), lock_holder():
                call("sharing.nfs.delete", share_id)

        assert server_locks(ds), "the server no longer holds the lock its client could not release"
        call("pool.export", other["id"], {"destroy": True}, job=True)


def test_nfsv4_lock_holder_is_left_alone(start_nfs, nfs_dataset):
    """
    nfsd can only revoke an NFSv4 byte-range lock, and a revoked lock may crash the server once its filesystem is
    gone. While an NFSv4 client holds one, nothing on the dataset is released: the delete fails with EBUSY, the log
    names the client, and the lock survives. Once the client lets go, the delete goes through. The share is disabled,
    not deleted, and the refused delete leaves a disabled share alone, so enabling it again lets the client unlock
    and close as its process exits. An NFS restart would free the lock too, but would put the tests after this one in
    a grace period.
    """
    with nfs_dataset("nfs_release_v4") as ds, nfs_share(f"/mnt/{ds}", MAPROOT) as share_id:
        with no_delegations(), loopback_mount(f"/mnt/{ds}", vers=4.2):
            with lock_holder():
                assert len(nfs4_lock_states(ds)) == 1
                with share_disabled(share_id):
                    with raises_busy():
                        call("pool.dataset.delete", ds, {"recursive": True})
                    assert len(nfs4_lock_states(ds)) == 1
                    log = ssh("grep 'hold byte-range locks' /var/log/middlewared.log | tail -1")
                    assert f"{ds}: NFSv4 clients {truenas_server.ip}:" in log, log
                    assert "the NFS service restarts" in log, log

            poll(
                lambda: nfs4_lock_states(ds),
                condition=lambda states: not states,
                timeout=30,
                message="the client did not release its lock",
            )

        call("sharing.nfs.delete", share_id)
        call("pool.dataset.delete", ds, {"recursive": True})
