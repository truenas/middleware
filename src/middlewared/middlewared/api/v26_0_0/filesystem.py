from middlewared.api.base import (
    BaseModel,
    NonEmptyString,
    UnixPerm,
    single_argument_args,
    single_argument_result,
    query_result
)
from pydantic import Field, model_validator
from typing import Any, Literal, Self
from middlewared.utils.filesystem.acl import (
    ACL_UNDEFINED_ID,
)
from middlewared.utils.filesystem.stat_x import (
    StatxEtype,
)
from .acl import AceWhoId
from .common import QueryFilters, QueryOptions

__all__ = [
    'FilesystemChownArgs', 'FilesystemChownResult',
    'FilesystemSetpermArgs', 'FilesystemSetpermResult',
    'FilesystemListdirArgs', 'FilesystemListdirResult',
    'FilesystemMkdirArgs', 'FilesystemMkdirResult',
    'FilesystemStatArgs', 'FilesystemStatResult',
    'FilesystemStatfsArgs', 'FilesystemStatfsResult',
    'FilesystemSetZfsAttributesArgs', 'FilesystemSetZfsAttributesResult',
    'FilesystemGetZfsAttributesArgs', 'FilesystemGetZfsAttributesResult',
    'FilesystemGetArgs', 'FilesystemGetResult',
    'FilesystemPutArgs', 'FilesystemPutResult',
    'FileFollowTailEventSourceArgs', 'FileFollowTailEventSourceEvent',
]


UNSET_ENTRY = frozenset([ACL_UNDEFINED_ID, None])


class FilesystemRecursionOptions(BaseModel):
    recursive: bool = Field(default=False, description="Whether to apply the operation recursively to subdirectories.")
    traverse: bool = Field(default=False, description="If set do not limit to single dataset / filesystem.")


class FilesystemChownOptions(FilesystemRecursionOptions):
    pass


class FilesystemSetpermOptions(FilesystemRecursionOptions):
    stripacl: bool = Field(
        default=False,
        description="Whether to remove existing Access Control Lists when setting permissions.",
    )


class FilesystemPermChownBase(BaseModel):
    path: NonEmptyString = Field(description="Filesystem path to modify.")
    uid: AceWhoId | None = Field(
        default=None,
        description="Numeric user ID to set as owner. `null` to leave unchanged.",
    )
    user: NonEmptyString | None = Field(
        default=None,
        description="Username to set as owner. `null` to leave unchanged.",
    )
    gid: AceWhoId | None = Field(
        default=None,
        description="Numeric group ID to set as group owner. `null` to leave unchanged.",
    )
    group: NonEmptyString | None = Field(
        default=None,
        description="Group name to set as group owner. `null` to leave unchanged.",
    )


@single_argument_args('filesystem_chown')
class FilesystemChownArgs(FilesystemPermChownBase):
    options: FilesystemChownOptions = Field(
        default=FilesystemChownOptions(),
        description="Additional options for the ownership change operation.",
    )

    @model_validator(mode='after')
    def user_group_present(self) -> Self:
        if all(field in UNSET_ENTRY for field in (self.uid, self.user, self.gid, self.group)):
            raise ValueError(
                'At least one of uid, gid, user, and group must be set in chown payload'
            )

        return self


class FilesystemChownResult(BaseModel):
    result: None = Field(description="Returns `null` when the ownership change is successfully completed.")


@single_argument_args('filesystem_setperm')
class FilesystemSetpermArgs(FilesystemPermChownBase):
    mode: UnixPerm | None = Field(
        default=None,
        description="Unix permissions to set (octal format). `null` to leave unchanged.",
    )
    options: FilesystemSetpermOptions = Field(
        default=FilesystemSetpermOptions(),
        description="Additional options for the permission change operation.",
    )

    @model_validator(mode='after')
    def payload_is_actionable(self) -> Self:
        """ User should be changing something. Either stripping ACL or setting mode """
        if self.mode is None and self.options.stripacl is False:
            raise ValueError(
                'Payload must either explicitly specify permissions or '
                'contain the stripacl option.'
            )

        return self


class FilesystemSetpermResult(BaseModel):
    result: None = Field(description="Returns `null` when the permission change is successfully completed.")


FILESYSTEM_STATX_ATTRS = Literal[
    'COMPRESSED',
    'APPEND',
    'NODUMP',
    'IMMUTABLE',
    'AUTOMOUNT',
    'MOUNT_ROOT',
    'VERIFY',
    'DAX'
]


