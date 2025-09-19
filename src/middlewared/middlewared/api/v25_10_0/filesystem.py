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
    recursive: bool = False
    """Whether to apply the operation recursively to subdirectories."""
    traverse: bool = False
    """If set do not limit to single dataset / filesystem."""


class FilesystemChownOptions(FilesystemRecursionOptions):
    pass


class FilesystemSetpermOptions(FilesystemRecursionOptions):
    stripacl: bool = False
    """Whether to remove existing Access Control Lists when setting permissions."""


class FilesystemPermChownBase(BaseModel):
    path: NonEmptyString
    """Filesystem path to modify."""
    uid: AceWhoId | None = None
    """Numeric user ID to set as owner. `null` to leave unchanged."""
    user: NonEmptyString | None = None
    """Username to set as owner. `null` to leave unchanged."""
    gid: AceWhoId | None = None
    """Numeric group ID to set as group owner. `null` to leave unchanged."""
    group: NonEmptyString | None = None
    """Group name to set as group owner. `null` to leave unchanged."""


@single_argument_args('filesystem_chown')
class FilesystemChownArgs(FilesystemPermChownBase):
    options: FilesystemChownOptions = Field(default=FilesystemChownOptions())
    """Additional options for the ownership change operation."""

    @model_validator(mode='after')
    def user_group_present(self) -> Self:
        if all(field in UNSET_ENTRY for field in (self.uid, self.user, self.gid, self.group)):
            raise ValueError(
                'At least one of uid, gid, user, and group must be set in chown payload'
            )

        return self


class FilesystemChownResult(BaseModel):
    result: None
    """Returns `null` when the ownership change is successfully completed."""


@single_argument_args('filesystem_setperm')
class FilesystemSetpermArgs(FilesystemPermChownBase):
    mode: UnixPerm | None = None
    """Unix permissions to set (octal format). `null` to leave unchanged."""
    options: FilesystemSetpermOptions = Field(default=FilesystemSetpermOptions())
    """Additional options for the permission change operation."""

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
    result: None
    """Returns `null` when the permission change is successfully completed."""


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
    name: NonEmptyString
    """ Entry's base name. """
    path: NonEmptyString
    """ Entry's full path. """
    realpath: NonEmptyString
    """ Canonical path of the entry, eliminating any symbolic links. """
    type: FileType
    """Type of filesystem entry.

    * `DIRECTORY`: Directory/folder
    * `FILE`: Regular file
    * `SYMLINK`: Symbolic link
    * `OTHER`: Other file types (device, pipe, socket, etc.)
    """
    size: int
    """Size of the file in bytes. For directories, this may not represent total content size. Corresonds with \
    stx_size."""
    allocation_size: int
    """ Allocated size of file. Calculated by multiplying stx_blocks by 512. """
    mode: int
    """ Entry's mode including file type information and file permission bits. This corresponds with stx_mode. """
    mount_id: int
    """ The mount ID of the mount containing the entry. This corresponds to the number in first \
    field of /proc/self/mountinfo and stx_mnt_id. """
    acl: bool
    """ Specifies whether ACL is present on the entry. If this is the case then file permission \
    bits as reported in `mode` may not be representative of the actual permissions. """
    uid: int
    """ User ID of the entry's owner. This corresponds with stx_uid. """
    gid: int
    """ Group ID of the entry's owner. This corresponds with stx_gid. """
    is_mountpoint: bool
    """ Specifies whether the entry is also the mountpoint of a filesystem. """
    is_ctldir: bool
    """ Specifies whether the entry is located within the ZFS ctldir (for example a snapshot). """
    attributes: list[FILESYSTEM_STATX_ATTRS]
    """ Extra file attribute indicators for entry as returned by statx. Expanded from stx_attributes. """
    xattrs: list[NonEmptyString]
    """ List of xattr names of extended attributes on file. """
    zfs_attrs: list[FILESYSTEM_ZFS_ATTRS] | None
    """ List of extra ZFS-related file attribute indicators on file. Will be None type if filesystem is not ZFS. """


class FilesystemListdirArgs(BaseModel):
    path: NonEmptyString
    """Directory path to list contents of."""
    query_filters: QueryFilters = []
    """Query filters to apply to the directory listing."""
    query_options: QueryOptions = QueryOptions()
    """Query options for sorting and pagination."""


