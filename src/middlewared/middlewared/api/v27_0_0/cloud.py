from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass, LongString, NonEmptyString
from .cloud_credential import CredentialsEntry
from .common import CronModel

__all__ = ["BaseCloudEntry", "CloudTaskAttributes"]


class CloudCron(CronModel):
    minute: str = "00"


class CloudTaskAttributes(BaseModel, metaclass=ForUpdateMetaclass):
    bucket: NonEmptyString = Field(description="Name of the cloud storage bucket or container.")
    folder: str = Field(description="Path within the cloud storage bucket to use as the root directory for operations.")
    fast_list: bool = Field(
        default=False,
        description=(
            "Valid only for some providers. Use fewer transactions in exchange for more RAM. This may also speed up or "
            "slow down your transfer. See https://rclone.org/docs/#fast-list for more details."
        ),
    )
    bucket_policy_only: bool = Field(
        default=False,
        description=(
            "Valid only for GOOGLE_CLOUD_STORAGE provider. Access checks should use bucket-level IAM policies. If you "
            "want to upload objects to a bucket with Bucket Policy Only set then you will need to set this."
        ),
    )
    b2_chunk_size: int = Field(
        alias="chunk_size",
        default=96,
        description=(
            "Valid only for B2 provider. Upload chunk size. Must fit in memory. Note that these chunks are buffered in "
            "memory and there might be a maximum of `--transfers` chunks in progress at once. Also, your largest file "
            "must be split in no more than 10,000 chunks."
        ),
    )
    dropbox_chunk_size: int = Field(
        alias="chunk_size",
        default=48,
        description=(
            "Valid only for DROPBOX provider. Upload chunk size in MiB. Must fit in memory. Note that these chunks are "
            "buffered in memory and there might be a maximum of `--transfers` chunks in progress at once. Dropbox "
            "Business accounts can have monthly data transfer limits per team per month. By using larger chunk sizes "
            "you will decrease the number of data transfer calls used and you'll be able to transfer more data to your "
            "Dropbox Business account."
        ),
    )
    acknowledge_abuse: bool = Field(
        default=False,
        description=(
            "Valid only for GOOGLE_DRIVER provider. Allow files which return cannotDownloadAbusiveFile to be "
            "downloaded. If downloading a file returns the error \"This file has been identified as malware or spam and"
            " cannot be downloaded\" with the error code \"cannotDownloadAbusiveFile\" then enable this flag to "
            "indicate you acknowledge the risks of downloading the file and TrueNAS will download it anyway."
        ),
    )
    region: str = Field(default="", description="Valid only for S3 provider. S3 Region.")
    encryption: Literal[None, "AES256"] = Field(
        default=None,
        description="Valid only for S3 provider. Server-Side Encryption.",
    )
    storage_class: Literal["", "STANDARD", "REDUCED_REDUNDANCY", "STANDARD_IA", "ONEZONE_IA", "INTELLIGENT_TIERING",
                           "GLACIER", "GLACIER_IR", "DEEP_ARCHIVE"] = Field(
        default="",
        description="Valid only for S3 provider. The storage class to use.",
    )


class BaseCloudEntry(BaseModel):
    id: int = Field(description="Unique identifier for this cloud storage configuration.")
    description: str = Field(default="", description="The name of the task to display in the UI.")
    path: str = Field(description="The local path to back up beginning with `/mnt` or `/dev/zvol`.")
    dataset: str | None = Field(
        description=(
            "The ZFS dataset containing this path (e.g., 'tank/backup'). This is a read-only field automatically "
            "resolved from \"path\". May be `null` if dataset is unavailable."
        ),
    )
    relative_path: str | None = Field(
        description=(
            "The path relative to the dataset mountpoint (e.g., 'subdir/data'). This is a read-only field automatically"
            " resolved from \"path\". May be `null` if dataset is unavailable."
        ),
    )
    credentials: CredentialsEntry = Field(description="Cloud credentials to use for each backup.")
    attributes: CloudTaskAttributes = Field(description="Additional information for each backup, e.g. bucket name.")
    schedule: CloudCron = Field(
        default_factory=CloudCron,
        description="Cron schedule dictating when the task should run.",
    )
    pre_script: LongString = Field(default="", description="A Bash script to run immediately before every backup.")
    post_script: LongString = Field(
        default="",
        description="A Bash script to run immediately after every backup if it succeeds.",
    )
    snapshot: bool = Field(
        default=False,
        description="Whether to create a temporary snapshot of the dataset before every backup.",
    )
    include: list[NonEmptyString] = Field(
        default_factory=list,
        description="Paths to pass to `restic backup --include`.",
    )
    exclude: list[NonEmptyString] = Field(
        default_factory=list,
        description="Paths to pass to `restic backup --exclude`.",
    )
    args: LongString = Field(default="", description="(Slated for removal).")
    enabled: bool = Field(default=True, description="Can enable/disable the task.")
    job: dict | None = Field(description="Information regarding the task's job state, e.g. progress.")
    locked: bool = Field(description="A locked task cannot run.")
