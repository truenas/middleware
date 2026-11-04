from collections.abc import Iterable, Iterator
from contextlib import suppress
import errno
import logging
import os
import re
import time
from typing import Any

import truenas_os

from middlewared.api.current import ZFSResourceQuery
from middlewared.plugins.zfs.resource_processes_utils import read_mountinfo
from middlewared.service import ServiceContext
from middlewared.service_exception import CallError

from .status import NFS4_CLIENTS_DIR

logger = logging.getLogger(__name__)

NFSD_UNLOCK_FILESYSTEM = "/proc/fs/nfsd/unlock_filesystem"
RPC_CACHE_DIR = "/proc/net/rpc"
# the export caches whose entries hold a reference to the mount they export
EXPORT_CACHES = ("nfsd.fh", "nfsd.export")
# A lock stateid in /proc/fs/nfsd/clients/*/states, see nfs4_show_lock(). The superblock is only shown while the
# stateid has its file open.
NFS4_LOCK_STATE = re.compile(
    r'- 0x[0-9a-f]{32}: \{ type: lock(, superblock: "(?P<major>[0-9a-f]+):(?P<minor>[0-9a-f]+):\d+")?'
)


class NFS4LockRevoked(CallError):
    """An NFSv4 lock stateid was revoked by the release; the filesystem must not be destroyed now."""


def alive_in_kernel(ds: str, objsetid: int) -> bool:
    # The objset kstat exists from the mount until the filesystem is freed, also while a lazily unmounted
    # filesystem is kept alive. Look it up by objsetid: its dataset_name goes stale when the dataset is renamed.
    return os.path.exists(f"/proc/spl/kstat/zfs/{ds.split('/', 1)[0]}/objset-0x{objsetid:x}")


def mounted_snapshots(name: str, tree: Iterable[str]) -> Iterator[tuple[str, str, int]]:
    """Yield (dataset, mountpoint, st_dev) for every mounted snapshot of a dataset in `tree`."""
    for mnt in read_mountinfo(name):
        source, mountpoint = mnt["mount_source"], mnt["mountpoint"]
        if (
            mnt["fs_type"] == "zfs"
            and source
            and mountpoint
            and "@" in source
            and (ds := source.split("@", 1)[0]) in tree
        ):
            yield ds, mountpoint, mnt["device_id"]["dev_t"]


def devices(paths: Iterable[str]) -> set[int]:
    """Return the st_dev of every one of `paths` that exists."""
    devs = set()
    for path in paths:
        with suppress(OSError):
            devs.add(os.stat(path).st_dev)
    return devs


def zfs_mount_fd(ds: str, readonly: bool) -> int:
    """
    Return an O_PATH fd for a mount of the ZFS filesystem `ds` that is attached nowhere. ZFS gives it the live
    superblock of the filesystem, also when the filesystem is mounted elsewhere or was lazily unmounted.
    """
    fsfd = truenas_os.fsopen(fs_name="zfs", flags=truenas_os.FSOPEN_CLOEXEC)
    try:
        truenas_os.fsconfig(fs_fd=fsfd, cmd=truenas_os.FSCONFIG_SET_STRING, key="source", value=ds)
        if readonly:
            truenas_os.fsconfig(fs_fd=fsfd, cmd=truenas_os.FSCONFIG_SET_FLAG, key="ro")
        truenas_os.fsconfig(fs_fd=fsfd, cmd=truenas_os.FSCONFIG_CMD_CREATE)
        return truenas_os.fsmount(fs_fd=fsfd, flags=truenas_os.FSMOUNT_CLOEXEC)
    finally:
        os.close(fsfd)


def open_filesystem(ds: str, readonly: bool) -> int:
    try:
        return zfs_mount_fd(ds, readonly)
    except OSError as e:
        if e.errno != errno.EBUSY:
            raise
        # the live superblock's read-only flag differs from the property
        return zfs_mount_fd(ds, not readonly)


def export_cache_mentions(mountpoints: set[str], devs: set[int]) -> bool:
    """
    Whether an export cache entry, expired or not, names a path under one of `mountpoints` or on one of the
    filesystems `devs`. A lazily unmounted filesystem is only found by its mountpoint: its path leads elsewhere.
    """
    paths: set[str] = set()
    for cache in EXPORT_CACHES:
        with suppress(OSError):
            with open(f"{RPC_CACHE_DIR}/{cache}/content", encoding="utf-8", errors="surrogateescape") as f:
                for line in f:
                    paths.update(
                        re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), field)
                        for field in line.split()
                        if field.startswith("/")
                    )
    if any(path == mp or path.startswith(f"{mp}/") for path in paths for mp in mountpoints):
        return True
    return bool(devices(paths) & devs)


