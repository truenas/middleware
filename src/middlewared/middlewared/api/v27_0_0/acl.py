from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    LocalUsername,
    NonEmptyString,
    RemoteUsername,
    excluded_field,
    single_argument_args,
)
from middlewared.utils.filesystem.acl import (
    ACL_UNDEFINED_ID,
    NFS4_SPECIAL_ENTRIES,
    POSIX_SPECIAL_ENTRIES,
    FS_ACL_Type,
    NFS4ACE_FlagSimple,
    NFS4ACE_MaskSimple,
    NFS4ACE_Tag,
    NFS4ACE_Type,
    POSIXACE_Tag,
)

from .common import QueryFilters, QueryOptions

__all__ = [
    'ACLTemplateEntry',
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
    READ_DATA: bool = Field(default=False, description="Permission to read file data or list directory contents.")
    WRITE_DATA: bool = Field(default=False, description="Permission to write file data or create files in directory.")
    APPEND_DATA: bool = Field(default=False, description="Permission to append data to files or create subdirectories.")
    READ_NAMED_ATTRS: bool = Field(
        default=False,
        description="Permission to read named attributes (extended attributes).",
    )
    WRITE_NAMED_ATTRS: bool = Field(
        default=False,
        description="Permission to write named attributes (extended attributes).",
    )
    EXECUTE: bool = Field(default=False, description="Permission to execute files or traverse directories.")
    DELETE: bool = Field(default=False, description="Permission to delete the file or directory.")
    DELETE_CHILD: bool = Field(default=False, description="Permission to delete child files within a directory.")
    READ_ATTRIBUTES: bool = Field(
        default=False,
        description="Permission to read basic file attributes (size, timestamps, etc.).",
    )
    WRITE_ATTRIBUTES: bool = Field(default=False, description="Permission to write basic file attributes.")
    READ_ACL: bool = Field(default=False, description="Permission to read the Access Control List.")
    WRITE_ACL: bool = Field(default=False, description="Permission to modify the Access Control List.")
    WRITE_OWNER: bool = Field(default=False, description="Permission to change the file owner.")
    SYNCHRONIZE: bool = Field(
        default=False,
        description="Permission to use the file/directory as a synchronization primitive.",
    )


class NFS4ACE_BasicPerms(BaseModel):
    BASIC: NFS4ACE_BasicPermset = Field(
        description=(
            "Basic permission level for NFS4 ACE.\n"
            "\n"
            "* `FULL_CONTROL`: Full read, write, execute, and administrative permissions\n"
            "* `MODIFY`: Read, write, and execute permissions\n"
            "* `READ`: Read-only permissions\n"
            "* `TRAVERSE`: Execute/traverse permissions only"
        ),
    )


class NFS4ACE_AdvancedFlags(BaseModel):
    FILE_INHERIT: bool = Field(default=False, description="Apply this ACE to files within directories.")
    DIRECTORY_INHERIT: bool = Field(default=False, description="Apply this ACE to subdirectories within directories.")
    NO_PROPAGATE_INHERIT: bool = Field(
        default=False,
        description="Do not propagate inheritance beyond immediate children.",
    )
    INHERIT_ONLY: bool = Field(default=False, description="This ACE only affects inheritance, not the object itself.")
    INHERITED: bool = Field(default=False, description="This ACE was inherited from a parent directory.")

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
    BASIC: NFS4ACE_BasicFlagset = Field(
        description=(
            "Basic inheritance behavior for NFS4 ACE.\n"
            "\n"
            "* `INHERIT`: Apply to child files and directories\n"
            "* `NOINHERIT`: Do not apply to child objects"
        ),
    )


class NFS4ACE(BaseModel):
    tag: NFS4ACE_Tags = Field(
        description=(
            "Subject type for this ACE.\n"
            "\n"
            "* `owner@`: File/directory owner\n"
            "* `group@`: File/directory primary group\n"
            "* `everyone@`: All users\n"
            "* `USER`: Specific user account\n"
            "* `GROUP`: Specific group"
        ),
    )
    type: NFS4ACE_EntryTypes = Field(
        description=(
            "Access control type.\n"
            "\n"
            "* `ALLOW`: Grant the specified permissions\n"
            "* `DENY`: Explicitly deny the specified permissions"
        ),
    )
    perms: NFS4ACE_AdvancedPerms | NFS4ACE_BasicPerms = Field(description="Permissions granted or denied by this ACE.")
    flags: NFS4ACE_AdvancedFlags | NFS4ACE_BasicFlags = Field(
        description="Inheritance and other behavioral flags for this ACE.",
    )
    id: AceWhoId | None = Field(
        default=None,
        description="UID or GID when `tag` is \"USER\" or \"GROUP\". `null` for special entries.",
    )
    who: LocalUsername | RemoteUsername | None = Field(
        default=None,
        description="Username or group name when `tag` is \"USER\" or \"GROUP\". `null` for special entries.",
    )

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
    autoinherit: bool = Field(
        default=False,
        description="Whether inheritance is automatically applied from parent directories.",
    )
    protected: bool = Field(default=False, description="Whether the ACL is protected from inheritance modifications.")
    defaulted: bool = Field(
        default=False,
        description="Whether this ACL was created by default rules rather than explicit configuration.",
    )


POSIXACE_Tags = Literal[
    POSIXACE_Tag.USER_OBJ,
    POSIXACE_Tag.GROUP_OBJ,
    POSIXACE_Tag.OTHER,
    POSIXACE_Tag.MASK,
    POSIXACE_Tag.USER,
    POSIXACE_Tag.GROUP
]


class POSIXACE_Perms(BaseModel):
    READ: bool = Field(description="Permission to read file contents or list directory contents.")
    WRITE: bool = Field(description="Permission to write file contents or create/delete files in directory.")
    EXECUTE: bool = Field(description="Permission to execute files or traverse directories.")


class POSIXACE(BaseModel):
    tag: POSIXACE_Tags = Field(
        description=(
            "Subject type for this POSIX ACE.\n"
            "\n"
            "* `USER_OBJ`: File/directory owner\n"
            "* `GROUP_OBJ`: File/directory primary group\n"
            "* `OTHER`: All other users\n"
            "* `MASK`: Maximum permissions for named users and groups\n"
            "* `USER`: Specific user account\n"
            "* `GROUP`: Specific group"
        ),
    )
    perms: POSIXACE_Perms = Field(description="Read, write, and execute permissions for this ACE.")
    default: bool = Field(description="Whether this is a default ACE that applies to newly created child objects.")
    id: AceWhoId | None = Field(
        default=None,
        description="Numeric user or group ID when tag is `USER` or `GROUP`. `null` for object entries.",
    )
    who: LocalUsername | RemoteUsername | None = Field(
        default=None,
        description="Username or group name when tag is `USER` or `GROUP`. `null` for object entries.",
    )

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
    uid: AceWhoId | None = Field(
        description="Numeric user ID for file/directory ownership or `null` to preserve existing.",
    )
    gid: AceWhoId | None = Field(
        description="Numeric group ID for file/directory ownership or `null` to preserve existing.",
    )


class NFS4ACL(AclBaseInfo):
    acltype: Literal[FS_ACL_Type.NFS4] = Field(description="ACL type identifier for NFS4 access control lists.")
    acl: list[NFS4ACE] = Field(description="Array of NFS4 Access Control Entries defining permissions.")
    aclflags: NFS4ACL_Flags = Field(description="NFS4 ACL behavioral flags for inheritance and protection.")
    trivial: bool = Field(description="Whether this ACL is a simple/trivial ACL equivalent to POSIX permissions.")


class POSIXACL(AclBaseInfo):
    acltype: Literal[FS_ACL_Type.POSIX1E] = Field(description="ACL type identifier for POSIX.1e access control lists.")
    acl: list[POSIXACE] = Field(description="Array of POSIX Access Control Entries defining permissions.")
    trivial: bool = Field(
        description="Whether this ACL is a simple/trivial ACL equivalent to standard POSIX permissions.",
    )


class DISABLED_ACL(AclBaseInfo):
    # ACL response paths with ACL entirely disabled
    acltype: Literal[FS_ACL_Type.DISABLED] = Field(
        description="ACL type identifier indicating access control lists are disabled.",
    )
    acl: None = Field(description="Always `null` when ACLs are disabled on the filesystem.")
    trivial: Literal[True] = Field(
        description="Always `true` when ACLs are disabled - only basic POSIX permissions apply.",
    )


class FilesystemGetaclArgs(BaseModel):
    path: NonEmptyString = Field(description="Absolute filesystem path to get ACL information for.")
    simplified: bool = Field(
        default=True,
        description="Whether to return simplified/basic permission sets instead of advanced permissions.",
    )
    resolve_ids: bool = Field(
        default=False,
        description="Whether to resolve numeric user/group IDs to names in the response.",
    )


class AclBaseResult(BaseModel):
    path: NonEmptyString = Field(description="Absolute filesystem path this ACL information applies to.")
    user: NonEmptyString | None = Field(description="Username of the file/directory owner or `null` if unresolved.")
    group: NonEmptyString | None = Field(description="Group name of the file/directory group or `null` if unresolved.")


class NFS4ACLResult(NFS4ACL, AclBaseResult):
    pass


class POSIXACLResult(POSIXACL, AclBaseResult):
    pass


class DISABLED_ACLResult(DISABLED_ACL, AclBaseResult):
    pass


class FilesystemGetaclResult(BaseModel):
    result: NFS4ACLResult | POSIXACLResult | DISABLED_ACLResult = Field(
        description="ACL information for the requested filesystem path.",
    )


class FilesystemSetAclOptions(BaseModel):
    stripacl: bool = Field(
        default=False,
        description="Whether to remove the ACL entirely and revert to basic POSIX permissions.",
    )
    recursive: bool = Field(
        default=False,
        description="Whether to apply ACL changes recursively to all child files and directories.",
    )
    traverse: bool = Field(
        default=False,
        description="Whether to traverse filesystem boundaries during recursive operations.",
    )
    validate_effective_acl: bool = Field(
        default=True,
        description=(
            "Whether to validate that the users/groups granted access in the ACL can actually access the path or parent"
            " path."
        ),
    )


@single_argument_args('filesystem_acl')
class FilesystemSetaclArgs(BaseModel):
    path: NonEmptyString = Field(description="Absolute filesystem path to set ACL on.")
    dacl: list[NFS4ACE] | list[POSIXACE] = Field(
        description="Array of Access Control Entries to apply to the filesystem object.",
    )
    options: FilesystemSetAclOptions = Field(
        default=FilesystemSetAclOptions(),
        description="Configuration options for ACL setting behavior.",
    )
    nfs41_flags: NFS4ACL_Flags = Field(
        default=NFS4ACL_Flags(),
        description="NFS4 ACL flags for inheritance and protection behavior.",
    )
    uid: AceWhoId | None = Field(
        default=ACL_UNDEFINED_ID,
        description="Numeric user ID to set as owner or `null` to preserve existing.",
    )
    user: str | None = Field(default=None, description="Username to set as owner or `null` to preserve existing.")
    gid: AceWhoId | None = Field(
        default=ACL_UNDEFINED_ID,
        description="Numeric group ID to set as group or `null` to preserve existing.",
    )
    group: str | None = Field(default=None, description="Group name to set as group or `null` to preserve existing.")

    # acltype is explicitly added to preserve compatibility with older setacl API
    acltype: Literal[FS_ACL_Type.NFS4, FS_ACL_Type.POSIX1E] | None = Field(
        default=None,
        description="ACL type to use or `null` to auto-detect from filesystem capabilities.",
    )

    @model_validator(mode='after')
    def check_setacl_valid(self) -> Self:
        if len(self.dacl) != 0 and self.options.stripacl:
            raise ValueError(
                'Simultaneosuly setting and removing ACL from path is not supported'
            )

        return self


class FilesystemSetaclResult(FilesystemGetaclResult):
    pass


class ACLTemplateEntry(BaseModel):
    id: int = Field(description="Unique identifier for the ACL template.")
    builtin: bool = Field(description="Whether this is a built-in system template or user-created.")
    name: str = Field(description="Human-readable name for the ACL template.")
    acltype: Literal[FS_ACL_Type.NFS4, FS_ACL_Type.POSIX1E] = Field(description="ACL type this template provides.")
    acl: list[NFS4ACE] | list[POSIXACE] = Field(description="Array of Access Control Entries defined by this template.")
    comment: str = Field(default='', description="Optional descriptive comment about the template's purpose.")


class AclTemplateCreate(ACLTemplateEntry):
    id: Excluded = excluded_field()
    builtin: Excluded = excluded_field()


class ACLTemplateCreateArgs(BaseModel):
    acltemplate_create: AclTemplateCreate = Field(description="ACL template configuration data for the new template.")


class ACLTemplateCreateResult(BaseModel):
    result: ACLTemplateEntry = Field(description="The created ACL template configuration.")


class AclTemplateUpdate(AclTemplateCreate, metaclass=ForUpdateMetaclass):
    pass


class ACLTemplateUpdateArgs(BaseModel):
    id: int = Field(description="ID of the ACL template to update.")
    acltemplate_update: AclTemplateUpdate = Field(description="Updated ACL template configuration data.")


class ACLTemplateUpdateResult(BaseModel):
    result: ACLTemplateEntry = Field(description="The updated ACL template configuration.")


class ACLTemplateDeleteArgs(BaseModel):
    id: int = Field(description="ID of the ACL template to delete.")


class ACLTemplateDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the ACL template is successfully deleted.")


class AclTemplateFormatOptions(BaseModel):
    ensure_builtins: bool = Field(
        default=False,
        description="Whether to ensure built-in templates are included in the response.",
    )
    resolve_names: bool = Field(
        default=False,
        description="Whether to resolve numeric user/group IDs to names in ACL entries.",
    )


class ACLTemplateByPathQueryOptions(QueryOptions):
    extra: Excluded = excluded_field()
    select: Excluded = excluded_field()
    count: Excluded = excluded_field()
    get: Excluded = excluded_field()


@single_argument_args('filesystem_acl')
class ACLTemplateByPathArgs(BaseModel):
    path: str = Field(
        default="",
        description="Filesystem path to filter templates by compatibility or empty string for all.",
    )
    query_filters: QueryFilters = Field(
        alias='query-filters',
        default=[],
        description="Query filters to apply when selecting templates.",
    )
    query_options: ACLTemplateByPathQueryOptions = Field(
        alias='query-options',
        default=ACLTemplateByPathQueryOptions(),
        description="Query options for pagination and ordering of results.",
    )
    format_options: AclTemplateFormatOptions = Field(
        alias='format-options',
        default=AclTemplateFormatOptions(),
        description="Formatting options for how template data is returned.",
    )


class ACLTemplateByPathResult(BaseModel):
    result: list[ACLTemplateEntry] = Field(description="Array of ACL templates matching the query criteria.")
