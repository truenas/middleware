from typing import Annotated, Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    NonEmptyString,
    excluded_field,
    query_result,
    single_argument_args,
    single_argument_result,
)

from .common import QueryFilters, QueryOptions, StorageTier

__all__ = [
    "ZfsTierEntry",
    "ZfsTierUpdateArgs",
    "ZfsTierUpdateResult",
    "ZfsTierRewriteJobStats",
    "ZfsTierRewriteJobEntry",
    "ZfsTierRewriteJobStatusEntry",
    "ZfsTierRewriteJobQueryEventSourceArgs",
    "ZfsTierRewriteJobQueryEventSourceEvent",
    "ZfsTierRewriteJobStatusEventSourceArgs",
    "ZfsTierRewriteJobStatusEventSourceEvent",
    "ZfsTierRewriteJobCreateArgs",
    "ZfsTierRewriteJobCreateResult",
    "ZfsTierRewriteJobCancelArgs",
    "ZfsTierRewriteJobCancelResult",
    "ZfsTierRewriteJobQueryArgs",
    "ZfsTierRewriteJobQueryResult",
    "ZfsTierRewriteJobRecoverArgs",
    "ZfsTierRewriteJobRecoverResult",
    "ZfsTierRewriteJobStatusArgs",
    "ZfsTierRewriteJobStatusResult",
    "ZfsTierRewriteJobFailureError",
    "ZfsTierRewriteJobFailureEntry",
    "ZfsTierRewriteJobFailuresArgs",
    "ZfsTierRewriteJobFailuresResult",
    "TierInfo",
    "ZfsTierDatasetSetTierArgs",
    "ZfsTierDatasetSetTierResult",
]

TierRewriteJobStatus = Literal[
    "COMPLETE", "RUNNING", "QUEUED", "CANCELLED", "STOPPED", "ERROR"
]


class ZfsTierEntry(BaseModel):
    id: int
    """Placeholder identifier. Not used; there is only one configuration instance."""
    enabled: bool
    """Whether the ZFS tier service is enabled."""
    max_concurrent_jobs: Annotated[int, Field(ge=1, le=10)]
    """Maximum number of rewrite jobs that execute simultaneously. Jobs submitted beyond this \
    limit are held in a QUEUED state until a slot becomes available (1-10)."""
    max_used_percentage: Annotated[int, Field(ge=70, le=95)]
    """Abort rewrites when filesystem usage reaches this percentage threshold (70-95)."""
    special_class_metadata_reserve_pct: Annotated[int, Field(ge=10, le=30)]
    """Percentage of PERFORMANCE tier space reserved for metadata. Metadata is always written \
    to the PERFORMANCE tier, but data is only placed there while allocated space stays below \
    `100 - special_class_metadata_reserve_pct` percent of total PERFORMANCE tier capacity. \
    Beyond that threshold data falls back to the REGULAR tier. Corresponds to the ZFS kernel \
    parameter `zfs_special_class_metadata_reserve_pct` (default: 25)."""


