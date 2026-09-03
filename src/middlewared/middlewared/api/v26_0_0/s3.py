from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, Secret

from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    NonEmptyString,
    LocalUsername,
    RemoteUsername,
    UniqueList,
)


__all__ = [
    "S3AccesskeyEntry",
    "S3AccesskeyCreate",
    "S3AccesskeyUpdate",
    "S3AccesskeyCreateArgs",
    "S3AccesskeyCreateResult",
    "S3AccesskeyUpdateArgs",
    "S3AccesskeyUpdateResult",
    "S3AccesskeyDeleteArgs",
    "S3AccesskeyDeleteResult",
    "S3AuditAction",
    "S3Grant",
    "S3GrantEntry",
    "S3Entry",
    "S3Update",
    "S3UpdateArgs",
    "S3UpdateResult",
    "S3BindipChoicesArgs",
    "S3BindipChoicesResult",
    "SharingS3Entry",
    "SharingS3Create",
    "SharingS3Update",
    "SharingS3CreateArgs",
    "SharingS3CreateResult",
    "SharingS3UpdateArgs",
    "SharingS3UpdateResult",
    "SharingS3DeleteArgs",
    "SharingS3DeleteResult",
    "SharingS3AuditChoicesArgs",
    "SharingS3AuditChoicesResult",
]

S3AuditAction = Literal[
    "GetObject",
    "PutObject",
    "DeleteObject",
    "GetObjectTagging",
    "PutObjectTagging",
    "DeleteObjectTagging",
    "ListBucket",
    "GetBucketLocation",
    "ListBucketMultipartUploads",
    "ListMultipartUploadParts",
    "AbortMultipartUpload",
    "PutObjectRetention",
    "PutObjectLegalHold",
    "ListAllMyBuckets",
]
"""The actions an audit mask may name, spelled exactly as the S3 service
reads them. The one middleware-side vocabulary; the service refuses its
whole config for an unknown name, so the live tests set every one."""

S3AuditMask = list[S3AuditAction] | Literal["ALL"]
S3AuditOverflow = Literal["DROP", "BACKPRESSURE"]
S3Access = Literal["READONLY", "WRITEONLY", "READWRITE", "DENY"]
S3PrincipalType = Literal["USER", "GROUP", "EVERYONE"]

S3AccessKeyId = Annotated[str, Field(pattern=r"^[A-Z0-9]{16,128}$")]
"""An S3 access key id. Uppercase alphanumerics only, so it is safe inside
the quoted section heading of the S3 service's credentials file."""

S3SecretKey = Annotated[str, Field(min_length=16, max_length=128, pattern=r"^[\x21-\x7E]+$")]
"""An S3 secret access key. Printable ASCII with no whitespace, so the
value survives the S3 service's whitespace-trimming config reader."""

S3AccesskeyStatus = Literal["ENABLED", "DISABLED", "EXPIRED", "USER_MISSING", "SECRET_LOST"]


class S3AccesskeyEntry(BaseModel):
    id: int = Field(description="Unique identifier for the access key.")
    name: NonEmptyString = Field(max_length=200, description="Human-readable name for the access key.")
    username: LocalUsername | RemoteUsername | None = Field(
        description="Account the access key belongs to, or `null` if that account no longer exists.",
    )
    user_identifier: int | str = Field(
        description=(
            "Stored account linkage. A numeric user ID for local accounts or a SID for directory services accounts."
        ),
    )
    local: bool = Field(
        description="Whether the access key belongs to a local user account rather than a directory services one.",
    )
    access_key: S3AccessKeyId = Field(description="The S3 access key id clients sign requests with.")
    secret: Secret[str | None] = Field(
        description=(
            "The S3 secret access key. Readable only by administrators holding `SHARING_S3_WRITE`; redacted for "
            "everyone else. `null` when the secret was lost to a configuration restore without the secret seed."
        ),
    )
    enabled: bool = Field(
        description="Whether the access key may be used. A disabled key is refused by the S3 service."
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Expiration timestamp for the access key or `null` for no expiration.",
    )
    created_at: datetime = Field(description="Timestamp when the access key was created.")
    status: S3AccesskeyStatus = Field(
        description=(
            "Effective state of the access key. Only `ENABLED` keys are usable. `DISABLED` was set by an "
            "administrator, `EXPIRED` passed its expiration, `USER_MISSING` belongs to a directory account that no "
            "longer resolves (a deleted local account takes its keys with it), and `SECRET_LOST` lost its secret to a "
            "configuration restore without the secret seed and "
            "must be rotated."
        ),
    )


