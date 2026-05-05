"""System dataset mount and replication primitives.

Mount mechanics use the new mount API (`fsopen` / `fsconfig` / `fsmount`)
plus `move_mount(MOVE_MOUNT_BENEATH)` for atomic swaps:

- `create_mount_one` builds a detached ZFS mount object held by an fd
  (no fork/exec, no PATH lookup — just syscalls).
- `mount_hierarchy` mounts the parent .system dataset at a target_fd and
  nests each child mount inside the parent. Children become nested mounts
  of the parent, so they follow it when the parent is move_mount'd.
- `swap_under` slips a staged mount tree underneath whatever is currently
  at the destination via MOVE_MOUNT_BENEATH, then unmounts the old top
  layer to expose the new tree. The destination is never bare during the
  swap — the only race-free way to replace a live mount.

Replication uses libzfs_core send/receive piped between threads:

- `replicate` is the entry point. It takes one atomic lzc_snapshot covering
  the entire source hierarchy (point-in-time consistent), then for each
  source dataset that exists, streams its snapshot to the matching
  destination dataset. lzc_send is non-recursive (recursion is a libzfs
  userspace construct), so we iterate parent-first and rely on
  lzc.receive to create the destination dataset from each stream.
- `_send_recv_one` runs the actual transfer: a sender thread calls
  lzc.send writing into a pipe; the calling thread runs lzc.receive
  reading from the other end. The pipe is enlarged to 1 MiB before any
  I/O (kernel bug 212295 deadlocks F_SETPIPE_SZ on a pipe with data, but
  we own the lifecycle so the resize is safe). Each fd has exactly one
  closer — sender owns the write end, the calling thread owns the read end.
"""

from contextlib import suppress
import fcntl
import os
import threading
import uuid

import truenas_os
from truenas_os_pyutils.mount import umount
import truenas_pylibzfs

from .hierarchy import get_system_dataset_spec

__all__ = ["create_mount_one", "mount_hierarchy", "swap_under", "replicate"]


def create_mount_one(dataset_spec: dict) -> int:
    """Build a detached ZFS mount via the new mount API; return the mount fd."""
    fsfd = truenas_os.fsopen(fs_name="zfs", flags=truenas_os.FSOPEN_CLOEXEC)
    try:
        truenas_os.fsconfig(
            fs_fd=fsfd,
            cmd=truenas_os.FSCONFIG_SET_STRING,
            key="source",
            value=dataset_spec["name"],
        )
        truenas_os.fsconfig(fs_fd=fsfd, cmd=truenas_os.FSCONFIG_CMD_CREATE)
        return truenas_os.fsmount(fs_fd=fsfd, flags=truenas_os.FSMOUNT_CLOEXEC)
    finally:
        os.close(fsfd)


def mount_hierarchy(*, target_fd: int, datasets: list[dict]) -> None:
    """Mount the system dataset hierarchy under `target_fd`.

    The first spec entry is the parent (e.g. <pool>/.system); its mount
    lands at target_fd. Subsequent entries are nested mounts inside the
    parent's mount root, so the whole tree moves as a unit when the parent
    is later move_mount'd.
    """
    child_target_fd = None
    mntfd = None
    try:
        for idx, ds in enumerate(datasets):
            mntfd = create_mount_one(ds)
            if idx == 0:
                truenas_os.move_mount(
                    from_dirfd=mntfd,
                    from_path="",
                    to_dirfd=target_fd,
                    to_path="",
                    flags=(truenas_os.MOVE_MOUNT_F_EMPTY_PATH | truenas_os.MOVE_MOUNT_T_EMPTY_PATH),
                )
                # target_fd was opened before the mount landed, so it
                # references the underlying dir entry. Re-open by path so
                # subsequent lookups traverse INTO the new mount.
                child_target_fd = os.open(
                    os.readlink(f"/proc/self/fd/{target_fd}"),
                    os.O_DIRECTORY,
                )
            else:
                target_path = os.path.basename(ds["name"])
                chown = dict(ds["chown_config"])
                mode = chown.pop("mode")
                try:
                    os.mkdir(target_path, dir_fd=child_target_fd, mode=mode)
                except FileExistsError:
                    os.chmod(target_path, dir_fd=child_target_fd, mode=mode)
                os.chown(target_path, dir_fd=child_target_fd, **chown)
                truenas_os.move_mount(
                    from_dirfd=mntfd,
                    from_path="",
                    to_dirfd=child_target_fd,
                    to_path=target_path,
                    flags=truenas_os.MOVE_MOUNT_F_EMPTY_PATH,
                )
            os.close(mntfd)
            mntfd = None
    finally:
        if child_target_fd is not None:
            os.close(child_target_fd)
        if mntfd is not None:
            os.close(mntfd)


