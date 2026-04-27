import contextlib
import dataclasses
import enum
import errno
import os
import threading
import time
import types
from collections.abc import Callable

import truenas_os

from middlewared.service_exception import CallError
from truenas_os_pyutils.mount import statmount as _statmount
from middlewared.plugins.zfs.object_count_impl import estimate_object_count_impl
from middlewared.utils.filesystem.acl import (
    ACL_UNDEFINED_ID,
    FS_ACL_Type,
    nfs4acl_dict_to_obj,
    nfs4acl_obj_to_dict,
    posixacl_dict_to_obj,
    posixacl_obj_to_dict,
)


class AclToolAction(enum.StrEnum):
    CHOWN = 'chown'  # Only chown files
    CLONE = 'clone'  # Use simplified imheritance logic
    INHERIT = 'inherit'  # NFS41-style inheritance
    STRIP = 'strip'  # Strip ACL from specified path


@dataclasses.dataclass(slots=True)
class ATBaseOptions:
    traverse: bool = False


@dataclasses.dataclass(slots=True)
class ATChownOptions(ATBaseOptions):
    pass


@dataclasses.dataclass(slots=True)
class ATPermOptions(ATBaseOptions):
    target_mode: int | None = None


@dataclasses.dataclass(slots=True)
class ATAclOptions(ATBaseOptions):
    target_acl: object = None


@dataclasses.dataclass(slots=True)
class _NFS4InheritedAcls:
    d1_file: object  # NFS4ACL for depth-1 files
    d1_dir: object   # NFS4ACL for depth-1 directories
    d2_file: object  # NFS4ACL for depth-2+ files
    d2_dir: object   # NFS4ACL for depth-2+ directories

    @classmethod
    def from_root(cls, root_acl):
        d1_dir = root_acl.generate_inherited_acl(is_dir=True)
        return cls(
            d1_file=root_acl.generate_inherited_acl(is_dir=False),
            d1_dir=d1_dir,
            d2_file=d1_dir.generate_inherited_acl(is_dir=False),
            d2_dir=d1_dir.generate_inherited_acl(is_dir=True),
        )

    def pick(self, depth, is_dir):
        if depth == 1:
            return self.d1_dir if is_dir else self.d1_file
        return self.d2_dir if is_dir else self.d2_file


def _get_mount_info(fd: int):
    sm = _statmount(fd=fd, as_dict=False)
    abs_path = os.readlink(f'/proc/self/fd/{fd}')
    rel = os.path.relpath(abs_path, sm.mnt_point)
    return sm.mnt_point, sm.sb_source, (None if rel == '.' else rel), sm.mnt_id


_PERM_LOCK_POLL_INTERVAL = 1.0  # seconds between on_wait callbacks while blocked
_DEFAULT_MAX_CONCURRENT_PERM_OPS = 10


class PermLockRegistry:
    """
    Global registry of active permission operation locks for filesystem ACL/chown/setperm jobs.

    Tracks (dataset, is_traverse) pairs for all in-flight recursive operations and enforces
    hierarchical conflict detection.

    Terms used below:
      exact(X)    -- a non-traverse lock on dataset X; the operation recurses within X but
                     does not cross into child dataset mount points.
      traverse(X) -- a traverse lock on dataset X; the operation recurses into X and all
                     ZFS datasets mounted beneath X in the filesystem tree.
      X, child, parent, sibling -- ZFS dataset name relationships in the mount hierarchy.
                     "child of X" means a dataset whose name starts with X + '/'.
                     "parent of X" means a dataset whose name is a prefix of X + '/'.
                     "sibling" means a dataset that shares the same parent as X but is
                     not X itself (e.g. tank/a and tank/b are siblings).

    Conflict matrix (Y = conflict/blocks, N = allowed concurrently):

      Incoming lock type
      |                   Active: exact(X)   Active: traverse(X)
      +------------------+------------------+--------------------
      exact(X)           |  Y  (same ds)    |  Y  (same ds)
      exact(child of X)  |  N               |  Y  (descendant)
      exact(sibling)     |  N               |  N  (unrelated)
      traverse(X)        |  Y  (same ds)    |  Y  (same ds)
      traverse(child)    |  N               |  Y  (descendant)
      traverse(parent)   |  Y  (ancestor)   |  Y  (ancestor)
      traverse(sibling)  |  N               |  N  (unrelated)

    The optional `on_wait` callback passed to `lock()` is called roughly every second
    while the caller is blocked, allowing job progress messages to be updated.
    """

    def __init__(self, max_concurrent: int = _DEFAULT_MAX_CONCURRENT_PERM_OPS):
        self._cond = threading.Condition(threading.Lock())
        # dataset -> is_traverse for all currently held locks
        self._active: dict[str, bool] = {}
        self._max_concurrent = max_concurrent

    def _conflicts(self, dataset: str, is_traverse: bool) -> bool:
        for active_ds, active_trav in self._active.items():
            if active_ds == dataset:
                return True
            # Traverse ops conflict with ancestor/descendant datasets
            if is_traverse or active_trav:
                if dataset.startswith(active_ds + '/') or active_ds.startswith(dataset + '/'):
                    return True
        return False

    @contextlib.contextmanager
    def lock(self, dataset: str, is_traverse: bool, on_wait: Callable | None = None):
        with self._cond:
            if len(self._active) >= self._max_concurrent:
                raise CallError(
                    f'Too many concurrent permission operations in progress '
                    f'(maximum {self._max_concurrent}). Try again later.',
                    errno.EBUSY,
                )
            while self._conflicts(dataset, is_traverse):
                self._cond.wait(timeout=_PERM_LOCK_POLL_INTERVAL)
                if on_wait:
                    on_wait()
            self._active[dataset] = is_traverse
        try:
            yield
        finally:
            with self._cond:
                del self._active[dataset]
                self._cond.notify_all()