class S3AccesskeyCreate(S3AccesskeyEntry):
    id: Excluded = excluded_field()
    username: LocalUsername | RemoteUsername = Field(description="Account the access key belongs to.")
    user_identifier: Excluded = excluded_field()
    local: Excluded = excluded_field()
    access_key: S3AccessKeyId | None = Field(
        default=None,
        description="Access key id for the new key. Generated when omitted.",
    )
    secret: Secret[S3SecretKey | None] = Field(
        default=None,
        description="Secret access key for the new key. Generated when omitted.",
    )
    enabled: bool = Field(default=True, description="Whether the access key may be used.")
    created_at: Excluded = excluded_field()
    status: Excluded = excluded_field()


class S3AccesskeyCreateArgs(BaseModel):
    data: S3AccesskeyCreate = Field(description="Configuration for the new access key.")


class S3AccesskeyCreateResult(BaseModel):
    result: S3AccesskeyEntry = Field(description="The created access key, including its secret.")


class S3AccesskeyUpdate(S3AccesskeyCreate, metaclass=ForUpdateMetaclass):
    username: Excluded = excluded_field()
    access_key: Excluded = excluded_field()
    secret: Excluded = excluded_field()
    rotate: bool = Field(
        default=False,
        description="Generate a new secret access key under the same access key id.",
    )


class S3AccesskeyUpdateArgs(BaseModel):
    id: int = Field(description="ID of the access key to update.")
    data: S3AccesskeyUpdate = Field(description="Access key changes to apply.")


class S3AccesskeyUpdateResult(BaseModel):
    result: S3AccesskeyEntry = Field(description="The updated access key, including its secret.")


class S3AccesskeyDeleteArgs(BaseModel):
    id: int = Field(description="ID of the access key to delete.")


class S3AccesskeyDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the access key is successfully deleted.")


class S3Grant(BaseModel):
    principal_type: S3PrincipalType = Field(
        description="Who the grant applies to. A user, a group, or everyone with a valid access key.",
    )
    xid: int | None = Field(
        default=None,
        description=(
            "The uid of the user or the gid of the group. Required for `USER` and `GROUP`, forbidden for `EVERYONE`."
        ),
    )
    access: S3Access = Field(
        description=(
            "What the grant allows. `READONLY`, `WRITEONLY` and `READWRITE` allow the matching operations. `DENY` "
            "refuses every operation for the principal and outranks the bucket owner."
        ),
    )


class S3GrantEntry(S3Grant):
    name: str = Field(
        description="Name of the user or group the grant applies to, resolved for display. Empty for `EVERYONE`.",
    )


class S3Entry(BaseModel):
    id: int = Field(description="Placeholder identifier. Not used as there is only one.")
    bindip: UniqueList[str] = Field(
        default=[],
        description=(
            "IP addresses the S3 service listens on, at most eight. An empty list listens on every address. Choices "
            "come from `s3.bindip_choices`."
        ),
    )
    port: Annotated[int, Field(ge=1, le=65535)] = Field(default=9000, description="TCP port the S3 service listens on.")
    servers: Annotated[int, Field(ge=1, le=8)] = Field(
        default=1,
        description=(
            "Reactor threads serving the listen addresses, each with its own io_uring ring and every address shared "
            "between them. At most eight, and no more than the system has CPUs. Each thread carries its own "
            "connection pool and buffering, so more of them cost memory. Changing it restarts the service."
        ),
    )
    certificate: int | None = Field(
        default=None,
        description="ID of the certificate that terminates TLS, or `null` to serve plaintext HTTP.",
    )
    region: str = Field(
        default="", description="Region name echoed to clients. Empty accepts whatever a client signs for."
    )
    log_level: Literal["ERROR", "WARNING", "NOTICE", "INFO", "DEBUG"] = Field(
        default="NOTICE",
        description="Least serious log record the S3 service keeps. `INFO` adds one record per request.",
    )
    default_audit: S3AuditMask = Field(
        default=[],
        description=(
            "Actions audited on every bucket that does not set its own `audit`, or `ALL`. An empty list audits "
            "nothing. Requires an Enterprise license."
        ),
    )
    default_audit_overflow: S3AuditOverflow = Field(
        default="DROP",
        description=(
            "What an audited request gets when no audit record slot is free, on buckets that do not set their own. "
            "`DROP` sheds the record, `BACKPRESSURE` answers the client with a retryable 503."
        ),
    )
    global_grants: list[S3GrantEntry] = Field(
        default=[],
        description=(
            "Grants that apply to every bucket. A `DENY` here suspends the principal everywhere, outranking every "
            "bucket grant. Listing buckets never needs one of these."
        ),
    )


class S3Update(S3Entry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    global_grants: list[S3Grant] = Field(description="Grants that apply to every bucket, replacing the current list.")


class S3UpdateArgs(BaseModel):
    data: S3Update = Field(description="S3 service configuration changes to apply.")


class S3UpdateResult(BaseModel):
    result: S3Entry = Field(description="The updated S3 service configuration.")


class S3BindipChoicesArgs(BaseModel):
    pass


class S3BindipChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="IP addresses the S3 service may listen on, keyed by address.")


