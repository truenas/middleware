from annotated_types import Ge, Le
from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    LocalUsername,
    NonEmptyString,
    RemoteUsername,
    single_argument_args,
)
from pydantic import Field
from typing import Annotated, Literal, Optional
from middlewared.utils.filesystem.acl import (
    FS_ACL_Type,
    NFS4ACE_Tag,
    NFS4ACE_Type,
    NFS4ACE_Mask,
    NFS4ACE_MaskSimple,
    NFS4ACE_Flag,
    NFS4ACE_FlagSimple,
    NFS4ACL_Flag,
    POSIXACE_Tag,
    POSIXACE_Mask,
)
from .common import QueryFilters, QueryOptions

__all__ = [
    'AclTemplateEntry',
    'AclTemplateByPathArgs', 'AclTemplateByPathResult',
    'AclTemplateCreateArgs', 'AclTemplateCreateResult',
    'AclTemplateUpdateArgs', 'AclTemplateUpdateResult',
    'AclTemplateDeleteArgs', 'AclTemplateDeleteResult',
    'FilesystemAddToAclArgs', 'FilesystemAddToAclResult',
    'FilesystemGetaclArgs', 'FilesystemGetaclResult',
    'FilesystemSetaclArgs', 'FilesystemSetaclResult',
    'FilesystemGetInheritedAclArgs', 'FilesystemGetInheritedAclResult'
]

ACL_UNDEFINED_ID = -1
ACL_MAX_ID = 2 ** 32 // 2 - 1

AceWhoId = Annotated[int, Ge(ACL_UNDEFINED_ID), Le(ACL_MAX_ID)]

NFS4ACE_BasicPermset = Literal[
    NFS4ACE_MaskSimple.FULL_CONTROL,
    NFS4ACE_MaskSimple.MODIFY,
    NFS4ACE_MaskSimple.READ,
    NFS4ACE_MaskSimple.TRAVERSE
]

NFS4ACE_BasicFlagset = Literal[
    NFS4ACE_FlagSimple.INHERIT,
    NFS4ACE_FlagSimple.NOINHERIT,
]

NFS4ACE_Tags = Literal[
    NFS4ACE_Tag.SPECIAL_OWNER,
    NFS4ACE_Tag.SPECIAL_GROUP,
    NFS4ACE_Tag.SPECIAL_EVERYONE,
    NFS4ACE_Tag.USER,
    NFS4ACE_Tag.GROUP
]

NFS4ACE_EntryTypes = Literal[
    NFS4ACE_Type.ALLOW,
    NFS4ACE_Type.DENY
]


class NFS4ACE_AdvancedPerms(BaseModel):
    NFS4ACE_Mask.READ_DATA: bool
    NFS4ACE_Mask.WRITE_DATA: bool
    NFS4ACE_Mask.APPEND_DATA: bool
    NFS4ACE_Mask.READ_NAMED_ATTRS: bool
    NFS4ACE_Mask.EXECUTE: bool
    NFS4ACE_Mask.DELETE: bool
    NFS4ACE_Mask.DELETE_CHILD: bool
    NFS4ACE_Mask.READ_ATTRIBUTES: bool
    NFS4ACE_Mask.WRITE_ATTRIBUTES: bool
    NFS4ACE_Mask.READ_ACL: bool
    NFS4ACE_Mask.WRITE_ACL: bool
    NFS4ACE_Mask.SYNCHRONIZE: bool


class NFS4ACE_BasicPerms(BaseModel):
    BASIC: NFS4ACE_BasicPermset


class NFS4ACE_AdvancedFlags(BaseModel):
    NFS4ACE_Flag.FILE_INHERIT: bool
    NFS4ACE_Flag.DIRECTORY_INHERIT: bool
    NFS4ACE_Flag.NO_PROPAGATE_INHERIT: bool
    NFS4ACE_Flag.INHERIT_ONLY: bool
    NFS4ACE_Flag.INHERITED: bool


class NFS4ACE_BasicFlags(BaseModel):
    BASIC: NFS4ACE_BasicFlagset


class NFS4ACE(BaseModel):
    tag: NFS4ACE_Tags
    id: AceWhoId
    type: NFS4ACE_EntryTypes
    perms: NFS4ACE_AdvancedPerms | NFS4ACE_BasicPerms
    flags: NFS4ACE_AdvancedFlags | NFS4ACE_BasicFlags
    who: Optional[LocalUsername | RemoteUsername | None]


class NFS4ACL_Flags(BaseModel):
    NFS4ACL_Flag.AUTOINHERIT: bool
    NFS4ACL_Flag.PROTECTED: bool
    NFS4ACL_Flag.DEFAULT: bool


POSIXACE_Tags = Literal[
    POSIXACE_Tag.USER_OBJ,
    POSIXACE_Tag.GROUP_OBJ,
    POSIXACE_Tag.OTHER,
    POSIXACE_Tag.MASK,
    POSIXACE_Tag.USER,
    POSIXACE_Tag.GROUP
]