def swap_under(staging_path: str, dest_path: str) -> None:
    """Atomically replace the mount tree at `dest_path` with the one at
    `staging_path` via MOVE_MOUNT_BENEATH.

    Sequence:
    - open_tree on the staging mount (no clone, no AT_RECURSIVE — we move
      the actual mount; nested children follow the parent)
    - move_mount with MOVE_MOUNT_BENEATH layers the new tree under
      whatever is currently mounted at dest_path
    - umount dest_path recursively, removing the old top layer and
      exposing the staged tree underneath

    `dest_path` is never bare: between move_mount and the umount it has
    both the old and new layers; only the umount removes the old. Source
    mount must have MS_PRIVATE propagation (set up by the parent /var
    mount_setattr call at boot) or move_mount returns EINVAL.
    """
    tree_fd = truenas_os.open_tree(
        path=staging_path,
        flags=truenas_os.OPEN_TREE_CLOEXEC,
    )
    try:
        truenas_os.move_mount(
            from_dirfd=tree_fd,
            from_path="",
            to_path=dest_path,
            flags=(truenas_os.MOVE_MOUNT_F_EMPTY_PATH | truenas_os.MOVE_MOUNT_BENEATH),
        )
    finally:
        os.close(tree_fd)

    umount(dest_path, force=True, recursive=True)


def replicate(_from: str, _to: str, uid: str) -> None:
    """Replicate the system dataset hierarchy from `_from` to `_to`.

    Source remains live and mounted throughout. A single atomic
    lzc_snapshot ioctl covers every source dataset point-in-time; each
    snapshot is then streamed via lzc.send | lzc.receive to its
    destination counterpart. Datasets in the spec that don't exist on the
    source (e.g. one added in a later release) are skipped — the caller's
    setup_datasets will create them empty afterwards.

    Caller is responsible for clearing any prior `{_to}/.system` so
    receive lands on a clean slate (no force flag needed).
    """
    spec = get_system_dataset_spec(_to, uid)
    prefix_to, prefix_from = f"{_to}/", f"{_from}/"

    lz = truenas_pylibzfs.open_handle()
    pairs: list[tuple[str, str]] = []
    for ds in spec:
        dest_name = ds["name"]
        src_name = dest_name.replace(prefix_to, prefix_from, 1)
        try:
            lz.open_resource(name=src_name)
        except truenas_pylibzfs.ZFSException as e:
            if e.code == truenas_pylibzfs.ZFSError.EZFS_NOENT:
                continue
            raise
        pairs.append((src_name, dest_name))

    if not pairs:
        return

    snap_tag = f"sysdataset-migrate-{uuid.uuid4().hex[:12]}"
    src_snaps = [f"{src}@{snap_tag}" for src, _ in pairs]
    dst_snaps = [f"{dest}@{snap_tag}" for _, dest in pairs]

    truenas_pylibzfs.lzc.create_snapshots(snapshot_names=src_snaps)
    try:
        for src, dest in pairs:
            _send_recv_one(f"{src}@{snap_tag}", f"{dest}@{snap_tag}")
    finally:
        with suppress(Exception):
            truenas_pylibzfs.lzc.destroy_snapshots(snapshot_names=src_snaps)
        with suppress(Exception):
            truenas_pylibzfs.lzc.destroy_snapshots(snapshot_names=dst_snaps)


def _send_recv_one(src_snap: str, dest_snap: str) -> None:
    """Stream one ZFS snapshot from `src_snap` to `dest_snap` via os.pipe.

    Sender thread runs lzc.send writing into the pipe write end; calling
    thread runs lzc.receive reading from the pipe read end. Both ioctls
    release the GIL so the threads run truly concurrent.

    Pipe is enlarged to 1 MiB before any I/O — bigger buffer means fewer
    block/wake cycles between the threads. F_SETPIPE_SZ on a pipe that
    already has data deadlocks (kernel bug 212295), so we resize while
    the pipe is empty. Best-effort: if the kernel caps below our request
    we keep the smaller value.

    fd ownership: sender's finally closes the write end (that's what
    delivers EOF to receive); the calling thread closes the read end.
    No shared closes — avoids the fd-reuse race in multi-threaded code.
    """
    r, w = os.pipe()
    with suppress(OSError):
        fcntl.fcntl(w, fcntl.F_SETPIPE_SZ, 1024 * 1024)

    send_err: list[BaseException] = []

    def _send() -> None:
        try:
            truenas_pylibzfs.lzc.send(snapname=src_snap, fd=w)
        except BaseException as e:
            send_err.append(e)
        finally:
            with suppress(OSError):
                os.close(w)

    sender = threading.Thread(target=_send, name=f"sysds-send:{src_snap}")
    sender.start()
    try:
        truenas_pylibzfs.lzc.receive(snapname=dest_snap, fd=r)
    finally:
        with suppress(OSError):
            os.close(r)
        sender.join()
    if send_err:
        raise send_err[0]
