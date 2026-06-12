import dataclasses
import enum
import os
import time
import types

import truenas_os
from truenas_os_pyutils.mount import statmount as _statmount

from middlewared.api.current import ZFSFileAttrsData
from middlewared.service_exception import CallError
from middlewared.utils.filesystem.acl import (
    ACL_UNDEFINED_ID,
    FS_ACL_Type,
    nfs4acl_dict_to_obj,
    nfs4acl_obj_to_dict,
    posixacl_dict_to_obj,
    posixacl_obj_to_dict,
)
from middlewared.utils.filesystem.attrs import (
    dict_to_zfs_attributes_mask,
    fget_zfs_file_attributes,
    fset_zfs_file_attributes,
    zfs_attributes_to_dict,
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


class _FsRecursionOp:
    """
    Recursive filesystem operation engine.

    Walks the tree under an open O_RDONLY directory `fd` via
    truenas_os.iter_filesystem_contents, optionally crossing dataset
    boundaries (options.traverse), and emits job progress updates throttled
    to >= 1s. Subclasses implement `_apply_action_fd` to perform the
    per-entry work and may override `_setup` for one-time precomputation.

    `fd` must be an open O_RDONLY descriptor for the root path of the
    operation. The base class reads from it but does NOT close it; the
    caller owns the descriptor lifetime.
    """

    _label = 'fsrecursion'

    # ZFS datasets have 6 internal objects (master node, SA attrs, unlinked
    # set, root dir, SA attr registration, SA attr layouts) reported in
    # f_files; subtract them so progress reflects user-visible objects. For
    # non-ZFS filesystems the offset is harmless (estimate is approximate).
    _ZFS_INTERNAL_OBJECTS = 6

    __slots__ = (
        'fd', 'options', 'job',
        'total_objects', 'cumulative_processed', 'last_report_time',
    )

    def __init__(self, fd, options, job=None):
        self.fd = fd
        self.options = options
        self.job = job
        self.total_objects = 0
        self.cumulative_processed = 0
        self.last_report_time = time.monotonic()

    def _estimate_total(self, fs_name, mnt_id):
        """Populate self.total_objects before iteration begins.

        Uses fstatvfs(f_files - f_ffree) on the root fd plus statvfs() on each
        child mount when traverse is enabled. No libzfs handle required.
        """
        if self.job is None:
            return
        # Subdirectory: dataset-wide estimate would dwarf actual work
        _, _, rel_path, _ = _get_mount_info(self.fd)
        if rel_path is not None:
            return
        try:
            sv = os.fstatvfs(self.fd)
            self.total_objects = max(
                sv.f_files - sv.f_ffree - self._ZFS_INTERNAL_OBJECTS, 0
            )
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
                    try:
                        sv = os.statvfs(entry.mnt_point)
                    except OSError:
                        continue
                    self.total_objects += max(
                        sv.f_files - sv.f_ffree - self._ZFS_INTERNAL_OBJECTS, 0
                    )
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

    def _setup(self):
        """Override for one-time setup before walk begins (default: no-op)."""

    def _apply_action_fd(self, fd, isdir, depth):
        """Subclass hook: apply the operation to a single open fd."""
        raise NotImplementedError

    def _apply_action(self, item, it, depth_offset=0):
        self._apply_action_fd(item.fd, item.isdir, depth_offset + len(it.dir_stack()))

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
                    raise CallError(f'{self._label} failed on item in {mnt_point}: {e}')

    def run(self):
        mountpoint, fs_name, rel_path, mnt_id = _get_mount_info(self.fd)

        self._estimate_total(fs_name, mnt_id)
        self._setup()

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
                        self._apply_action_fd(child_fd, True, child_depth)
                    except OSError as e:
                        raise CallError(f'{self._label} failed on {child_mnt}: {e}')
                    self._process_mount(child_mnt, entry.sb_source, None, depth_offset=child_depth)
                finally:
                    os.close(child_fd)


class AclTool(_FsRecursionOp):
    """
    Perform recursive ACL-related operations using fd-based operations via the
    truenas_os extension.
    """

    __slots__ = (
        'action', 'uid', 'gid', 'nfs4_inh', 'posix_file_acl', '_action_fd_fn',
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

    def __init__(self, fd, action, uid, gid, options, job=None):
        expected = self._OPTIONS_TYPE[action]
        if not isinstance(options, expected):
            raise TypeError(f'{action}: expected {expected.__name__}, got {type(options).__name__}')
        super().__init__(fd, options, job)
        self.action = action
        self.uid = uid
        self.gid = gid
        self.nfs4_inh = None
        self.posix_file_acl = None
        self._action_fd_fn = getattr(self, self._ACTION_FN[action])

    @property
    def _label(self):
        return f'acltool [{self.action}]'

    def _setup(self):
        if self.action in (AclToolAction.CLONE, AclToolAction.INHERIT):
            if isinstance(self.options.target_acl, truenas_os.NFS4ACL):
                self.nfs4_inh = _NFS4InheritedAcls.from_root(self.options.target_acl)
            elif isinstance(self.options.target_acl, truenas_os.POSIXACL):
                self.posix_file_acl = self.options.target_acl.generate_inherited_acl(is_dir=False)

    def _apply_action_fd(self, fd, isdir, depth):
        self._action_fd_fn(fd, isdir, depth)

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


class ZfsAttrTool(_FsRecursionOp):
    """
    Recursively apply a ZFS attribute change to a tree under an open dir fd.

    `attrs_dict` is keyed by lower-case ZFS attr name (None values stripped).
    Only entries whose type (file or directory) matches `targets` receive
    the change. Symlinks are skipped (inherited from base walk).

    `targets` is a sequence containing 'FILES', 'DIRECTORIES', or both.
    """

    _label = 'set_zfs_attributes'

    __slots__ = ('attrs_dict', '_apply_to_files', '_apply_to_dirs')

    def __init__(self, fd, attrs_dict, targets, job=None):
        super().__init__(fd, ATBaseOptions(traverse=False), job)
        self.attrs_dict = {k: v for k, v in attrs_dict.items() if v is not None}
        self._apply_to_files = 'FILES' in targets
        self._apply_to_dirs = 'DIRECTORIES' in targets

    def _apply_action_fd(self, fd, isdir, depth):
        if isdir and not self._apply_to_dirs:
            return
        if not isdir and not self._apply_to_files:
            return
        current = zfs_attributes_to_dict(fget_zfs_file_attributes(fd))
        new = current | self.attrs_dict
        if new == current:
            return
        fset_zfs_file_attributes(fd, dict_to_zfs_attributes_mask(new))


def apply_zfs_attrs_recursive(fd, is_dir, attrs_in: ZFSFileAttrsData, targets, job=None) -> ZFSFileAttrsData:
    """
    Apply ZFS attribute changes to an open root fd and (if `is_dir`) walk
    the tree under it applying the same change to descendants whose type is
    in `targets`. The root fd is touched only if its type appears in
    `targets`.

    `targets` is a sequence containing 'FILES', 'DIRECTORIES', or both.
    `attrs_in` is the dict from the API model (lower-case keys, bool|None
    values; None values are ignored).

    Returns the post-op attrs dict for the root, suitable as the API result.
    """
    apply_to_root = (
        (is_dir and 'DIRECTORIES' in targets) or
        (not is_dir and 'FILES' in targets)
    )

    current = zfs_attributes_to_dict(fget_zfs_file_attributes(fd))

    if apply_to_root:
        attrs_filtered = {k: v for k, v in attrs_in.model_dump().items() if v is not None}
        new = current | attrs_filtered
        if new != current:
            fset_zfs_file_attributes(fd, dict_to_zfs_attributes_mask(new))
            current = zfs_attributes_to_dict(fget_zfs_file_attributes(fd))

    if is_dir:
        ZfsAttrTool(fd, attrs_in.model_dump(), targets, job=job).run()

    return ZFSFileAttrsData(**current)


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