class SharingS3Entry(BaseModel):
    id: int = Field(description="Unique identifier for the bucket.")
    name: Annotated[str, Field(min_length=3, max_length=63, pattern=r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")] = Field(
        description=(
            "Bucket name, following the S3 rules. Three to 63 characters of lowercase letters, digits, dots and "
            "hyphens, starting and ending with a letter or digit, no adjacent dots, and never an IPv4 address."
        ),
    )
    dataset: NonEmptyString = Field(
        description="The ZFS dataset the bucket is. Created by `sharing.s3.create` and owned by it.",
    )
    path: str = Field(
        description=(
            "Mount point of the bucket's dataset. Objects live under its `data` directory, which is created owned by "
            "`owner` with an inheritable ACL every grantee satisfies, so the grants alone decide access."
        ),
    )
    enabled: bool = Field(default=True, description="Whether the bucket is served. Toggling restarts the S3 service.")
    owner: NonEmptyString = Field(
        description=(
            "Account that owns the bucket and bypasses its grants. Its uid is captured when set, so a later rename "
            "or reuse of the name never changes who owns the bucket."
        ),
    )
    owner_uid: int = Field(description="The uid the owner resolved to when it was set.")
    grants: list[S3GrantEntry] = Field(default=[], description="Who may access the bucket and how, beyond its owner.")
    permissions_model: Literal["S3", "MULTIPROTOCOL"] = Field(
        default="S3",
        description=(
            "`S3` when only the S3 service writes the dataset. `MULTIPROTOCOL` when other protocols share the tree."
        ),
    )
    versioning: Literal["OFF", "ENABLED", "SUSPENDED"] = Field(default="OFF", description="Bucket versioning state.")
    object_lock: bool = Field(
        default=False,
        description=(
            "Whether object lock is enabled. Requires `versioning` to be `ENABLED` and the `S3` permissions model."
        ),
    )
    object_lock_default_mode: Literal["GOVERNANCE", "COMPLIANCE"] | None = Field(
        default=None,
        description="Retention mode of the default object lock rule, or `null` for no default rule.",
    )
    object_lock_default_days: Annotated[int, Field(ge=1, le=36500)] | None = Field(
        default=None,
        description="Retention period of the default object lock rule in days. Mutually exclusive with years.",
    )
    object_lock_default_years: Annotated[int, Field(ge=1, le=100)] | None = Field(
        default=None,
        description="Retention period of the default object lock rule in years. Mutually exclusive with days.",
    )
    sosapi_block_size: Literal[256, 512, 1024, 4096, 8192] | None = Field(
        default=None,
        description="Block size in KiB recommended to Veeam through SOSAPI, or `null` to recommend nothing.",
    )
    audit: S3AuditMask | None = Field(
        default=None,
        description=(
            "Actions audited on this bucket, `ALL`, or an empty list to audit nothing. `null` inherits the service's "
            "`default_audit`. Requires an Enterprise license."
        ),
    )
    audit_overflow: S3AuditOverflow | None = Field(
        default=None,
        description="Overflow behavior for this bucket's audit records, or `null` to inherit the service's default.",
    )
    locked: bool | None = Field(default=None, description="Whether the bucket's dataset is locked. Read only.")


class SharingS3Create(SharingS3Entry):
    id: Excluded = excluded_field()
    path: Excluded = excluded_field()
    owner_uid: Excluded = excluded_field()
    grants: list[S3Grant] = Field(default=[], description="Who may access the bucket and how, beyond its owner.")
    locked: Excluded = excluded_field()


class SharingS3Update(SharingS3Create, metaclass=ForUpdateMetaclass):
    dataset: Excluded = excluded_field()


class SharingS3CreateArgs(BaseModel):
    data: SharingS3Create = Field(description="Configuration for the new bucket.")


class SharingS3CreateResult(BaseModel):
    result: SharingS3Entry = Field(description="The created bucket.")


class SharingS3UpdateArgs(BaseModel):
    id: int = Field(description="ID of the bucket to update.")
    data: SharingS3Update = Field(description="Bucket changes to apply. `grants` replaces the whole list.")


class SharingS3UpdateResult(BaseModel):
    result: SharingS3Entry = Field(description="The updated bucket.")


class SharingS3DeleteArgs(BaseModel):
    id: int = Field(description="ID of the bucket to delete.")


class SharingS3DeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the bucket is successfully deregistered.")


class SharingS3AuditChoicesArgs(BaseModel):
    pass


class SharingS3AuditChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Actions an audit mask may name, keyed by name.")