FILESYSTEM_ZFS_ATTRS = Literal[
    'READONLY',
    'HIDDEN',
    'SYSTEM',
    'ARCHIVE',
    'IMMUTABLE',
    'NOUNLINK',
    'APPENDONLY',
    'NODUMP',
    'OPAQUE',
    'AV_QUARANTINED',
    'AV_MODIFIED',
    'REPARSE',
    'OFFLINE',
    'SPARSE'
]


FileType = Literal[
    StatxEtype.DIRECTORY,
    StatxEtype.FILE,
    StatxEtype.SYMLINK,
    StatxEtype.OTHER,
]


class FilesystemDirEntry(BaseModel):
    name: NonEmptyString = Field(description="Entry's base name.")
    path: NonEmptyString = Field(description="Entry's full path.")
    realpath: NonEmptyString = Field(description="Canonical path of the entry, eliminating any symbolic links.")
    type: FileType = Field(
        description=(
            "Type of filesystem entry.\n"
            "\n"
            "* `DIRECTORY`: Directory/folder\n"
            "* `FILE`: Regular file\n"
            "* `SYMLINK`: Symbolic link\n"
            "* `OTHER`: Other file types (device, pipe, socket, etc.)"
        ),
    )
    size: int = Field(
        description=(
            "Size of the file in bytes. For directories, this may not represent total content size. Corresonds with "
            "stx_size."
        ),
    )
    allocation_size: int = Field(description="Allocated size of file. Calculated by multiplying stx_blocks by 512.")
    mode: int = Field(
        description=(
            "Entry's mode including file type information and file permission bits. This corresponds with stx_mode."
        ),
    )
    mount_id: int = Field(
        description=(
            "The mount ID of the mount containing the entry. This corresponds to the number in first field of "
            "/proc/self/mountinfo and stx_mnt_id."
        ),
    )
    acl: bool = Field(
        description=(
            "Specifies whether ACL is present on the entry. If this is the case then file permission bits as reported "
            "in `mode` may not be representative of the actual permissions."
        ),
    )
    uid: int = Field(description="User ID of the entry's owner. This corresponds with stx_uid.")
    gid: int = Field(description="Group ID of the entry's owner. This corresponds with stx_gid.")
    is_mountpoint: bool = Field(description="Specifies whether the entry is also the mountpoint of a filesystem.")
    is_ctldir: bool = Field(
        description="Specifies whether the entry is located within the ZFS ctldir (for example a snapshot).",
    )
    attributes: list[FILESYSTEM_STATX_ATTRS] = Field(
        description="Extra file attribute indicators for entry as returned by statx. Expanded from stx_attributes.",
    )
    xattrs: list[NonEmptyString] = Field(description="List of xattr names of extended attributes on file.")
    zfs_attrs: list[FILESYSTEM_ZFS_ATTRS] | None = Field(
        description=(
            "List of extra ZFS-related file attribute indicators on file. Will be None type if filesystem is not ZFS."
        ),
    )


class FilesystemListdirArgs(BaseModel):
    path: NonEmptyString = Field(description="Directory path to list contents of.")
    query_filters: QueryFilters = Field(default=[], description="Query filters to apply to the directory listing.")
    query_options: QueryOptions = Field(default=QueryOptions(), description="Query options for sorting and pagination.")


FilesystemListdirResult = query_result(FilesystemDirEntry, "FilesystemListdirResult")


class FilesystemMkdirOptions(BaseModel):
    mode: UnixPerm = Field(default='755', description="Unix permissions for the new directory.")
    raise_chmod_error: bool = Field(default=True, description="Whether to raise an error if chmod fails.")


@single_argument_args('filesystem_mkdir')
class FilesystemMkdirArgs(BaseModel):
    path: NonEmptyString = Field(description="Path where the new directory should be created.")
    options: FilesystemMkdirOptions = Field(
        default=FilesystemMkdirOptions(),
        description="Options controlling directory creation behavior.",
    )


class FilesystemMkdirResult(BaseModel):
    result: FilesystemDirEntry = Field(description="Information about the created directory.")


