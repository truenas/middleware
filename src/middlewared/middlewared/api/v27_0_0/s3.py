from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, Secret

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    LocalUsername,
    NonEmptyString,
    RemoteUsername,
    excluded_field,
)

from .zfs_tier import TierInfo

__all__ = [
    "S3AccesskeyEntry",
    "S3AccesskeyEntryWithSecret",
    "S3AccesskeyCreate",
    "S3AccesskeyUpdate",
    "S3AccesskeyCreateArgs",
    "S3AccesskeyCreateResult",
    "S3AccesskeyUpdateArgs",
    "S3AccesskeyUpdateResult",
    "S3AccesskeyDeleteArgs",
    "S3AccesskeyDeleteResult",
    "S3Access",
    "S3AuditAction",
    "S3AuditMask",
    "S3Listener",
    "S3PrincipalType",
    "S3BucketName",
    "S3PermissionsModel",
    "S3BucketLayout",
    "S3ObjectOwnership",
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
    "SharingS3ForceDisableVersioningArgs",
    "SharingS3ForceDisableVersioningResult",
    "SharingS3RecoverBucket",
    "SharingS3RecoverableBucket",
    "SharingS3RecoveredBucket",
    "SharingS3RecoverableBucketsArgs",
    "SharingS3RecoverableBucketsResult",
    "SharingS3RecoverArgs",
    "SharingS3RecoverResult",
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
    "GetObjectAcl",
    "PutObjectAcl",
    "GetBucketAcl",
    "PutBucketAcl",
    "PutBucketVersioning",
    "CreateBucket",
    "DeleteBucket",
]
"""The actions an audit mask may name, spelled exactly as the S3 service
reads them: its maskable vocabulary in full. The service refuses its
whole config for an unknown name, and refuses `BypassGovernanceRetention`
in a mask — that probe rides beside an operation's own action and would
match no request — so it is the one action name not here."""

S3AuditMask = list[S3AuditAction] | Literal["ALL"]
S3AuditOverflow = Literal["DROP", "BACKPRESSURE"]
S3Access = Literal["READONLY", "WRITEONLY", "READWRITE", "DENY"]
S3PrincipalType = Literal["USER", "GROUP", "EVERYONE"]

S3PermissionsModel = Literal["S3", "MULTIPROTOCOL"]
"""How the S3 service treats the filesystem permissions on a bucket's
tree."""

S3BucketLayout = Literal["BUCKET", "DATASET"]
"""BUCKET: the S3 service owns the dataset and writes to it. DATASET: the
S3 service serves an existing dataset read-only."""

S3ObjectOwnership = Literal["BUCKET_OWNER_ENFORCED", "BUCKET_OWNER_PREFERRED", "OBJECT_WRITER"]
"""S3 Object Ownership: the bucket-level setting that controls ownership
of objects uploaded to a bucket and disables or enables ACLs."""

