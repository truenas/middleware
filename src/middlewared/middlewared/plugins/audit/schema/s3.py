from typing import Literal

from middlewared.api.base import BaseModel
from middlewared.api.base.jsonschema import add_attrs, replace_refs
from middlewared.utils.pydantic_ import model_json_schema

from .common import AuditEvent, AuditEventVersion, convert_schema_to_set

# The S3 daemon (s3d) emits one kernel-audit record per audited request;
# the audit_rules handler recognizes them by their op=s3d: vocabulary and
# emits them under the TNAUDIT_S3 ident with the envelope and per-event
# field sets below. The producer's contract is AUDIT.md in the truenas_s3
# repository; the event name is the S3 wire operation, verbatim.

# The thirteen bucket-configuration probes route as one operation whose
# rendering names the probed subresource.
S3_PROBE_EVENTS = tuple(
    f'GetBucketProbe({probe})' for probe in (
        'Accelerate', 'Cors', 'Encryption', 'Lifecycle', 'Logging',
        'ObjectLock', 'OwnershipControls', 'Policy', 'PolicyStatus',
        'PublicAccessBlock', 'RequestPayment', 'Tagging', 'Website',
    )
)


class AuditEventS3ServiceData(BaseModel):
    vers: AuditEventVersion


class AuditEventS3EventData(BaseModel):
    """The envelope every S3 record carries.

    `record_type` is the kernel-audit class the daemon originated the
    record as: TRUSTED_APP is an executed operation, USER_AUTH a request
    refused before a principal existed, USER_ACCT an account the
    identity gate refused, and DAC_CHECK a discretionary denial.
    `status` and `err` are absent together on a request that died
    without an answer.
    """
    vers: AuditEventVersion
    record_type: Literal['TRUSTED_APP', 'USER_AUTH', 'USER_ACCT', 'DAC_CHECK']
    req: str
    acct_uid: int | None = None
    keyid: str | None = None
    bucket: str | None = None
    obj: str | None = None
    ver: str | None = None
    status: int | None = None
    err: str | None = None
    bytes_in: int
    bytes_out: int
    clipped: bool | None = None


class AuditEventS3(AuditEvent):
    event_data: AuditEventS3EventData
    service: Literal['S3']
    service_data: AuditEventS3ServiceData


class AuditEventS3ReadEventData(AuditEventS3EventData):
    range: str | None = None


class AuditEventS3Read(AuditEventS3):
    event: Literal['GetObject', 'HeadObject']
    event_data: AuditEventS3ReadEventData


class AuditEventS3PutEventData(AuditEventS3EventData):
    size: int | None = None


class AuditEventS3Put(AuditEventS3):
    event: Literal['PutObject']
    event_data: AuditEventS3PutEventData


class AuditEventS3CopyEventData(AuditEventS3EventData):
    src_bucket: str | None = None
    src_obj: str | None = None
    src_ver: str | None = None


class AuditEventS3Copy(AuditEventS3):
    event: Literal['CopyObject']
    event_data: AuditEventS3CopyEventData


class AuditEventS3DeleteEventData(AuditEventS3EventData):
    marker: bool | None = None


class AuditEventS3Delete(AuditEventS3):
    event: Literal['DeleteObject']
    event_data: AuditEventS3DeleteEventData


class AuditEventS3BatchDeleteEventData(AuditEventS3EventData):
    """One record for the whole batch: counts partitioning an ordered
    key list, truncated to the record's size budget with the remainder
    accounted."""
    deleted: int | None = None
    denied: int | None = None
    errors: int | None = None
    objs: list[str] | None = None
    truncated: int | None = None


class AuditEventS3BatchDelete(AuditEventS3):
    event: Literal['DeleteObjects']
    event_data: AuditEventS3BatchDeleteEventData


class AuditEventS3UploadEventData(AuditEventS3EventData):
    upload: str | None = None


class AuditEventS3Upload(AuditEventS3):
    event: Literal[
        'CreateMultipartUpload', 'AbortMultipartUpload', 'ListParts',
    ]
    event_data: AuditEventS3UploadEventData


class AuditEventS3PartEventData(AuditEventS3EventData):
    upload: str | None = None
    part: int | None = None
    size: int | None = None


class AuditEventS3Part(AuditEventS3):
    event: Literal['UploadPart']
    event_data: AuditEventS3PartEventData


class AuditEventS3CompleteEventData(AuditEventS3EventData):
    upload: str | None = None
    parts: int | None = None


class AuditEventS3Complete(AuditEventS3):
    event: Literal['CompleteMultipartUpload']
    event_data: AuditEventS3CompleteEventData


class AuditEventS3ListingEventData(AuditEventS3EventData):
    prefix: str | None = None


class AuditEventS3Listing(AuditEventS3):
    event: Literal['ListObjects', 'ListObjectsV2', 'ListMultipartUploads']
    event_data: AuditEventS3ListingEventData


class AuditEventS3AccountEventData(AuditEventS3EventData):
    n: int | None = None


class AuditEventS3Account(AuditEventS3):
    event: Literal['ListBuckets']
    event_data: AuditEventS3AccountEventData


class AuditEventS3BucketRead(AuditEventS3):
    event: Literal[
        'HeadBucket', 'GetBucketLocation', 'GetBucketVersioning',
        *S3_PROBE_EVENTS,
    ]
    event_data: AuditEventS3EventData


AUDIT_EVENT_S3_JSON_SCHEMAS = [
    add_attrs(replace_refs(model_json_schema(event_model)))
    for event_model in (
        AuditEventS3Read,
        AuditEventS3Put,
        AuditEventS3Copy,
        AuditEventS3Delete,
        AuditEventS3BatchDelete,
        AuditEventS3Upload,
        AuditEventS3Part,
        AuditEventS3Complete,
        AuditEventS3Listing,
        AuditEventS3Account,
        AuditEventS3BucketRead,
    )
]


AUDIT_EVENT_S3_PARAM_SET = convert_schema_to_set(AUDIT_EVENT_S3_JSON_SCHEMAS)