_perm_lock_registry = PermLockRegistry()


class AclTool:
    """
    Perform recursive ACL-related operations using fd-based operations via the
    truenas_os extension.

    `fd` must be an open O_RDONLY descriptor for the root path of the
    operation.  AclTool reads from it but does NOT close it; the caller owns
    the descriptor lifetime.

    If `job` is provided, progress updates are emitted no more frequently than
    every 1 second.
    """

    __slots__ = (
        'fd', 'action', 'uid', 'gid', 'options', 'job', 'tls',
        'nfs4_inh', 'posix_file_acl', '_action_fd_fn',
        'total_objects', 'cumulative_processed', 'last_report_time',
        'root_fn',
    )

    _OPTIONS_TYPE = types.MappingProxyType({
        AclToolAction.CHOWN: ATChownOptions,
        AclToolAction.STRIP: ATPermOptions,
        AclToolAction.CLONE: ATAclOptions,
        AclToolAction.INHERIT: ATAclOptions,
    })

    _ACTION_FN = types.MappingProxyType({
        AclToolAction.CHOWN: '_do_chown',
        AclToolAction.STRIP: '_do_strip',
        AclToolAction.CLONE: '_do_acl',
        AclToolAction.INHERIT: '_do_acl',
    })

    def __init__(self, fd, action, uid, gid, options, job=None, tls=None, root_fn=None):
        expected = self._OPTIONS_TYPE[action]
        if not isinstance(options, expected):
            raise TypeError(f'{action}: expected {expected.__name__}, got {type(options).__name__}')
        self.fd = fd
        self.action = action
        self.uid = uid
        self.gid = gid
        self.options = options
        self.job = job
        self.tls = tls
        self.total_objects = 0
        self.cumulative_processed = 0
        self.last_report_time = time.monotonic()
        self.nfs4_inh = None
        self.posix_file_acl = None
        self._action_fd_fn = getattr(self, self._ACTION_FN[action])
        self.root_fn = root_fn

    def _estimate_total(self, fs_name, mnt_id):
        """Populate self.total_objects before iteration begins."""
        if self.job is None or self.tls is None:
            return
        # Subdirectory: dataset-wide estimate would dwarf actual work
        mountpoint, _, rel_path, _ = _get_mount_info(self.fd)
        if rel_path is not None:
            return
        try:
            self.total_objects = estimate_object_count_impl(self.tls, fs_name)
            if self.options.traverse:
                real_path = os.readlink(f'/proc/self/fd/{self.fd}')
                _sm_flags = (
                    truenas_os.STATMOUNT_MNT_POINT |
                    truenas_os.STATMOUNT_SB_SOURCE |
                    truenas_os.STATMOUNT_FS_TYPE
                )
                for entry in truenas_os.iter_mount(mnt_id=mnt_id, statmount_flags=_sm_flags):
                    if not entry.mnt_point.startswith(real_path + '/'):
                        continue
                    if entry.fs_type == 'zfs' and entry.sb_source and '@' in entry.sb_source:
                        continue
                    if entry.fs_type == 'zfs' and entry.sb_source:
                        self.total_objects += estimate_object_count_impl(self.tls, entry.sb_source)
        except Exception:
            self.total_objects = 0

    def _report_progress(self, dir_stack, state, private_data):
        now = time.monotonic()
        if now - self.last_report_time < 1.0:
            return
        self.last_report_time = now
        if self.total_objects > 0:
            pct = min(10 + int(self.cumulative_processed / self.total_objects * 89), 99)
        else:
            pct = None
        self.job.set_progress(
            pct,
            f'Processing {state.current_directory} ({self.cumulative_processed:,} files processed)',
        )

    def _do_chown(self, fd, isdir, depth):
        os.fchown(fd, self.uid, self.gid)

    def _do_strip(self, fd, isdir, depth):
        truenas_os.fsetacl(fd, None)
        if self.uid != ACL_UNDEFINED_ID or self.gid != ACL_UNDEFINED_ID:
            os.fchown(fd, self.uid, self.gid)
        if self.options.target_mode is not None:
            os.fchmod(fd, self.options.target_mode & 0o7777)

    def _do_acl(self, fd, isdir, depth):
        if self.nfs4_inh is not None:
            # NFS4: use precomputed depth/type-specific inherited ACL
            truenas_os.fsetacl(fd, self.nfs4_inh.pick(depth, isdir))
        elif not isdir:
            # POSIX1E file: use precomputed file-inherited ACL
            truenas_os.fsetacl(fd, self.posix_file_acl)
        else:
            # POSIX1E dir: apply root ACL directly
            truenas_os.fsetacl(fd, self.options.target_acl)
        if self.uid != ACL_UNDEFINED_ID or self.gid != ACL_UNDEFINED_ID:
            os.fchown(fd, self.uid, self.gid)

    def _apply_action(self, item, it, depth_offset=0):
        self._action_fd_fn(item.fd, item.isdir, depth_offset + len(it.dir_stack()))

    def _process_mount(self, mnt_point, fs, rel, depth_offset=0):
        reporting_cb = self._report_progress if self.job is not None else None
        with truenas_os.iter_filesystem_contents(
            mnt_point, fs,
            relative_path=rel,
            reporting_increment=1000,
            reporting_callback=reporting_cb,
        ) as it:
            for item in it:
                self.cumulative_processed += 1
                if item.islnk:
                    continue
                try:
                    self._apply_action(item, it, depth_offset)
                except OSError as e:
                    raise CallError(f'acltool [{self.action}] failed on item in {mnt_point}: {e}')

    def run(self):
        mountpoint, fs_name, rel_path, mnt_id = _get_mount_info(self.fd)
        is_traverse = self.options.traverse
        wait_msg = f'Waiting to acquire {"traverse " if is_traverse else ""}lock on dataset {fs_name!r}'
        on_wait = (lambda: self.job.set_progress(0, wait_msg)) if self.job is not None else None

        with _perm_lock_registry.lock(fs_name, is_traverse, on_wait=on_wait):
            self._run_locked(mountpoint, fs_name, rel_path, mnt_id)

    def _run_locked(self, mountpoint, fs_name, rel_path, mnt_id):
        if self.root_fn is not None:
            self.root_fn(self.fd)
        self._estimate_total(fs_name, mnt_id)

        if self.action in (AclToolAction.CLONE, AclToolAction.INHERIT):
            if isinstance(self.options.target_acl, truenas_os.NFS4ACL):
                self.nfs4_inh = _NFS4InheritedAcls.from_root(self.options.target_acl)
            elif isinstance(self.options.target_acl, truenas_os.POSIXACL):
                self.posix_file_acl = self.options.target_acl.generate_inherited_acl(is_dir=False)

        self._process_mount(mountpoint, fs_name, rel_path)

        if self.options.traverse:
            real_path = os.readlink(f'/proc/self/fd/{self.fd}')
            _sm_flags = (
                truenas_os.STATMOUNT_MNT_POINT |
                truenas_os.STATMOUNT_SB_SOURCE |
                truenas_os.STATMOUNT_FS_TYPE
            )
            for entry in truenas_os.iter_mount(mnt_id=mnt_id, statmount_flags=_sm_flags):
                child_mnt = entry.mnt_point
                if not child_mnt.startswith(real_path + '/'):
                    continue

                # Skip ZFS snapshot mounts: they are read-only and transient, so
                # write operations (fsetacl/fchown/fchmod) would fail with EROFS.
                if entry.fs_type == 'zfs' and entry.sb_source and '@' in entry.sb_source:
                    continue

                child_depth = len(child_mnt[len(real_path):].strip('/').split('/'))
                child_fd = truenas_os.openat2(
                    child_mnt, flags=os.O_RDONLY, resolve=truenas_os.RESOLVE_NO_SYMLINKS
                )
                try:
                    try:
                        self.cumulative_processed += 1
                        self._action_fd_fn(child_fd, True, child_depth)
                    except OSError as e:
                        raise CallError(f'acltool [{self.action}] failed on {child_mnt}: {e}')
                    self._process_mount(child_mnt, entry.sb_source, None, depth_offset=child_depth)
                finally:
                    os.close(child_fd)


def calculate_inherited_acl(theacl: dict, isdir: bool = True) -> list:
    """
    Create a new ACL based on what a file or directory would receive if it
    were created within a directory that had `theacl` set on it.

    This is intended to be used for determining new ACL to set on a dataset
    that is created (in certain scenarios) to meet user expectations of
    inheritance.
    """
    acltype = FS_ACL_Type(theacl['acltype'])

    match acltype:
        case FS_ACL_Type.NFS4:
            obj = nfs4acl_dict_to_obj(theacl['acl'], theacl.get('aclflags'))
            return nfs4acl_obj_to_dict(obj.generate_inherited_acl(is_dir=isdir), 0, 0, simplified=False)['acl']

        case FS_ACL_Type.POSIX1E:
            obj = posixacl_dict_to_obj(theacl['acl'])
            return posixacl_obj_to_dict(obj.generate_inherited_acl(is_dir=isdir), 0, 0)['acl']

        case FS_ACL_Type.DISABLED:
            raise ValueError('ACL is disabled')

        case _:
            raise TypeError(f'{acltype}: unknown ACL type')