class POSIXACE_Perms(BaseModel):
    POSIXACE_Mask.READ: bool
    POSIXACE_Mask.WRITE: bool
    POSIXACE_Mask.EXECUTE: bool


class POSIXACE(BaseModel):
    tag: POSIXACE_Tags
    id: AceWhoId
    perms: POSIXACE_Perms
    default: bool
    who: Optional[LocalUsername | RemoteUsername | None]


class AclBaseFileInfo(BaseModel):
    uid: int
    gid: int
    path: str


class NFS4ACL(AclBaseFileInfo):
    acltype: Literal[FS_ACL_Type.NFS4]
    acl: list[NFS4ACE]
    aclflags: NFS4ACL_Flags
    trivial: bool


class POSIXACL(AclBaseFileInfo):
    acltype: Literal[FS_ACL_Type.POSIX1E]
    acl: list[POSIXACE]
    trivial: bool


class DISABLED_ACL(AclBaseFileInfo):
    # ACL response paths with ACL entirely disabled
    acltype: Literal[FS_ACL_Type.DISABLED]
    acl: Literal[[]]
    trivial: Literal[True]


class FilesystemGetaclArgs(BaseModel):
    path: NonEmptyString
    simplified: bool = True
    resolve_ids: bool = False


class FilesystemGetaclResult(BaseModel):
    result: NFS4ACL | POSIXACL | DISABLED_ACL


class FilesystemSetaclOptions(BaseModel):
    stripacl: bool = False
    recursive: bool = False
    traverse: bool = False
    canonicalize: bool = True
    validate_effective_acl: bool = True


@single_argument_args('filesystem_acl')
class FilesystemSetaclArgs(AclBaseFileInfo):
    dacl: list[NFS4ACE] | list[POSIXACE]
    nfs41_flags: Optional[NFS4ACL_Flags]
    acltype: Literal[FS_ACL_Type.NFS4, FS_ACL_Type.POSIX1E]
    options: FilesystemSetaclOptions = Field(default=FilesystemSetaclOptions())


class FilesystemSetaclResult(FilesystemGetaclResult):
    pass


class AclTemplateEntry(BaseModel):
    id: int
    builtin: bool
    name: str
    acltype: Literal[FS_ACL_Type.NFS4, FS_ACL_Type.POSIX1E]
    acl: list[NFS4ACE] | list[POSIXACE]
    comment: str


class AclTemplateCreate(AclTemplateEntry):
    id: Excluded = excluded_field()
    builtin: Excluded = excluded_field()


class AclTemplateCreateArgs(AclTemplateEntry):
    acltemplate_create: AclTemplateCreate


class AclTemplateCreateResult(BaseModel):
    result: AclTemplateEntry


class AclTemplateUpdate(AclTemplateCreate, metaclass=ForUpdateMetaclass):
    pass


class AclTemplateUpdateArgs(BaseModel):
    id: int
    acltemplate_update: AclTemplateUpdate


class AclTemplateUpdateResult(BaseModel):
    result: AclTemplateEntry


class AclTemplateDeleteArgs(BaseModel):
    id: int


class AclTemplateDeleteResult(BaseModel):
    result: int


class AclTemplateFormatOptions(BaseModel):
    canonicalize: bool = False
    ensure_builtins: bool = False
    resolve_names: bool = False


@single_argument_args('filesystem_acl')
class AclTemplateByPathArgs(BaseModel):
    path: NonEmptyString
    query_filters: QueryFilters = Field(alias='query-filters', default=[])
    query_options: QueryOptions = Field(alias='query-options', default=QueryOptions())
    format_options: AclTemplateFormatOptions = Field(alias='format-options', default=AclTemplateFormatOptions())


class AclTemplateByPathResult(BaseModel):
    result: list[AclTemplateEntry]


class SimplifiedAclEntry(BaseModel):
    id_type: Literal[NFS4ACE_Tag.USER, NFS4ACE_Tag.GROUP]
    id: int
    access: Literal[
        NFS4ACE_MaskSimple.READ,
        NFS4ACE_MaskSimple.MODIFY,
        NFS4ACE_MaskSimple.FULL_CONTROL
    ]


class FilesystemAddToAclOptions(BaseModel):
    force: bool = False


@single_argument_args('add_to_acl')
class FilesystemAddToAclArgs(BaseModel):
    path: NonEmptyString
    entries: list[SimplifiedAclEntry]
    options: FilesystemAddToAclOptions = Field(default=FilesystemAddToAclOptions())


class FilesystemAddToAclResult(BaseModel):
    result: bool


class FSGetInheritedAclOptions(BaseModel):
    directory: bool = True


@single_argument_args('calculate_inherited_acl')
class FilesystemGetInheritedAclArgs(BaseModel):
    path: NonEmptyString
    options: FSGetInheritedAclOptions = Field(default=FSGetInheritedAclOptions())


class FilesystemGetInheritedAclResult(BaseModel):
    result: list[NFS4ACE] | list[POSIXACE]