FilesystemListdirResult = query_result(FilesystemDirEntry, "FilesystemListdirResult")


class FilesystemMkdirOptions(BaseModel):
    mode: UnixPerm = '755'
    """Unix permissions for the new directory."""
    raise_chmod_error: bool = True
    """Whether to raise an error if chmod fails."""


@single_argument_args('filesystem_mkdir')
class FilesystemMkdirArgs(BaseModel):
    path: NonEmptyString
    """Path where the new directory should be created."""
    options: FilesystemMkdirOptions = Field(default=FilesystemMkdirOptions())
    """Options controlling directory creation behavior."""


class FilesystemMkdirResult(BaseModel):
    result: FilesystemDirEntry
    """Information about the created directory."""


class FilesystemStatData(BaseModel):
    realpath: NonEmptyString
    """ Canonical path of the entry, eliminating any symbolic links. """
    type: FileType
    """Type of filesystem entry."""
    size: int
    """ Size in bytes of a plain file. This corresonds with stx_size. """
    allocation_size: int
    """ Allocated size of file. Calculated by multiplying stx_blocks by 512. """
    mode: int
    """ Entry's mode including file type information and file permission bits. This corresponds with stx_mode. """
    mount_id: int
    """ The mount ID of the mount containing the entry. This corresponds to the number in first \
    field of /proc/self/mountinfo and stx_mnt_id. """
    uid: int
    """ User ID of the entry's owner. This corresponds with stx_uid. """
    gid: int
    """ Group ID of the entry's owner. This corresponds with stx_gid. """
    atime: float
    """ Time of last access. Corresponds with stx_atime. This is mutable from userspace. """
    mtime: float
    """ Time of last modification. Corresponds with stx_mtime. This is mutable from userspace. """
    ctime: float
    """ Time of last status change. Corresponds with stx_ctime. """
    btime: float
    """ Time of creation. Corresponds with stx_btime. """
    dev: int
    """ The ID of the device containing the filesystem where the file resides. This is not sufficient to uniquely \
    identify a particular filesystem mount. mount_id must be used for that purpose. This corresponds with st_dev. """
    inode: int
    """ The inode number of the file. This corresponds with stx_ino. """
    nlink: int
    """ Number of hard links. Corresponds with stx_nlinks. """
    acl: bool
    """ Specifies whether ACL is present on the entry. If this is the case then file permission \
    bits as reported in `mode` may not be representative of the actual permissions. """
    is_mountpoint: bool
    """ Specifies whether the entry is also the mountpoint of a filesystem. """
    is_ctldir: bool
    """ Specifies whether the entry is located within the ZFS ctldir (for example a snapshot). """
    attributes: list[FILESYSTEM_STATX_ATTRS]
    """ Extra file attribute indicators for entry as returned by statx. Expanded from stx_attributes. """
    user: NonEmptyString | None
    """ Username associated with `uid`. Will be None if the User ID does not map to existing user. """
    group: NonEmptyString | None
    """ Groupname associated with `gid`. Will be None if the Group ID does not map to existing group. """


class FilesystemStatArgs(BaseModel):
    path: NonEmptyString
    """Absolute filesystem path to get statistics for."""


class FilesystemStatResult(BaseModel):
    result: FilesystemStatData
    """File or directory statistics information."""


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
    flags: list[StatfsFlags | Any]  # ANY is here because we can't predict what random FS will have
    """ Combined per-mount options and per-superblock options for mounted filesystem. """
    fsid: NonEmptyString
    """ Unique filesystem ID as returned by statvfs. """
    fstype: StatfsFlags | Any  # Same as with flags
    """ String representation of filesystem type from mountinfo. """
    source: NonEmptyString
    """ Source for the mounted filesystem. For ZFS this will be dataset name. """
    dest: NonEmptyString
    """ Local path on which filesystem is mounted. """
    blocksize: int
    """ Filesystem block size as reported by statvfs. """
    total_blocks: int
    """ Filesystem size as reported in blocksize blocks as reported by statvfs. """
    free_blocks: int
    """ Number of free blocks as reported by statvfs. """
    avail_blocks: int
    """ Number of available blocks as reported by statvfs. """
    total_blocks_str: NonEmptyString
    """Total filesystem size in blocks as a human-readable string."""
    free_blocks_str: NonEmptyString
    """Free blocks available as a human-readable string."""
    avail_blocks_str: NonEmptyString
    """Available blocks for unprivileged users as a human-readable string."""
    files: int
    """ Number of inodes in use as reported by statvfs. """
    free_files: int
    """ Number of free inodes as reported by statvfs. """
    name_max: int
    """ Maximum filename length as reported by statvfs. """
    total_bytes: int
    """Total filesystem size in bytes."""
    free_bytes: int
    """Free space available in bytes."""
    avail_bytes: int
    """Available space for unprivileged users in bytes."""
    total_bytes_str: NonEmptyString
    """Total filesystem size in bytes as a human-readable string."""
    free_bytes_str: NonEmptyString
    """Free space available in bytes as a human-readable string."""
    avail_bytes_str: NonEmptyString
    """Available space for unprivileged users in bytes as a human-readable string."""


