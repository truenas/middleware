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
    traverse: bool = False
    """If set do not limit to single dataset / filesystem."""


class FilesystemChownOptions(FilesystemRecursionOptions):
    pass


class FilesystemSetpermOptions(FilesystemRecursionOptions):
    stripacl: bool = False


class FilesystemPermChownBase(BaseModel):
    path: NonEmptyString
    uid: AceWhoId | None = None
    user: NonEmptyString | None = None
    gid: AceWhoId | None = None
    group: NonEmptyString | None = None


@single_argument_args('filesystem_chown')
class FilesystemChownArgs(FilesystemPermChownBase):
    options: FilesystemChownOptions = Field(default=FilesystemChownOptions())

    @model_validator(mode='after')
    def user_group_present(self) -> Self:
        if all(field in UNSET_ENTRY for field in (self.uid, self.user, self.gid, self.group)):
            raise ValueError(
                'At least one of uid, gid, user, and group must be set in chown payload'
            )

        return self


class FilesystemChownResult(BaseModel):
    result: Literal[None]


@single_argument_args('filesystem_setperm')
class FilesystemSetpermArgs(FilesystemPermChownBase):
    mode: UnixPerm | None = None
    options: FilesystemSetpermOptions = Field(default=FilesystemSetpermOptions())

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
    result: Literal[None]


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
    """ Canonical path of the entry, eliminating any symbolic links"""
    type: FileType
    size: int
    """ Size in bytes of a plain file. This corresonds with stx_size. """
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
    query_filters: QueryFilters = []
    query_options: QueryOptions = QueryOptions()


FilesystemListdirResult = query_result(FilesystemDirEntry, "FilesystemListdirResult")


class FilesystemMkdirOptions(BaseModel):
    mode: UnixPerm = '755'
    raise_chmod_error: bool = True


@single_argument_args('filesystem_mkdir')
class FilesystemMkdirArgs(BaseModel):
    path: NonEmptyString
    options: FilesystemMkdirOptions = Field(default=FilesystemMkdirOptions())


class FilesystemMkdirResult(BaseModel):
    result: FilesystemDirEntry


class FilesystemStatData(BaseModel):
    realpath: NonEmptyString
    """ Canonical path of the entry, eliminating any symbolic links"""
    type: FileType
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


class FilesystemStatResult(BaseModel):
    result: FilesystemStatData


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
    free_blocks_str: NonEmptyString
    avail_blocks_str: NonEmptyString
    files: int
    """ Number of inodes in use as reported by statvfs. """
    free_files: int
    """ Number of free inodes as reported by statvfs. """
    name_max: int
    """ Maximum filename length as reported by statvfs. """
    total_bytes: int
    free_bytes: int
    avail_bytes: int
    total_bytes_str: NonEmptyString
    free_bytes_str: NonEmptyString
    avail_bytes_str: NonEmptyString


class FilesystemStatfsArgs(BaseModel):
    path: NonEmptyString


class FilesystemStatfsResult(BaseModel):
    result: FilesystemStatfsData


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
    zfs_file_attributes: ZFSFileAttrsData


class FilesystemSetZfsAttributesResult(BaseModel):
    result: ZFSFileAttrsData


class FilesystemGetZfsAttributesArgs(BaseModel):
    path: NonEmptyString


class FilesystemGetZfsAttributesResult(BaseModel):
    result: ZFSFileAttrsData


class FilesystemGetArgs(BaseModel):
    path: NonEmptyString


class FilesystemGetResult(BaseModel):
    result: Literal[None]


class FilesystemPutOptions(BaseModel):
    append: bool = False
    mode: int | None = None


class FilesystemPutArgs(BaseModel):
    path: NonEmptyString
    options: FilesystemPutOptions = FilesystemPutOptions()


class FilesystemPutResult(BaseModel):
    result: Literal[True]


class FileFollowTailEventSourceArgs(BaseModel):
    path: str


@single_argument_result
class FileFollowTailEventSourceEvent(BaseModel):
    data: str