class FilesystemStatData(BaseModel):
    realpath: NonEmptyString = Field(description="Canonical path of the entry, eliminating any symbolic links.")
    type: FileType = Field(description="Type of filesystem entry.")
    size: int = Field(description="Size in bytes of a plain file. This corresonds with stx_size.")
    allocation_size: int = Field(description="Allocated size of file. Calculated by multiplying stx_blocks by 512.")
    mode: int = Field(
        description=(
            "Entry's mode including file type information and file permission bits. This corresponds with stx_mode."
        ),
    )
    mount_id: int = Field(
        description=(
            "The mount ID of the mount containing the entry. This corresponds to the number in first field of "
            "/proc/self/mountinfo and stx_mnt_id."
        ),
    )
    uid: int = Field(description="User ID of the entry's owner. This corresponds with stx_uid.")
    gid: int = Field(description="Group ID of the entry's owner. This corresponds with stx_gid.")
    atime: float = Field(description="Time of last access. Corresponds with stx_atime. This is mutable from userspace.")
    mtime: float = Field(
        description="Time of last modification. Corresponds with stx_mtime. This is mutable from userspace.",
    )
    ctime: float = Field(description="Time of last status change. Corresponds with stx_ctime.")
    btime: float = Field(description="Time of creation. Corresponds with stx_btime.")
    dev: int = Field(
        description=(
            "The ID of the device containing the filesystem where the file resides. This is not sufficient to uniquely "
            "identify a particular filesystem mount. mount_id must be used for that purpose. This corresponds with "
            "st_dev."
        ),
    )
    inode: int = Field(description="The inode number of the file. This corresponds with stx_ino.")
    nlink: int = Field(description="Number of hard links. Corresponds with stx_nlinks.")
    acl: bool = Field(
        description=(
            "Specifies whether ACL is present on the entry. If this is the case then file permission bits as reported "
            "in `mode` may not be representative of the actual permissions."
        ),
    )
    is_mountpoint: bool = Field(description="Specifies whether the entry is also the mountpoint of a filesystem.")
    is_ctldir: bool = Field(
        description="Specifies whether the entry is located within the ZFS ctldir (for example a snapshot).",
    )
    attributes: list[FILESYSTEM_STATX_ATTRS] = Field(
        description="Extra file attribute indicators for entry as returned by statx. Expanded from stx_attributes.",
    )
    user: NonEmptyString | None = Field(
        description="Username associated with `uid`. Will be None if the User ID does not map to existing user.",
    )
    group: NonEmptyString | None = Field(
        description="Groupname associated with `gid`. Will be None if the Group ID does not map to existing group.",
    )


class FilesystemStatArgs(BaseModel):
    path: NonEmptyString = Field(description="Absolute filesystem path to get statistics for.")


class FilesystemStatResult(BaseModel):
    result: FilesystemStatData = Field(description="File or directory statistics information.")


StatfsFlags = Literal[
    'RW', 'RO',
    'XATTR',
    'NOACL', 'NFS4ACL', 'POSIXACL',
    'CASESENSITIVE', 'CASEINSENSITIVE',
    'NOATIME', 'RELATIME',
    'NOSUID', 'NODEV', 'NOEXEC',
]


StatfsFstype = Literal['zfs', 'tmpfs']


class FilesystemStatfsData(BaseModel):
    flags: list[StatfsFlags | Any] = Field(
        description="Combined per-mount options and per-superblock options for mounted filesystem.",
    )  # ANY is here because we can't predict what random FS will have
    fsid: NonEmptyString = Field(description="Unique filesystem ID as returned by statvfs.")
    fstype: StatfsFlags | Any = Field(
        description="String representation of filesystem type from mountinfo.",
    )  # Same as with flags
    source: NonEmptyString = Field(description="Source for the mounted filesystem. For ZFS this will be dataset name.")
    dest: NonEmptyString = Field(description="Local path on which filesystem is mounted.")
    blocksize: int = Field(description="Filesystem block size as reported by statvfs.")
    total_blocks: int = Field(description="Filesystem size as reported in blocksize blocks as reported by statvfs.")
    free_blocks: int = Field(description="Number of free blocks as reported by statvfs.")
    avail_blocks: int = Field(description="Number of available blocks as reported by statvfs.")
    total_blocks_str: NonEmptyString = Field(description="Total filesystem size in blocks as a human-readable string.")
    free_blocks_str: NonEmptyString = Field(description="Free blocks available as a human-readable string.")
    avail_blocks_str: NonEmptyString = Field(
        description="Available blocks for unprivileged users as a human-readable string.",
    )
    files: int = Field(description="Number of inodes in use as reported by statvfs.")
    free_files: int = Field(description="Number of free inodes as reported by statvfs.")
    name_max: int = Field(description="Maximum filename length as reported by statvfs.")
    total_bytes: int = Field(description="Total filesystem size in bytes.")
    free_bytes: int = Field(description="Free space available in bytes.")
    avail_bytes: int = Field(description="Available space for unprivileged users in bytes.")
    total_bytes_str: NonEmptyString = Field(description="Total filesystem size in bytes as a human-readable string.")
    free_bytes_str: NonEmptyString = Field(description="Free space available in bytes as a human-readable string.")
    avail_bytes_str: NonEmptyString = Field(
        description="Available space for unprivileged users in bytes as a human-readable string.",
    )


