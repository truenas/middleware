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
from pydantic import Field, model_validator
from typing import Annotated, Literal, Optional, Self
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
    NFS4_SPECIAL_ENTRIES,
    POSIX_SPECIAL_ENTRIES,
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
    READ_DATA: bool
    WRITE_DATA: bool
    APPEND_DATA: bool
    READ_NAMED_ATTRS: bool
    EXECUTE: bool
    DELETE: bool
    DELETE_CHILD: bool
    READ_ATTRIBUTES: bool
    WRITE_ATTRIBUTES: bool
    READ_ACL: bool
    WRITE_ACL: bool
    SYNCHRONIZE: bool


class NFS4ACE_BasicPerms(BaseModel):
    BASIC: NFS4ACE_BasicPermset


class NFS4ACE_AdvancedFlags(BaseModel):
    FILE_INHERIT: bool
    DIRECTORY_INHERIT: bool
    NO_PROPAGATE_INHERIT: bool
    INHERIT_ONLY: bool
    INHERITED: bool

    @model_validator(mode='after')
    def check_inherit_only(self) -> Self:
        if not self.INHERIT_ONLY:
            return self

        if not self.FILE_INHERIT and not self.DIRECTORY_INHERIT:
            raise ValueError(
                'At least one of FILE_INHERIT or DIRECTORY_INHERIT must '
                'be set if INHERIT_ONLY is present in the ACE flags'
            )

        return self


class NFS4ACE_BasicFlags(BaseModel):
    BASIC: NFS4ACE_BasicFlagset


class NFS4ACE(BaseModel):
    tag: NFS4ACE_Tags
    id: AceWhoId | None
    type: NFS4ACE_EntryTypes
    perms: NFS4ACE_AdvancedPerms | NFS4ACE_BasicPerms
    flags: NFS4ACE_AdvancedFlags | NFS4ACE_BasicFlags
    who: LocalUsername | RemoteUsername | None = None

    @model_validator(mode='after')
    def check_ace_valid(self) -> Self:
        if self.tag in NFS4_SPECIAL_ENTRIES:
            if self.id not in (-1, None):
                raise ValueError(
                    f'{self.id}: id may not be specified for the following ACL entry '
                    f'tags: {", ".join([tag for tag in NFS4_SPECIAL_ENTRIES])}'
                )
        else:
            if not self.who and self.id in (None, -1):
                raise ValueError(
                    'Numeric ID "id" or account name "who" must be specified'
                )

        return self


class NFS4ACL_Flags(BaseModel):
    autoinherit: bool = False
    protected: bool = False
    defaulted: bool = False


POSIXACE_Tags = Literal[
    POSIXACE_Tag.USER_OBJ,
    POSIXACE_Tag.GROUP_OBJ,
    POSIXACE_Tag.OTHER,
    POSIXACE_Tag.MASK,
    POSIXACE_Tag.USER,
    POSIXACE_Tag.GROUP
]


class POSIXACE_Perms(BaseModel):
    READ: bool
    WRITE: bool
    EXECUTE: bool


class POSIXACE(BaseModel):
    tag: POSIXACE_Tags
    id: AceWhoId | None
    perms: POSIXACE_Perms
    default: bool
    who: LocalUsername | RemoteUsername | None = None

    @model_validator(mode='after')
    def check_ace_valid(self) -> Self:
        if self.tag in POSIX_SPECIAL_ENTRIES:
            if self.id not in (-1, None):
                raise ValueError(
                    f'{self.id}: id may not be specified for the following ACL entry '
                    f'tags: {", ".join([tag for tag in POSIX_SPECIAL_ENTRIES])}'
                )
        else:
            if not ace_in.who and ace_in.id in (None, -1):
                raise ValueError(
                    'Numeric ID "id" or account name "who" must be specified'
                )

        return self


class AclBaseFileInfo(BaseModel):
    uid: AceWhoId | None
    gid: AceWhoId | None
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
class FilesystemSetaclArgs(BaseModel):
    path: NonEmptyString
    dacl: list[NFS4ACE] | list[POSIXACE]
    options: FilesystemSetaclOptions = Field(default=FilesystemSetaclOptions())
    nfs41_flags: NFS4ACL_Flags = Field(default=NFS4ACL_Flags())
    uid: AceWhoId | None = ACL_UNDEFINED_ID
    gid: AceWhoId | None = ACL_UNDEFINED_ID

    @model_validator(mode='after')
    def check_setacl_valid(self) -> Self:
        if len(self.dacl) != 0 and self.options.stripacl:
            raise ValueError(
                'Simultaneosuly setting and removing ACL from path is not supported' 
            )

        return self


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
    path: str = ""
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
