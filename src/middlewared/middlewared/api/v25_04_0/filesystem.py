from middlewared.api.base import (
    BaseModel,
    NonEmptyString,
    UnixPerm,
    single_argument_args,
    query_result
)
from pydantic import Field, model_validator
from typing import Literal, Self
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
    'FilesystemSetPermArgs', 'FilesystemSetPermResult',
    'FilesystemListdirArgs', 'FilesystemListdirResult',
    'FilesystemMkdirArgs', 'FilesystemMkdirResult',
]


UNSET_ENTRY = frozenset([ACL_UNDEFINED_ID, None])


class FilesystemRecursionOptions(BaseModel):
    recursive: bool = False
    traverse: bool = False
    "If set do not limit to single dataset / filesystem."


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
class FilesystemSetPermArgs(FilesystemPermChownBase):
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


class FilesystemSetPermResult(BaseModel):
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


class FilesystemDirEntry(BaseModel):
    name: NonEmptyString
    """ Entry's base name. """
    path: NonEmptyString
    """ Entry's full path. """
    realpath: NonEmptyString
    """ Canonical path of the entry, eliminating any symbolic links"""
    type: Literal[
        StatxEtype.DIRECTORY,
        StatxEtype.FILE,
        StatxEtype.SYMLINK,
        StatxEtype.OTHER,
    ]
    size: int
    """ Size in bytes of a plain file. """
    allocation_size: int
    mode: int
    """ Entry's mode including file type information and file permission bits. """
    mount_id: int
    """ The mount ID of the mount containing the entry. This corresponds to the number in first
    field of /proc/self/mountinfo. """
    acl: bool
    """ Specifies whether ACL is present on the entry. If this is the case then file permission
    bits as reported in `mode` may not be representative of the actual permissions. """
    uid: int
    """ User ID of the entry's owner. """
    gid: int
    """ Group ID of the entry's owner. """
    is_mountpoint: bool
    """ Specifies whether the entry is also the mountpoint of a filesystem. """
    is_ctldir: bool
    """ Specifies whether the entry is located within the ZFS ctldir (for example a snapshot). """
    attributes: list[FILESYSTEM_STATX_ATTRS]
    """ Extra file attribute indicators for entry as returned by statx. """
    xattrs: list[NonEmptyString]
    """ List of xattr names of extended attributes on file. """
    zfs_attrs: list[FILESYSTEM_ZFS_ATTRS] | None
    """ List of extra ZFS-related file attribute indicators on file. Will be None type if filesystem is not ZFS. """


class FilesystemListdirArgs(BaseModel):
    path: NonEmptyString
    query_filters: QueryFilters = []
    query_options: QueryOptions = QueryOptions()


FilesystemListdirResult = query_result(FilesystemDirEntry)


class FilesystemMkdirOptions(BaseModel):
    mode: UnixPerm = '755'
    raise_chmod_error: bool = True


@single_argument_args('filesystem_mkdir')
class FilesystemMkdirArgs(BaseModel):
    path: NonEmptyString
    options: FilesystemMkdirOptions = Field(default=FilesystemMkdirOptions())


class FilesystemMkdirResult(BaseModel):
    result: FilesystemDirEntry