class FilesystemStatfsArgs(BaseModel):
    path: NonEmptyString = Field(description="Path on the filesystem to get statistics for.")


class FilesystemStatfsResult(BaseModel):
    result: FilesystemStatfsData = Field(description="Filesystem statistics and mount information.")


class ZFSFileAttrsData(BaseModel):
    readonly: bool | None = Field(
        default=None,
        description=(
            "READONLY MS-DOS attribute. When set, file may not be written to (toggling does not impact existing file "
            "opens)."
        ),
    )
    hidden: bool | None = Field(
        default=None,
        description=(
            "HIDDEN MS-DOS attribute. When set, the SMB HIDDEN flag is set and file is \"hidden\" from the perspective "
            "of SMB clients."
        ),
    )
    system: bool | None = Field(
        default=None,
        description="SYSTEM MS-DOS attribute. Is presented to SMB clients, but has no impact on local filesystem.",
    )
    archive: bool | None = Field(
        default=None,
        description="ARCHIVE MS-DOS attribute. Value is reset to True whenever file is modified.",
    )
    immutable: bool | None = Field(
        default=None,
        description=(
            "File may not be altered or deleted. Also appears as IMMUTABLE in attributes in `filesystem.stat` output "
            "and as STATX_ATTR_IMMUTABLE in statx() response."
        ),
    )
    nounlink: bool | None = Field(default=None, description="File may be altered but not deleted.")
    appendonly: bool | None = Field(
        default=None,
        description=(
            "File may only be opened with O_APPEND flag. Also appears as APPEND in attributes in `filesystem.stat` "
            "output and as STATX_ATTR_APPEND in statx() response."
        ),
    )
    offline: bool | None = Field(
        default=None,
        description="OFFLINE MS-DOS attribute. Is presented to SMB clients, but has no impact on local filesystem.",
    )
    sparse: bool | None = Field(
        default=None,
        description="SPARSE MS-DOS attribute. Is presented to SMB clients, but has no impact on local filesystem.",
    )


FilesystemZFSAttrRecursiveTarget = Literal['FILES', 'DIRECTORIES']


class FilesystemSetZfsAttributesOptions(BaseModel):
    recursive: list[FilesystemZFSAttrRecursiveTarget] | None = Field(
        default=None,
        description=(
            "If set, walk the tree under `path` and apply attributes to entries whose type appears in the list "
            "(`FILES`, `DIRECTORIES`, or both). The root `path` is included only if its type matches the filter. `null`"
            " means no recursion (operate on `path` only). An empty list is rejected."
        ),
    )


@single_argument_args('set_zfs_file_attributes')
class FilesystemSetZfsAttributesArgs(BaseModel):
    path: NonEmptyString = Field(description="Path to the file or directory to set ZFS attributes on.")
    zfs_file_attributes: ZFSFileAttrsData = Field(description="ZFS file attributes to set.")
    options: FilesystemSetZfsAttributesOptions = Field(
        default=FilesystemSetZfsAttributesOptions(),
        description="Additional options including recursion behavior.",
    )


class FilesystemSetZfsAttributesResult(BaseModel):
    result: ZFSFileAttrsData = Field(description="The updated ZFS file attributes for the root `path`.")


class FilesystemGetZfsAttributesArgs(BaseModel):
    path: NonEmptyString = Field(description="Path to the file to get ZFS attributes for.")


class FilesystemGetZfsAttributesResult(BaseModel):
    result: ZFSFileAttrsData = Field(description="The current ZFS file attributes.")


class FilesystemGetArgs(BaseModel):
    path: NonEmptyString = Field(description="Path of the file to read.")


class FilesystemGetResult(BaseModel):
    result: None = Field(description="Returns `null` when the file is successfully read.")


class FilesystemPutOptions(BaseModel):
    append: bool = Field(default=False, description="Whether to append to the file instead of overwriting.")
    mode: int | None = Field(default=None, description="Unix permissions to set on the file or `null` to use default.")


class FilesystemPutArgs(BaseModel):
    path: NonEmptyString = Field(description="Path where the file should be written.")
    options: FilesystemPutOptions = Field(
        default=FilesystemPutOptions(),
        description="Options controlling file writing behavior.",
    )


class FilesystemPutResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the file is successfully written.")


class FileFollowTailEventSourceArgs(BaseModel):
    path: str = Field(description="Path to the file to follow/tail.")
    tail_lines: int = Field(default=3, description="Number of log lines to tail from the end of the log.")


@single_argument_result
class FileFollowTailEventSourceEvent(BaseModel):
    data: str = Field(description="New data appended to the file being followed.")
