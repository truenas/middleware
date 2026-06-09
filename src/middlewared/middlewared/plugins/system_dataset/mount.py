"""System dataset mount and replication primitives.

Mount mechanics use the new mount API (`fsopen` / `fsconfig` / `fsmount`):

- `create_mount_one` builds a detached ZFS mount object held by an fd
  (no fork/exec, no PATH lookup -- just syscalls).
- `mount_hierarchy` mounts the parent .system dataset at a target_fd and
  nests each child mount inside the parent. Children become nested mounts
  of the parent, so they follow it when the parent is move_mount'd.

Replication uses the `TAKE_SNAPSHOTS` channel program for an atomic
recursive snapshot, then `ZFSDataset.local_replicate` to move the tree.
Cleanup uses the `DESTROY_SNAPSHOTS` zcp on both sides.
"""

import logging
import os
import uuid

import truenas_os
import truenas_pylibzfs

from .utils import SYSDATASET_PATH, dataset_mountpoint

__all__ = ["create_mount_one", "mount_hierarchy", "replicate"]

logger = logging.getLogger("system_dataset")


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
                # child_target_fd already points at SYSDATASET_PATH, so the
                # mount lands at the dataset's absolute mountpoint reduced to a
                # path relative to that root. Must be a single component: the
                # os.mkdir below has no makedirs semantics, so a nested
                # mountpoint override would fail here.
                target_path = os.path.relpath(dataset_mountpoint(ds), SYSDATASET_PATH)
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


def replicate(_from: str, _to: str) -> None:
    """Replicate the system dataset hierarchy from `_from` to `_to`.

    Source remains live and mounted throughout. Spec datasets that don't
    exist on the source aren't snapshotted -- the caller's setup_datasets
    will create them empty afterwards.

    `force=True` (zfs receive -F) lets the receive overwrite anything
    already at `{_to}/.system`. For a recursive (-R) stream the kernel
    destroys snapshots and child datasets on the destination that aren't
    in the stream, atomically with the receive -- so the caller can rely
    on the destination being a byte-for-byte copy of the source after a
    successful return, even when `{_to}/.system` was non-empty going in.

    Caveat: libzfs rejects -F up front when the destination has top-level
    snapshots or is a clone. The receive raises ZFSException(EZFS_EXISTS)
    in those cases; the caller handles the fallback.
    """
    src_root_name = f"{_from}/.system"
    dst_root_name = f"{_to}/.system"
    snap_tag = f"sysdataset-migrate-{uuid.uuid4().hex[:12]}"

    lz = truenas_pylibzfs.open_handle()
    src_root = lz.open_resource(name=src_root_name)

    take_result = truenas_pylibzfs.lzc.run_channel_program(
        pool_name=_from,
        script=truenas_pylibzfs.lzc.ChannelProgramEnum.TAKE_SNAPSHOTS,
        script_arguments=[src_root_name, snap_tag],
        readonly=False,
    )
    try:
        # lzc wraps the Lua return value under a "return" key, so the
        # outer dict is always truthy. The Lua program's `failed` table
        # is empty on full success -- only non-empty inner value means
        # at least one descendant failed to snapshot.
        failed_snaps = take_result.get("return") or {}
        if failed_snaps:
            raise RuntimeError(
                f"TAKE_SNAPSHOTS failed on {src_root_name}@{snap_tag}: {failed_snaps!r}",
            )
        src_root.local_replicate(tosnap=snap_tag, dest=dst_root_name, force=True)
    finally:
        # Best-effort cleanup: log failures rather than raise so we don't
        # mask any error from the replicate above.
        for pool, root in ((_from, src_root_name), (_to, dst_root_name)):
            try:
                truenas_pylibzfs.lzc.run_channel_program(
                    pool_name=pool,
                    script=truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_SNAPSHOTS,
                    script_arguments_dict={
                        "target": root,
                        "recursive": True,
                        "pattern": snap_tag,
                        "defer": False,
                    },
                    readonly=False,
                )
            except Exception:
                logger.warning(
                    "%s@%s: failed to destroy migration snapshot",
                    root,
                    snap_tag,
                    exc_info=True,
                )
