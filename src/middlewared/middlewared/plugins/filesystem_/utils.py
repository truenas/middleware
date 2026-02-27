import dataclasses
import enum
import os
import time

import truenas_os

from middlewared.service_exception import CallError
from middlewared.utils.mount import statmount as _statmount
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
    return sm.mnt_point, sm.sb_source, (None if rel == '.' else rel)


def acltool(fd: int, action: AclToolAction, uid: int, gid: int, options: dict, job=None) -> None:
    """
    Perform recursive ACL-related operations using fd-based operations via the
    truenas_os extension.

    `fd` must be an open O_RDONLY descriptor for the root path of the
    operation.  acltool reads from it but does NOT close it; the caller owns
    the descriptor lifetime.

    If `job` is provided, progress updates are emitted at most once per 1 000
    items *and* no more frequently than every 1 second (whichever is later).
    """
    traverse = options.get('traverse', False)
    do_chmod = options.get('do_chmod', False)

    mountpoint, fs_name, rel_path = _get_mount_info(fd)

    root_acl = (
        truenas_os.fgetacl(fd)
        if action in (AclToolAction.CLONE, AclToolAction.INHERIT)
        else None
    )
    root_mode = os.fstat(fd).st_mode if do_chmod else None

    nfs4_inh = None
    if root_acl is not None and isinstance(root_acl, truenas_os.NFS4ACL):
        nfs4_inh = _NFS4InheritedAcls.from_root(root_acl)

    last_report_time = time.monotonic()

    def _report_progress(dir_stack, state, private_data):
        nonlocal last_report_time
        now = time.monotonic()
        if now - last_report_time < 1.0:
            return

        last_report_time = now
        job.set_progress(
            None,
            f'Processing {state.current_directory} ({state.cnt:,} files processed)',
        )

    reporting_callback = _report_progress if job is not None else None

    def _apply_action(item, it, depth_offset=0):
        if action == AclToolAction.CHOWN:
            os.fchown(item.fd, uid, gid)

        elif action == AclToolAction.STRIP:
            truenas_os.fsetacl(item.fd, None)
            if uid != ACL_UNDEFINED_ID or gid != ACL_UNDEFINED_ID:
                os.fchown(item.fd, uid, gid)
            if do_chmod and root_mode is not None:
                os.fchmod(item.fd, root_mode & 0o7777)

        elif action in (AclToolAction.CLONE, AclToolAction.INHERIT):
            if nfs4_inh is not None:
                inherited = nfs4_inh.pick(depth_offset + len(it.dir_stack()), item.isdir)
                truenas_os.fsetacl(item.fd, inherited)
            elif root_acl is not None:
                truenas_os.fsetacl(item.fd, root_acl)
            if uid != ACL_UNDEFINED_ID or gid != ACL_UNDEFINED_ID:
                os.fchown(item.fd, uid, gid)
            if do_chmod and root_mode is not None:
                os.fchmod(item.fd, root_mode & 0o7777)

    def _process_mount(mnt_point, fs, rel, depth_offset=0):
        with truenas_os.iter_filesystem_contents(
            mnt_point, fs,
            relative_path=rel,
            reporting_increment=1000,
            reporting_callback=reporting_callback,
        ) as it:
            for item in it:
                if item.islnk:
                    continue
                try:
                    _apply_action(item, it, depth_offset)
                except OSError as e:
                    raise CallError(f'acltool [{action}] failed on item in {mountpoint}: {e}')

    _process_mount(mountpoint, fs_name, rel_path)

    if traverse:
        real_path = os.readlink(f'/proc/self/fd/{fd}')
        for entry in truenas_os.iter_mount(
            statmount_flags=truenas_os.STATMOUNT_MNT_POINT | truenas_os.STATMOUNT_SB_SOURCE,
        ):
            child_mnt = entry.mnt_point
            if not child_mnt.startswith(real_path + '/'):
                continue
            child_depth = len(child_mnt[len(real_path):].strip('/').split('/'))
            _process_mount(child_mnt, entry.sb_source, None, depth_offset=child_depth)



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