class FilesystemStatfsArgs(BaseModel):
    path: NonEmptyString
    """Path on the filesystem to get statistics for."""


class FilesystemStatfsResult(BaseModel):
    result: FilesystemStatfsData
    """Filesystem statistics and mount information."""


class ZFSFileAttrsData(BaseModel):
    readonly: bool | None = None
    """ READONLY MS-DOS attribute. When set, file may not be written to (toggling \
    does not impact existing file opens). """
    hidden: bool | None = None
    """ HIDDEN MS-DOS attribute. When set, the SMB HIDDEN flag is set and file \
    is "hidden" from the perspective of SMB clients. """
    system: bool | None = None
    """ SYSTEM MS-DOS attribute. Is presented to SMB clients, but has no impact on local filesystem. """
    archive: bool | None = None
    """ ARCHIVE MS-DOS attribute. Value is reset to True whenever file is modified. """
    immutable: bool | None = None
    """ File may not be altered or deleted. Also appears as IMMUTABLE in attributes in \
    `filesystem.stat` output and as STATX_ATTR_IMMUTABLE in statx() response. """
    nounlink: bool | None = None
    """ File may be altered but not deleted. """
    appendonly: bool | None = None
    """ File may only be opened with O_APPEND flag. Also appears as APPEND in \
    attributes in `filesystem.stat` output and as STATX_ATTR_APPEND in statx() response. """
    offline: bool | None = None
    """ OFFLINE MS-DOS attribute. Is presented to SMB clients, but has no impact on local filesystem. """
    sparse: bool | None = None
    """ SPARSE MS-DOS attribute. Is presented to SMB clients, but has no impact on local filesystem. """


@single_argument_args('set_zfs_file_attributes')
class FilesystemSetZfsAttributesArgs(BaseModel):
    path: NonEmptyString
    """Path to the file to set ZFS attributes on."""
    zfs_file_attributes: ZFSFileAttrsData
    """ZFS file attributes to set."""


class FilesystemSetZfsAttributesResult(BaseModel):
    result: ZFSFileAttrsData
    """The updated ZFS file attributes."""


class FilesystemGetZfsAttributesArgs(BaseModel):
    path: NonEmptyString
    """Path to the file to get ZFS attributes for."""


class FilesystemGetZfsAttributesResult(BaseModel):
    result: ZFSFileAttrsData
    """The current ZFS file attributes."""


class FilesystemGetArgs(BaseModel):
    path: NonEmptyString
    """Path of the file to read."""


class FilesystemGetResult(BaseModel):
    result: None
    """Returns `null` when the file is successfully read."""


class FilesystemPutOptions(BaseModel):
    append: bool = False
    """Whether to append to the file instead of overwriting."""
    mode: int | None = None
    """Unix permissions to set on the file or `null` to use default."""


class FilesystemPutArgs(BaseModel):
    path: NonEmptyString
    """Path where the file should be written."""
    options: FilesystemPutOptions = FilesystemPutOptions()
    """Options controlling file writing behavior."""


class FilesystemPutResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the file is successfully written."""


class FileFollowTailEventSourceArgs(BaseModel):
    path: str
    """Path to the file to follow/tail."""


@single_argument_result
class FileFollowTailEventSourceEvent(BaseModel):
    data: str
    """New data appended to the file being followed."""
