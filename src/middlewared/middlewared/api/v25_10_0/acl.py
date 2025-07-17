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
from typing import Annotated, Literal, Self
from middlewared.utils.filesystem.acl import (
    ACL_UNDEFINED_ID,
    FS_ACL_Type,
    NFS4ACE_Tag,
    NFS4ACE_Type,
    NFS4ACE_MaskSimple,
    NFS4ACE_FlagSimple,
    POSIXACE_Tag,
    NFS4_SPECIAL_ENTRIES,
    POSIX_SPECIAL_ENTRIES,
)
from .common import QueryFilters, QueryOptions

__all__ = [
    'AclTemplateEntry',
    'ACLTemplateByPathArgs', 'ACLTemplateByPathResult',
    'ACLTemplateCreateArgs', 'ACLTemplateCreateResult',
    'ACLTemplateUpdateArgs', 'ACLTemplateUpdateResult',
    'ACLTemplateDeleteArgs', 'ACLTemplateDeleteResult',
    'FilesystemGetaclArgs', 'FilesystemGetaclResult',
    'FilesystemSetaclArgs', 'FilesystemSetaclResult',
    'NFS4ACE', 'POSIXACE',
]

ACL_MAX_ID = 2 ** 32 // 2 - 1

AceWhoId = Annotated[int, Field(ge=ACL_UNDEFINED_ID, le=ACL_MAX_ID)]

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
    READ_DATA: bool = False
    WRITE_DATA: bool = False
    APPEND_DATA: bool = False
    READ_NAMED_ATTRS: bool = False
    WRITE_NAMED_ATTRS: bool = False
    EXECUTE: bool = False
    DELETE: bool = False
    DELETE_CHILD: bool = False
    READ_ATTRIBUTES: bool = False
    WRITE_ATTRIBUTES: bool = False
    READ_ACL: bool = False
    WRITE_ACL: bool = False
    WRITE_OWNER: bool = False
    SYNCHRONIZE: bool = False


class NFS4ACE_BasicPerms(BaseModel):
    BASIC: NFS4ACE_BasicPermset


class NFS4ACE_AdvancedFlags(BaseModel):
    FILE_INHERIT: bool = False
    DIRECTORY_INHERIT: bool = False
    NO_PROPAGATE_INHERIT: bool = False
    INHERIT_ONLY: bool = False
    INHERITED: bool = False

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
    type: NFS4ACE_EntryTypes
    perms: NFS4ACE_AdvancedPerms | NFS4ACE_BasicPerms
    flags: NFS4ACE_AdvancedFlags | NFS4ACE_BasicFlags
    id: AceWhoId | None = None
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
    perms: POSIXACE_Perms
    default: bool
    id: AceWhoId | None = None
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
            if not self.who and self.id in (None, -1):
                raise ValueError(
                    'Numeric ID "id" or account name "who" must be specified'
                )

        return self


class AclBaseInfo(BaseModel):
    uid: AceWhoId | None
    gid: AceWhoId | None


class NFS4ACL(AclBaseInfo):
    acltype: Literal[FS_ACL_Type.NFS4]
    acl: list[NFS4ACE]
    aclflags: NFS4ACL_Flags
    trivial: bool


class POSIXACL(AclBaseInfo):
    acltype: Literal[FS_ACL_Type.POSIX1E]
    acl: list[POSIXACE]
    trivial: bool


class DISABLED_ACL(AclBaseInfo):
    # ACL response paths with ACL entirely disabled
    acltype: Literal[FS_ACL_Type.DISABLED]
    acl: Literal[None]
    trivial: Literal[True]


class FilesystemGetaclArgs(BaseModel):
    path: NonEmptyString
    simplified: bool = True
    resolve_ids: bool = False


class AclBaseResult(BaseModel):
    path: NonEmptyString
    user: NonEmptyString | None
    group: NonEmptyString | None


class NFS4ACLResult(NFS4ACL, AclBaseResult):
    pass


class POSIXACLResult(POSIXACL, AclBaseResult):
    pass


class DISABLED_ACLResult(DISABLED_ACL, AclBaseResult):
    pass


class FilesystemGetaclResult(BaseModel):
    result: NFS4ACLResult | POSIXACLResult | DISABLED_ACLResult


class FilesystemSetAclOptions(BaseModel):
    stripacl: bool = False
    recursive: bool = False
    traverse: bool = False
    canonicalize: bool = True
    validate_effective_acl: bool = True


@single_argument_args('filesystem_acl')
class FilesystemSetaclArgs(BaseModel):
    path: NonEmptyString
    dacl: list[NFS4ACE] | list[POSIXACE]
    options: FilesystemSetAclOptions = Field(default=FilesystemSetAclOptions())
    nfs41_flags: NFS4ACL_Flags = Field(default=NFS4ACL_Flags())
    uid: AceWhoId | None = ACL_UNDEFINED_ID
    user: str | None = None
    gid: AceWhoId | None = ACL_UNDEFINED_ID
    group: str | None = None

    # acltype is explicitly added to preserve compatibility with older setacl API
    acltype: Literal[FS_ACL_Type.NFS4, FS_ACL_Type.POSIX1E] | None = None

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
    comment: str = ''


class AclTemplateCreate(AclTemplateEntry):
    id: Excluded = excluded_field()
    builtin: Excluded = excluded_field()


class ACLTemplateCreateArgs(BaseModel):
    acltemplate_create: AclTemplateCreate


class ACLTemplateCreateResult(BaseModel):
    result: AclTemplateEntry


class AclTemplateUpdate(AclTemplateCreate, metaclass=ForUpdateMetaclass):
    pass


class ACLTemplateUpdateArgs(BaseModel):
    id: int
    acltemplate_update: AclTemplateUpdate


class ACLTemplateUpdateResult(BaseModel):
    result: AclTemplateEntry


class ACLTemplateDeleteArgs(BaseModel):
    id: int


class ACLTemplateDeleteResult(BaseModel):
    result: Literal[True]


class AclTemplateFormatOptions(BaseModel):
    canonicalize: bool = False
    ensure_builtins: bool = False
    resolve_names: bool = False


class ACLTemplateByPath(BaseModel):
    path: str = ""
    query_filters: QueryFilters = Field(alias='query-filters', default=[])
    query_options: QueryOptions = Field(alias='query-options', default=QueryOptions())
    format_options: AclTemplateFormatOptions = Field(alias='format-options', default=AclTemplateFormatOptions())


class ACLTemplateByPathArgs(BaseModel):
    filesystem_acl: ACLTemplateByPath = ACLTemplateByPath()


class ACLTemplateByPathResult(BaseModel):
    result: list[AclTemplateEntry]