def recent_flush() -> bool:
    """Whether an export cache was flushed within the last 35 seconds, as it is when a share was just removed."""
    for cache in EXPORT_CACHES:
        with suppress(OSError, ValueError):
            with open(f"{RPC_CACHE_DIR}/{cache}/flush") as f:
                if int(f.read()) > time.time() - 35:
                    return True
    return False


def flush_export_caches() -> None:
    """
    Flush the export caches. Their entries hold the mounts they export, also the negative entries nfsd makes for a
    mountpoint under an export that a client looked at, and the cache cleaner only drops them when they expire, up
    to 30 minutes later. Removing a share flushes them, but a flush written in the same second as the one before only
    moves the cache's flush time ahead and drops nothing (write_flush() in net/sunrpc/cache.c). The file shows the
    wall-clock second of the last flush; a write takes effect once that second has passed, and shows a later second
    otherwise. A flush is also due within half a minute of the last one: that is when a share was just removed. And
    a flush drops only the entries made before it, so one is due each time the caches name the tree.
    """
    for cache in EXPORT_CACHES:
        path = f"{RPC_CACHE_DIR}/{cache}/flush"
        for _ in range(3):
            try:
                with open(path) as f:
                    flush_time = int(f.read())
            except (OSError, ValueError):
                break
            # the second shown is converted from boot time and can be one less than the wall clock's
            time.sleep(max(0.0, flush_time + 2 - time.time()))
            try:
                with open(path, "w") as f:
                    f.write("1\n")
                with open(path) as f:
                    flush_time = int(f.read())
            except (OSError, ValueError):
                break
            if flush_time <= int(time.time()):
                break


def unlock_filesystem(fd: int) -> None:
    # unlock_filesystem resolves the path and releases the state of its superblock. The trailing slash makes the
    # lookup follow the /proc/self/fd magic link, so no path to the filesystem is needed.
    ufd = os.open(NFSD_UNLOCK_FILESYSTEM, os.O_WRONLY)
    try:
        os.write(ufd, f"/proc/self/fd/{fd}/\n".encode())
    except OSError as e:
        # EINVAL: nfsd is not running. Its NFSv4 state is gone with it, and lockd has released its NLM locks before
        # the error (which also hides a failure of lockd to do so).
        if e.errno != errno.EINVAL:
            raise
    finally:
        os.close(ufd)


def nfs4_lock_holders() -> dict[int, set[str]] | None:
    """
    Return {st_dev: {client address}} for the filesystems on which NFSv4 clients hold lock stateids, or None when a
    revoked lock stateid exists: it no longer shows its filesystem, and it is what must never be left behind.
    """
    holders: dict[int, set[str]] = {}
    try:
        clients = os.listdir(NFS4_CLIENTS_DIR)
    except FileNotFoundError:
        return holders
    for client in clients:
        try:
            with open(f"{NFS4_CLIENTS_DIR}/{client}/info", encoding="utf-8", errors="surrogateescape") as f:
                info = f.read()
            with open(f"{NFS4_CLIENTS_DIR}/{client}/states", encoding="utf-8", errors="surrogateescape") as f:
                states = f.read()
        except OSError as e:
            if e.errno in (errno.ENOENT, errno.ENXIO):
                # the client went away meanwhile
                continue
            logger.warning("NFSv4 client %s: cannot read its state: %s", client, e)
            return None
        address = re.search(r'^address: "(.*)"$', info, re.M)
        who = address[1] if address else client
        for line in states.splitlines():
            if not (m := NFS4_LOCK_STATE.match(line)):
                continue
            if m["major"] is None:
                if "admin-revoked" in line:
                    logger.warning("NFSv4 client %s holds a revoked lock stateid", who)
                    return None
                # closed, and still referenced by a request: it holds no lock
                continue
            holders.setdefault(os.makedev(int(m["major"], 16), int(m["minor"], 16)), set()).add(who)
    return holders