@single_argument_args("zfs_tier_update")
class ZfsTierUpdateArgs(ZfsTierEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ZfsTierUpdateResult(BaseModel):
    result: ZfsTierEntry
    """The updated ZFS tier daemon configuration."""


class ZfsTierRewriteJobStats(BaseModel):
    start_time: int
    """Unix timestamp (seconds) when the current run started. Reset each time the job is \
    resumed or recovered."""
    initial_time: int
    """Unix timestamp (seconds) when the job was first created. Preserved across resumes."""
    update_time: int
    """Unix timestamp (seconds) of the most recent statistics update."""
    count_items: int
    """Number of files processed in the current run. Reset to zero on each resume."""
    count_bytes: int
    """Bytes processed in the current run. Reset to zero on each resume."""
    total_items: int
    """Total number of files to process across the entire dataset."""
    total_bytes: int
    """Total bytes to process across the entire dataset."""
    failures: int
    """Cumulative count of files that failed rewriting across all runs of this job."""
    success: int
    """Cumulative count of files successfully rewritten across all runs of this job."""
    parent: str
    """Directory path of the file currently being processed. Also used as the resume \
    checkpoint if the job is interrupted."""
    name: str
    """Name of the file currently being processed."""


class ZfsTierRewriteJobEntry(BaseModel):
    tier_job_id: NonEmptyString
    """Rewrite job identifier in `dataset_name@job_uuid` format."""
    dataset_name: NonEmptyString
    """ZFS dataset this job is operating on."""
    job_uuid: NonEmptyString
    """Unique identifier for this rewrite job."""
    status: TierRewriteJobStatus
    """Current lifecycle state of the job.

    * `COMPLETE` - All files in the dataset have been processed.
    * `RUNNING` - Job is actively processing files.
    * `QUEUED` - Job is waiting for a free execution slot (see `max_concurrent_jobs`).
    * `CANCELLED` - Job was stopped via `zfs_tier_job.cancel`. Not resumable.
    * `STOPPED` - Job was RUNNING but its process is no longer active (e.g. daemon restart). \
    This state is computed on read and is never written to persistent storage.
    * `ERROR` - Job halted due to an unrecoverable error. Use `zfs_tier_job.recover` to \
    retry failed files.
    """


class TierInfo(BaseModel):
    tier_type: StorageTier
    """Storage performance tier for this share."""
    tier_job: ZfsTierRewriteJobEntry | None = None
    """Most recent rewrite job for this share's dataset, or `null` if no job history exists."""


class ZfsTierRewriteJobStatusEntry(ZfsTierRewriteJobEntry):
    stats: ZfsTierRewriteJobStats | None
    """Progress statistics, or `null` if no statistics have been recorded yet."""
    error: str | None
    """Error message describing why the job entered `ERROR` state, otherwise `null`."""


class ZfsTierRewriteJobQueryEventSourceArgs(BaseModel):
    """No arguments — subscribes to all rewrite job lifecycle events."""


@single_argument_result
class ZfsTierRewriteJobQueryEventSourceEvent(BaseModel):
    fields: ZfsTierRewriteJobEntry
    """Current job entry reflecting the latest lifecycle state."""


class ZfsTierRewriteJobQueryAddedEvent(BaseModel):
    id: NonEmptyString
    """Identifier of the rewrite job that was added (`dataset_name@job_uuid` format)."""
    fields: ZfsTierRewriteJobEntry
    """Complete job information for the newly created job."""


class ZfsTierRewriteJobQueryChangedEvent(BaseModel):
    id: NonEmptyString
    """Identifier of the rewrite job that changed (`dataset_name@job_uuid` format)."""
    fields: ZfsTierRewriteJobEntry
    """Updated job information reflecting the latest lifecycle state."""


class ZfsTierRewriteJobQueryRemovedEvent(BaseModel):
    id: NonEmptyString
    """Identifier of the rewrite job that removed (`dataset_name@job_uuid` format)."""


class ZfsTierRewriteJobStatusEventSourceArgs(BaseModel):
    dataset_name: NonEmptyString
    """ZFS dataset to subscribe to (e.g. `tank/data`). Receives updates whenever the job \
    status or statistics change."""


@single_argument_result
class ZfsTierRewriteJobStatusEventSourceEvent(BaseModel):
    fields: ZfsTierRewriteJobStatusEntry
    """Current status and statistics for the dataset's active rewrite job."""


@single_argument_args("zfs_tier_rewrite_job_create")
class ZfsTierRewriteJobCreateArgs(BaseModel):
    dataset_name: NonEmptyString
    """ZFS dataset to rewrite (e.g. `tank/data`). Only one job may exist per dataset at \
    a time; creating a second returns an error."""


class ZfsTierRewriteJobCreateResult(BaseModel):
    result: ZfsTierRewriteJobEntry
    """The newly created rewrite job, initially in `QUEUED` state."""


@single_argument_args("zfs_tier_rewrite_job_cancel")
class ZfsTierRewriteJobCancelArgs(BaseModel):
    tier_job_id: NonEmptyString
    """Rewrite job to cancel, in `dataset_name@job_uuid` format."""


class ZfsTierRewriteJobCancelResult(BaseModel):
    result: None
    """Returns `null` when the job has been successfully cancelled."""


@single_argument_args("zfs_tier_rewrite_job_query")
class ZfsTierRewriteJobQueryArgs(BaseModel):
    status: list[TierRewriteJobStatus] | None = None
    """Limit results to jobs in the specified states. Pass `null` or omit to return all jobs."""
    query_filters: QueryFilters = Field(alias="query-filters", default=[])
    """Additional filters to apply to the results."""
    query_options: QueryOptions = Field(alias="query-options", default=QueryOptions())
    """Options controlling sort order, pagination, and result format."""


ZfsTierRewriteJobQueryResult = query_result(
    ZfsTierRewriteJobEntry, name="ZfsTierRewriteJobQueryResult"
)


@single_argument_args("zfs_tier_rewrite_job_recover")
class ZfsTierRewriteJobRecoverArgs(BaseModel):
    tier_job_id: NonEmptyString
    """Rewrite job to recover, in `dataset_name@job_uuid` format. The job must be in \
    `ERROR` state."""


class ZfsTierRewriteJobRecoverResult(BaseModel):
    result: ZfsTierRewriteJobEntry
    """The job after recovery is initiated. Status will be `RUNNING` if failed files remain \
    to be retried, or `COMPLETE` if all previously failed files were retried successfully."""


@single_argument_args("zfs_tier_rewrite_job_status")
class ZfsTierRewriteJobStatusArgs(BaseModel):
    tier_job_id: NonEmptyString
    """Rewrite job to query, in `dataset_name@job_uuid` format."""


class ZfsTierRewriteJobStatusResult(BaseModel):
    result: ZfsTierRewriteJobStatusEntry
    """Current status and statistics for the requested rewrite job."""


class ZfsTierRewriteJobFailureError(BaseModel):
    errno: int
    """Error number from the failed storage tier migration."""
    strerror: str
    """Human-readable description of the error."""


class ZfsTierRewriteJobFailureEntry(BaseModel):
    filename: str
    """Name of the file that failed to migrate storage tier."""
    error: ZfsTierRewriteJobFailureError
    """Error details for the failed storage tier migration."""
    path: str | None
    """Absolute path of the file resolved via its file handle, or `null` if the file \
    no longer exists on the filesystem."""


@single_argument_args("zfs_tier_rewrite_job_failures")
class ZfsTierRewriteJobFailuresArgs(BaseModel):
    tier_job_id: NonEmptyString
    """Rewrite job to query, in `dataset_name@job_uuid` format."""
    query_filters: QueryFilters = Field(alias="query-filters", default=[])
    """Additional filters to apply to the results."""
    query_options: QueryOptions = Field(alias="query-options", default=QueryOptions())
    """Options controlling sort order, pagination, and result format."""


ZfsTierRewriteJobFailuresResult = query_result(
    ZfsTierRewriteJobFailureEntry,
    name="ZfsTierRewriteJobFailuresResult",
)


@single_argument_args("zfs_tier_dataset_set_tier")
class ZfsTierDatasetSetTierArgs(BaseModel):
    dataset_name: NonEmptyString
    """ZFS dataset to configure (e.g. `tank/data`)."""
    tier_type: StorageTier
    """Storage performance tier for this dataset."""
    move_existing_data: bool = False
    """When `true`, immediately create a rewrite job to physically migrate existing \
    data to match the new tier."""


class ZfsTierDatasetSetTierResult(BaseModel):
    result: TierInfo
    """Updated tier info for the dataset. If `move_existing_data` was `true`, \
    `tier_job` will contain the newly created rewrite job."""
