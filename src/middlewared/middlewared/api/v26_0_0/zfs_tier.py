from typing import Annotated, Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    NonEmptyString,
    query_result,
    single_argument_args,
)
from .common import DatasetTier, QueryFilters, QueryOptions


__all__ = [
    'ZfsTierEntry', 'ZfsTierUpdateArgs', 'ZfsTierUpdateResult',
    'ZfsTierRewriteJobStats', 'ZfsTierRewriteJobEntry', 'ZfsTierRewriteJobStatusEntry',
    'ZfsTierRewriteJobCreateArgs', 'ZfsTierRewriteJobCreateResult',
    'ZfsTierRewriteJobAbortArgs', 'ZfsTierRewriteJobAbortResult',
    'ZfsTierRewriteJobQueryArgs', 'ZfsTierRewriteJobQueryResult',
    'ZfsTierRewriteJobRecoverArgs', 'ZfsTierRewriteJobRecoverResult',
    'ZfsTierRewriteJobStatusArgs', 'ZfsTierRewriteJobStatusResult',
    'SharingTierInfo',
]

TierRewriteJobStatus = Literal['COMPLETE', 'RUNNING', 'QUEUED', 'CANCELLED', 'STOPPED', 'ERROR']


class ZfsTierEntry(BaseModel):
    id: int
    """Placeholder identifier. Not used; there is only one configuration instance."""
    enabled: bool
    """Whether the ZFS tier service is enabled."""
    max_concurrent_jobs: Annotated[int, Field(ge=1, le=10)]
    """Maximum number of rewrite jobs that execute simultaneously. Jobs submitted beyond this \
    limit are held in a QUEUED state until a slot becomes available (1-10)."""
    min_available_space: Annotated[int, Field(ge=0)]
    """If available space on the dataset falls below this value (GiB), any active rewrite on \
    that dataset is aborted. Set to 0 to disable the check."""


@single_argument_args('zfs_tier_update')
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
    * `CANCELLED` - Job was stopped via `zfs_tier_job.abort`. Not resumable.
    * `STOPPED` - Job was RUNNING but its process is no longer active (e.g. daemon restart). \
    This state is computed on read and is never written to persistent storage.
    * `ERROR` - Job halted due to an unrecoverable error. Use `zfs_tier_job.recover` to \
    retry failed files.
    """


class SharingTierInfo(BaseModel):
    tier_type: DatasetTier
    """Storage performance tier for this share."""
    tier_job: ZfsTierRewriteJobEntry | None = None
    """Most recent rewrite job for this share's dataset, or `null` if no job history exists."""


class ZfsTierRewriteJobStatusEntry(ZfsTierRewriteJobEntry):
    stats: ZfsTierRewriteJobStats | None
    """Progress statistics, or `null` if no statistics have been recorded yet."""
    error: str | None
    """Error message describing why the job entered `ERROR` state, otherwise `null`."""


class ZfsTierRewriteJobCreateArgs(BaseModel):
    dataset_name: NonEmptyString
    """ZFS dataset to rewrite (e.g. `tank/data`). Only one job may exist per dataset at \
    a time; creating a second returns an error."""


class ZfsTierRewriteJobCreateResult(BaseModel):
    result: ZfsTierRewriteJobEntry
    """The newly created rewrite job, initially in `QUEUED` state."""


class ZfsTierRewriteJobAbortArgs(BaseModel):
    tier_job_id: NonEmptyString
    """Rewrite job to abort, in `dataset_name@job_uuid` format."""


class ZfsTierRewriteJobAbortResult(BaseModel):
    result: None
    """Returns `null` when the job has been successfully aborted."""


class ZfsTierRewriteJobQueryArgs(BaseModel):
    status: list[TierRewriteJobStatus] | None = None
    """Limit results to jobs in the specified states. Pass `null` or omit to return all jobs."""
    query_filters: QueryFilters = Field(alias='query-filters', default=[])
    """Additional filters to apply to the results."""
    query_options: QueryOptions = Field(alias='query-options', default=QueryOptions())
    """Options controlling sort order, pagination, and result format."""


ZfsTierRewriteJobQueryResult = query_result(ZfsTierRewriteJobEntry, name='ZfsTierRewriteJobQueryResult')


class ZfsTierRewriteJobRecoverArgs(BaseModel):
    tier_job_id: NonEmptyString
    """Rewrite job to recover, in `dataset_name@job_uuid` format. The job must be in \
    `ERROR` state."""


class ZfsTierRewriteJobRecoverResult(BaseModel):
    result: ZfsTierRewriteJobEntry
    """The job after recovery is initiated. Status will be `RUNNING` if failed files remain \
    to be retried, or `COMPLETE` if all previously failed files were retried successfully."""


class ZfsTierRewriteJobStatusArgs(BaseModel):
    tier_job_id: NonEmptyString
    """Rewrite job to query, in `dataset_name@job_uuid` format."""


class ZfsTierRewriteJobStatusResult(BaseModel):
    result: ZfsTierRewriteJobStatusEntry
    """Current status and statistics for the requested rewrite job."""