S3BucketName = Annotated[str, Field(min_length=3, max_length=63, pattern=r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")]
"""Bucket names may be 3-63 characters including lowercase letters, numbers, hyphens, and dots. Adjacent
dots (..) and names shaped like an IPv4 address are not permitted."""

S3AccessKeyId = Annotated[str, Field(pattern=r"^[A-Z0-9]{16,128}$")]
"""An S3 access key id: 16 to 128 uppercase letters and digits."""

S3SecretKey = Annotated[str, Field(min_length=16, max_length=128, pattern=r"^[\x21-\x7E]+$")]
"""An S3 secret access key: 16 to 128 printable ASCII characters with no
whitespace."""

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
    enabled: bool = Field(
        description="Whether the access key may be used. A disabled key is refused by the S3 service."
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Expiration timestamp for the access key or `null` for no expiration.",
    )
    created_at: datetime = Field(description="Timestamp when the access key was created.")
    last_used_at: datetime | None = Field(
        default=None,
        description=(
            "Timestamp of when the S3 service last accepted a request signed with this key. The value is "
            "`null` if the key has never been used. Access Key timestamps are updated from the S3 service at periodic "
            "intervals. This field is read-only."
        ),
    )
    manage_buckets: bool = Field(
        default=False,
        description=(
            "Whether this access key may create, delete, or modify buckets through the S3 protocol. Setting it "
            "requires the account that owns the key to hold the `SHARING_S3_WRITE` role."
        ),
    )
    status: S3AccesskeyStatus = Field(
        description=(
            "Effective state of the access key. Only `ENABLED` keys are usable. `DISABLED` was set by an "
            "administrator, `EXPIRED` passed its expiration, `USER_MISSING` belongs to a directory account that no "
            "longer resolves (a deleted local account takes its keys with it), and `SECRET_LOST` lost its secret to a "
            "configuration restore without the secret seed and "
            "must be rotated."
        ),
    )


class S3AccesskeyEntryWithSecret(S3AccesskeyEntry):
    secret: str = Field(
        description=(
            "The S3 secret access key. `s3.accesskey.create` and `s3.accesskey.update` with `rotate` return it "
            "once. No query returns it."
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
    last_used_at: Excluded = excluded_field()
    status: Excluded = excluded_field()


class S3AccesskeyCreateArgs(BaseModel):
    data: S3AccesskeyCreate = Field(description="Configuration for the new access key.")


class S3AccesskeyCreateResult(BaseModel):
    result: S3AccesskeyEntryWithSecret = Field(description="The created access key, with its secret.")


class S3AccesskeyUpdate(S3AccesskeyCreate, metaclass=ForUpdateMetaclass):
    username: Excluded = excluded_field()
    access_key: Excluded = excluded_field()
    secret: Excluded = excluded_field()
    rotate: bool = Field(
        default=False,
        description=(
            "Generate a new secret access key under the same access key id. The result includes the new secret."
        ),
    )


class S3AccesskeyUpdateArgs(BaseModel):
    id: int = Field(description="ID of the access key to update.")
    data: S3AccesskeyUpdate = Field(description="Access key changes to apply.")


class S3AccesskeyUpdateResult(BaseModel):
    result: S3AccesskeyEntryWithSecret | S3AccesskeyEntry = Field(
        description="The updated access key. With `rotate`, the result includes the new secret.",
    )


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


class S3Listener(BaseModel):
    address: NonEmptyString = Field(
        description="IP address to listen on, from `s3.bindip_choices`: a static address, a loopback or a wildcard.",
    )
    port: Annotated[int, Field(ge=1, le=65535)] = Field(default=9000, description="TCP port to listen on.")
    tls: bool = Field(
        default=False,
        description=(
            "Serve this address over TLS with `certificate`, which must then be set. Plaintext otherwise. A "
            "multi-homed system may serve a storage network in the clear and a management network over TLS."
        ),
    )


class S3Entry(BaseModel):
    id: int = Field(description="Placeholder identifier. Not used as there is only one.")
    listeners: list[S3Listener] = Field(
        default=[],
        description=(
            "Where the S3 service listens, at most eight entries, each an address and port served in plaintext or "
            "over TLS. An empty list listens on every address on port 9000 in plaintext. Changing it restarts the "
            "service."
        ),
    )
    servers: Annotated[int, Field(ge=1, le=12)] = Field(
        default=1,
        description=(
            "Reactor threads serving the listen addresses, each with its own io_uring ring and every address shared "
            "between them. At most twelve, and no more than the system has CPUs. Each thread carries its own "
            "connection pool and buffering, so more of them cost memory. Changing it restarts the service."
        ),
    )
    certificate: int | None = Field(
        default=None,
        description=(
            "ID of the certificate the TLS listeners serve. `null` serves them with the UI certificate "
            "(`system.general.ui_certificate`), so a renewal or a change there reaches the S3 service too."
        ),
    )
    region: Annotated[str, Field(max_length=63, pattern=r"^[a-z0-9-]*$")] = Field(
        default="",
        description=(
            "Region name echoed to clients: at most 63 characters of lowercase letters, digits and hyphens, "
            "`us-east-1` shaped. Empty accepts whatever a client signs for."
        ),
    )
    log_level: Literal["ERROR", "WARNING", "NOTICE", "INFO", "DEBUG"] = Field(
        default="NOTICE",
        description="Least serious log record the S3 service keeps. `INFO` adds one record per request.",
    )
    default_audit: S3AuditMask = Field(
        default=[],
        description=(
            "Actions audited on every bucket that does not set its own `audit`, or `ALL`. An empty list audits "
            "nothing. Also the only mask that can select `CreateBucket` and `ListAllMyBuckets`: a create precedes "
            "its bucket's registration, and listing buckets is account-scoped, so neither ever consults a bucket's "
            "own mask. NOTE: this is a licensed feature."
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
    managed_root_dataset: str = Field(
        default="",
        description=(
            "Path where datasets for S3 buckets created through S3 protocol CreateBucket requests are created, "
            "for example `tank/s3`. The path is a dataset name, not a mount point, and the dataset must already "
            "exist. If this field is empty (the default), S3 protocol CreateBucket requests are refused."
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
    result: dict[str, str] = Field(
        description="IP addresses a listener may name, keyed by address: static ones, loopbacks and the wildcards."
    )


class SharingS3Entry(BaseModel):
    id: int = Field(description="Unique identifier for the bucket.")
    name: S3BucketName = Field(
        description=(
            "Bucket name must be three to 63 characters of lowercase letters, digits, dots and "
            "hyphens, starting and ending with a letter or digit, no adjacent dots, and not an IP address."
        ),
    )
    dataset: NonEmptyString = Field(
        description=(
            "The ZFS dataset of the bucket. The location of S3 data within the dataset depends on the `layout` field."
        ),
    )
    layout: S3BucketLayout = Field(
        default="BUCKET",
        description=(
            "This create-time mutable field determines where S3 objects are located within the share. "
            "If set to `BUCKET` (the default), then the S3 share is a conventional S3 bucket that supports "
            "writes through the S3 protocol. Data must be accessed through the `s3data` directory inside the "
            "dataset. If set to `DATASET`, then the entire dataset contents are exposed as S3 objects, but S3 protocol "
            "access is restricted to read only operations. This setting is available to S3 protocol access to non-S3 "
            "data, for example, SMB or NFS shares."
        ),
    )
    enabled: bool = Field(default=True, description="Whether the bucket is served. Changing it reloads the S3 service.")
    owner: NonEmptyString = Field(
        description=(
            "Account that owns the bucket and bypasses its grants, owns the `s3data` directory when the S3 "
            "service creates it, and owns every object written under the `BUCKET_OWNER_ENFORCED` object "
            "ownership setting."
        ),
    )
    owner_uid: int = Field(description="The uid that owns the bucket.")
    grants: list[S3GrantEntry] = Field(default=[], description="Who may access the bucket and how, beyond its owner.")
    permissions_model: S3PermissionsModel = Field(
        default="S3",
        description=(
            "How the S3 service treats the filesystem permissions on the bucket's tree. "
            "When `S3` is set, access is solely determined by the bucket's grants and object ACL if the "
            "`object_ownership` bucket configuration field is not set to `BUCKET_OWNER_ENFORCED`. In this "
            "configuration, filesystem ACLs are not evaluated by the S3 server. "
            "When `MULTIPROTOCOL` is set, filesystem ACLs are enforced in addition to S3 protocol access "
            "control mechanisms. S3 shares with `DATASET` layout default to the `MULTIPROTOCOL` permissions model."
        ),
    )
    object_ownership: S3ObjectOwnership = Field(
        default="BUCKET_OWNER_ENFORCED",
        description=(
            "S3 Object Ownership, the bucket-level setting that controls ownership of objects uploaded to the "
            "bucket and disables or enables ACLs, and what `GetBucketOwnershipControls` reports. "
            "`BUCKET_OWNER_ENFORCED` (the default): ACLs are disabled, and the bucket owner automatically owns "
            "and has full control over every object in the bucket. ACLs no longer affect permissions to data in "
            "the bucket, and the bucket uses its grants to define access control. Requests to set or update "
            "ACLs fail with `AccessControlListNotSupported`; requests to read ACLs are supported. Only uploads "
            "with bucket owner full control ACLs, or uploads that do not specify an ACL, are accepted. "
            "`BUCKET_OWNER_PREFERRED`: the bucket owner owns and has full control over new objects that other "
            "accounts write to the bucket with the `bucket-owner-full-control` canned ACL. Objects uploaded "
            "with other ACLs are owned by the writing account. ACLs can be updated and can grant permissions. "
            "`OBJECT_WRITER`: the account that uploads an object owns the object, has full control over it, and "
            "can grant other users access to it through ACLs. "
            "A `MULTIPROTOCOL` bucket is always `OBJECT_WRITER` whatever is given here, and its ACLs stay "
            "disabled: the other protocols' users own the filesystem permissions on the tree."
        ),
    )
    versioning: Literal["OFF", "ENABLED", "SUSPENDED"] = Field(
        default="OFF",
        description=(
            "Bucket versioning state. One-way: a bucket that has been `ENABLED` or `SUSPENDED` cannot return to "
            "`OFF` here, only move between those two, so its stored versions never go unreachable. "
            "`sharing.s3.force_disable_versioning` is the one destructive way back, and it destroys every prior "
            "object version. NOTE: this is a licensed feature."
        ),
    )
    snapshot_versions: list[NonEmptyString] = Field(
        default=[],
        description=(
            "Patterns over the names of the bucket dataset's ZFS snapshots, `*` and `?` the only metacharacters, "
            "each matched against a whole name. Every snapshot a pattern selects serves each object's state frozen "
            "in it as a read-only version: listed by `ListObjectVersions` and read by its version id. Empty serves "
            "none. Requires `versioning` to be `ENABLED` or `SUSPENDED`."
        ),
    )
    snapshot_versions_max: Annotated[int, Field(ge=1, le=4294967295)] = Field(
        default=64,
        description=(
            "How many of the newest selected snapshots one `ListObjectVersions` listing consults. Bounds the listing "
            "alone: a selected snapshot beyond it still serves by its version id."
        ),
    )
    multipart_etag: Literal["COMPOSITE", "MINTED"] = Field(
        default="MINTED",
        description=(
            "ETag format for objects created by multipart upload. `MINTED` gives the object an opaque token. "
            "`COMPOSITE` gives it the standard S3 multipart ETag, built from the MD5 of each part. Choose "
            "`COMPOSITE` if a client verifies or resumes uploads by computing that ETag itself and comparing."
        ),
    )
    object_lock: bool = Field(
        default=False,
        description=(
            "Whether object lock is enabled. Requires `versioning` to be `ENABLED` and a permissions model other "
            "than `MULTIPROTOCOL`: a locked bucket is the S3 service's alone. One-way: the lock is latched on the "
            "bucket's dataset and cannot be disabled once enabled. NOTE: this is a licensed feature."
        ),
    )
    object_lock_default_mode: Literal["GOVERNANCE", "COMPLIANCE"] | None = Field(
        default=None,
        description="Retention mode of the default object lock rule, or `null` for no default rule.",
    )
    object_lock_default_days: Annotated[int, Field(ge=1, le=36500)] | None = Field(
        default=None,
        description="Retention period of the default object lock rule in days, up to 36500 (a hundred years).",
    )
    audit: S3AuditMask | None = Field(
        default=None,
        description=(
            "Actions audited on this bucket, `ALL`, or an empty list to audit nothing. `null` inherits the service's "
            "`default_audit`. `CreateBucket` and `ListAllMyBuckets` never match here — the service `default_audit` "
            "governs both — while `DeleteBucket` does match this bucket's own deletion. NOTE: this is a licensed "
            "feature."
        ),
    )
    audit_overflow: S3AuditOverflow | None = Field(
        default=None,
        description="Overflow behavior for this bucket's audit records, or `null` to inherit the service's default.",
    )
    locked: bool | None = Field(default=None, description="Whether the bucket's dataset is locked. Read only.")
    tier: TierInfo | None = Field(
        default=None,
        description=(
            "Storage tier in which the bucket's dataset is located. This field is read-only; configure the "
            "dataset's tier via `zfs.tier.dataset_set_tier`. NOTE: this is a licensed feature. Will be `null` if "
            "TrueNAS is unlicensed, if tiering is disabled, or if the pool has no SPECIAL vdev."
        ),
    )


class SharingS3Create(SharingS3Entry):
    id: Excluded = excluded_field()
    owner_uid: Excluded = excluded_field()
    dataset: NonEmptyString | None = Field(
        default=None,
        description=(
            "The ZFS dataset for the bucket. With `create_dataset` true, `sharing.s3.create` creates the "
            "dataset. When this field is omitted, the dataset is created under the S3 service's "
            "`managed_root_dataset` with the name of the bucket, plus a `_N` suffix if that name is in use. "
            "With `create_dataset` false, this field is required and must name an existing dataset."
        ),
    )
    create_dataset: bool = Field(
        default=True,
        description=(
            "Whether `sharing.s3.create` creates `dataset`. When false, `dataset` must name an existing, mounted "
            "dataset. With the `BUCKET` layout, that dataset must be empty and have the properties "
            "`sharing.s3.create` sets on a new dataset. With the `DATASET` layout, this field defaults to false "
            "and cannot be true."
        ),
    )
    grants: list[S3Grant] = Field(default=[], description="Who may access the bucket and how, beyond its owner.")
    locked: Excluded = excluded_field()
    tier: Excluded = excluded_field()


class SharingS3Update(SharingS3Create, metaclass=ForUpdateMetaclass):
    dataset: Excluded = excluded_field()
    layout: Excluded = excluded_field()
    create_dataset: Excluded = excluded_field()


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


class SharingS3ForceDisableVersioningArgs(BaseModel):
    id: int = Field(description="ID of the bucket whose versioning is forced off.")


class SharingS3ForceDisableVersioningResult(BaseModel):
    result: SharingS3Entry = Field(description="The updated bucket, with versioning `OFF`.")


class SharingS3RecoverableBucket(SharingS3Entry):
    """The stored configuration of a bucket that is no longer registered."""

    id: Excluded = excluded_field()
    locked: Excluded = excluded_field()
    tier: Excluded = excluded_field()


class SharingS3RecoverableBucketsArgs(BaseModel):
    pass


class SharingS3RecoverableBucketsResult(BaseModel):
    result: list[SharingS3RecoverableBucket] = Field(
        description="Array of datasets containing S3 data and configuration that can be recovered.",
    )


class SharingS3RecoverBucket(BaseModel):
    dataset: NonEmptyString = Field(description="The dataset from which to recover the bucket.")
    name_override: S3BucketName | None = Field(
        default=None,
        description="Manual override for bucket name. Replaces stored configuration. Use `null` to keep original.",
    )
    owner_override: NonEmptyString | None = Field(
        default=None,
        description="Manual override for bucket owner. Replaces stored configuration. Use `null` to keep original.",
    )


class SharingS3RecoverArgs(BaseModel):
    buckets: Annotated[list[SharingS3RecoverBucket], Field(min_length=1)] = Field(
        description="Array of datasets to recover. Each dataset gets a separate success / failure answer.",
    )


class SharingS3RecoveredBucket(BaseModel):
    dataset: NonEmptyString = Field(description="The dataset this answer is for.")
    bucket: SharingS3Entry | None = Field(
        description="Recovered bucket configuration or `null` when not recovered.",
    )
    error: str | None = Field(description="Reason why bucket restore failed. `null` on success.")


class SharingS3RecoverResult(BaseModel):
    result: list[SharingS3RecoveredBucket] = Field(
        description="One answer per requested dataset in the order requested.",
    )


class SharingS3AuditChoicesArgs(BaseModel):
    pass


class SharingS3AuditChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Actions an audit mask may name, keyed by name.")