def release_filesystems(name: str, rows: list[dict[str, Any]], exported: set[int]) -> list[str]:
    """
    Make nfsd release every file it keeps open on the filesystems of `rows`, the dataset (or pool) `name` and its
    children, except on those whose st_dev is in `exported`. Return the names of the filesystems released.
    """
    # Not only while nfsd runs: lockd also serves this host's own NFS mounts and keeps the NLM locks of NFS clients
    # after nfsd is stopped, for as long as such a mount exists.
    if not os.path.exists(NFSD_UNLOCK_FILESYSTEM):
        return []

    rows = [row for row in rows if row["type"] == "FILESYSTEM"]
    tree = {
        row["name"]: (int(row["properties"]["objsetid"]["raw"]), row["properties"]["readonly"]["raw"] == "on")
        for row in rows
    }
    mountpoints = {
        row["properties"]["mountpoint"]["raw"] for row in rows if row["properties"]["mountpoint"]["raw"].startswith("/")
    }
    # neither mounted nor kept alive: nfsd cannot hold anything on it
    filesystems = {}
    for ds, (objsetid, readonly) in tree.items():
        if not alive_in_kernel(ds, objsetid):
            continue
        try:
            fd = open_filesystem(ds, readonly)
        except OSError as e:
            logger.warning("%s: failed to reach the filesystem to release NFS locks: %s", ds, e)
            continue
        try:
            filesystems[ds] = (readonly, os.fstat(fd).st_dev)
        finally:
            os.close(fd)
    try:
        snapshots = list(mounted_snapshots(name, tree))
    except CallError as e:
        logger.warning("%s: %s; not releasing NFS locks on its snapshots", name, e)
        snapshots = []
    if not filesystems and not snapshots:
        return []

    # nfsd releases an NFSv4 lock by revoking its stateid, and the revoked stateid keeps pointing at the inode, which
    # the laundromat can still look at after the filesystem is gone (nfs4_lockowner_has_blockers()). Leave the whole
    # tree alone then: unmounting it fails as before, and no client loses its locks.
    locks = nfs4_lock_holders()
    if locks is None:
        logger.warning("%s: not releasing NFS locks until that client frees it or the NFS service restarts", name)
        return []
    on_tree = [(ds, dev) for ds, (_, dev) in filesystems.items()] + [(path, dev) for _, path, dev in snapshots]
    held = [(what, locks[dev]) for what, dev in on_tree if dev in locks]
    for what, clients in held:
        logger.warning(
            "%s: NFSv4 clients %s hold byte-range locks, not releasing NFS locks until they let go or the NFS "
            "service restarts",
            what,
            ", ".join(sorted(clients)),
        )
    if held:
        return []

    devs = {dev for _, dev in filesystems.values()} | {dev for _, _, dev in snapshots}
    if recent_flush() or export_cache_mentions(mountpoints, devs):
        flush_export_caches()

    released: list[str] = []
    kept = set()
    for ds, (readonly, dev) in filesystems.items():
        if dev in exported:
            # A share still exports it: its mountpoint is outside the one whose shares were removed. Its clients
            # keep their locks, and unmounting it fails as before.
            kept.add(ds)
            logger.info("%s: still exported over NFS, not releasing NFS locks", ds)
            continue
        try:
            fd = open_filesystem(ds, readonly)
        except OSError as e:
            logger.warning("%s: failed to reach the filesystem to release NFS locks: %s", ds, e)
            continue
        try:
            unlock_filesystem(fd)
        except OSError as e:
            logger.warning("%s: failed to release NFS locks: %s", ds, e)
        else:
            released.append(ds)
        finally:
            os.close(fd)

    # A snapshot an NFS client reached through .zfs/snapshot is automounted, and a lock or open file in it keeps
    # the snapshot, and so the destroy of its dataset, busy.
    for ds, path, dev in snapshots:
        if ds in kept or dev in exported:
            continue
        try:
            fd = os.open(path, os.O_PATH | os.O_NOFOLLOW)
        except OSError:
            continue
        try:
            # an expired automount leaves a plain directory of the parent filesystem behind
            if os.fstat(fd).st_dev == dev:
                unlock_filesystem(fd)
                released.append(path)
        except OSError as e:
            logger.warning("%s: failed to release NFS locks: %s", path, e)
        finally:
            os.close(fd)

    # A LOCK that passed its export check before the share was removed can be granted after the check above and
    # revoked here. Then stop: destroying the filesystem would leave the revoked stateid pointing at a freed inode.
    if released and nfs4_lock_holders() is None:
        raise NFS4LockRevoked(
            f"{name}: an NFSv4 lock was revoked while releasing NFS locks; retry once its client frees it, or "
            "restart the NFS service",
            errno.EBUSY,
        )
    logger.debug("%s: released NFS locks on %s", name, ", ".join(released))
    return released


def release_dataset_filesystems(context: ServiceContext, name: str) -> list[str]:
    """
    Make nfsd release every file it keeps open on the filesystems of dataset (or pool) `name` and its children, so
    that they can be unmounted. Only for a tree whose shares are gone or stopped: its NFS clients lose their locks. A
    filesystem that a share still exports, and the whole tree while NFSv4 clients hold byte-range locks on it, are
    left alone. Returns the filesystems released.
    """
    try:
        rows = context.call_sync2(
            context.s.zfs.resource.list_impl,
            ZFSResourceQuery(paths=[name], properties=["mountpoint", "objsetid", "readonly"], get_children=True),
        )
        shares = context.call_sync2(context.s.sharing.nfs.query, [["enabled", "=", True]])
        # a locked share's path is a directory of the parent filesystem: it must not count as the parent's export
        exported = devices(share.path for share in shares if not share.locked)
        return release_filesystems(name, rows, exported)
    except NFS4LockRevoked:
        raise
    except Exception:
        # the unmount that follows then fails as it would have without the release
        logger.warning("%s: failed to release NFS locks", name, exc_info=True)
        return []
