from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field

from middlewared.api.base import (
    BaseModel, ForUpdateMetaclass, LongString, single_argument_args, single_argument_result,
)

__all__ = [
    "CoreGetServicesArgs", "CoreGetServicesResult",
    "CoreGetMethodsArgs", "CoreGetMethodsResult",
    "CoreGetJobsItem",
    "CoreGetJobsAddedEvent", "CoreGetJobsChangedEvent",
    "CoreResizeShellArgs", "CoreResizeShellResult",
    "CoreJobDownloadLogsArgs", "CoreJobDownloadLogsResult",
    "CoreJobWaitArgs", "CoreJobWaitResult",
    "CoreJobAbortArgs", "CoreJobAbortResult",
    "CorePingArgs", "CorePingResult",
    "CorePingRemoteArgs", "CorePingRemoteResult",
    "CoreArpArgs", "CoreArpResult",
    "CoreDownloadArgs", "CoreDownloadResult",
    "CoreDebugArgs", "CoreDebugResult",
    "CoreBulkArgs", "CoreBulkResult",
    "CoreSetOptionsArgs", "CoreSetOptionsResult",
    "CoreSubscribeArgs", "CoreSubscribeResult",
    "CoreUnsubscribeArgs", "CoreUnsubscribeResult",
]


class CoreGetServicesArgs(BaseModel):
    target: Literal['WS', 'CLI', 'REST'] = 'WS'
    """Target interface to get services for.

    `WS` for WebSocket, `CLI` for command line, `REST` for HTTP API."""


class CoreGetServicesResult(BaseModel):
    result: dict[str, Any]
    """Object mapping service names to their configuration and available methods."""


class CoreGetMethodsArgs(BaseModel):
    service: str | None = None
    """Filters the result for a single service."""
    target: Literal['WS', 'CLI', 'REST'] = 'WS'
    """Target interface to get methods for.

    `WS` for WebSocket, `CLI` for command line, `REST` for HTTP API."""


class CoreGetMethodsResult(BaseModel):
    result: dict[str, Any]
    """Object mapping method names to their signatures, documentation, and metadata."""


class CoreGetJobsItemProgress(BaseModel):
    percent: int | None
    """Completion percentage of the job. `null` if not available."""
    description: LongString | None
    """Human-readable description of the current progress. `null` if not available."""
    extra: Any
    """Additional progress information specific to the job type."""


class CoreGetJobsItemExcInfo(BaseModel):
    repr: LongString | None
    """String representation of the exception. `null` if no exception occurred."""
    type: str | None
    """Exception type name. `null` if no exception occurred."""
    errno: int | None
    """System error number if applicable. `null` otherwise."""
    extra: Any
    """Additional exception information."""


class CoreGetJobsItemCredentials(BaseModel):
    type: str
    """Authentication type used for the job."""
    data: dict
    """Authentication data and credentials for the job."""


class CoreGetJobsItem(BaseModel):
    id: int
    """Unique identifier for this job."""
    message_ids: list
    """Array of message IDs associated with this job."""
    method: str
    """Name of the method/service being executed by this job."""
    arguments: list
    """Array of arguments passed to the job method."""
    transient: bool
    """Whether this is a temporary job that will be automatically cleaned up."""
    description: LongString | None
    """Human-readable description of what this job does. `null` if not provided."""
    abortable: bool
    """Whether this job can be cancelled/aborted."""
    logs_path: str | None
    """File system path to detailed job logs. `null` if no logs available."""
    logs_excerpt: LongString | None
    """Brief excerpt from job logs for quick preview. `null` if no logs available."""
    progress: CoreGetJobsItemProgress
    """Current progress information for the job."""
    result: Any
    """The result data returned by the job upon successful completion."""
    result_encoding_error: Any
    """Encoding error information if result serialization failed."""
    error: LongString | None
    """Error message if the job failed. `null` if no error occurred."""
    exception: LongString | None
    """Exception details if the job encountered an exception. `null` if no exception occurred."""
    exc_info: CoreGetJobsItemExcInfo | None
    """Detailed exception information. `null` if no exception occurred."""
    state: str = Field(examples=["WAITING", "RUNNING", "SUCCESS", "FAILED", "ABORTED"])
    """Current execution state of the job."""
    time_started: datetime | None
    """Timestamp when the job started execution. `null` if not yet started."""
    time_finished: datetime | None
    """Timestamp when the job completed execution. `null` if still running or not started."""
    credentials: CoreGetJobsItemCredentials | None
    """Authentication credentials used for this job. `null` if no authentication required."""


class CoreGetJobsAddedEvent(BaseModel):
    id: int
    """ID of the job that was added."""
    fields: CoreGetJobsItem
    """Complete job information for the newly added job."""


class CoreGetJobsChangedEvent(BaseModel):
    id: int
    """ID of the job that was updated."""
    fields: CoreGetJobsItem
    """Updated job information with changes."""


class CoreResizeShellArgs(BaseModel):
    id: str
    """Shell session identifier."""
    cols: int
    """New terminal width in columns."""
    rows: int
    """New terminal height in rows."""


class CoreResizeShellResult(BaseModel):
    result: None
    """Returns `null` when the shell is successfully resized."""


class CoreJobDownloadLogsArgs(BaseModel):
    id: int
    """ID of the job to download logs for."""
    filename: str
    """Filename for the downloaded log file."""
    buffered: bool = False
    """Whether to buffer the entire log file before download."""


class CoreJobDownloadLogsResult(BaseModel):
    result: str
    """URL for downloading the job log file."""


class CoreJobWaitArgs(BaseModel):
    id: int
    """ID of the job to wait for completion."""


class CoreJobWaitResult(BaseModel):
    result: Any
    """The result data returned by the completed job."""


class CoreJobAbortArgs(BaseModel):
    id: int
    """ID of the job to abort."""


class CoreJobAbortResult(BaseModel):
    result: None
    """Returns `null` when the job is successfully aborted."""


class CorePingArgs(BaseModel):
    pass


class CorePingResult(BaseModel):
    result: Literal["pong"]
    """Always returns `pong` to confirm system responsiveness."""


@single_argument_args("options")
class CorePingRemoteArgs(BaseModel):
    type: Literal["ICMP", "ICMPV4", "ICMPV6"] = "ICMP"
    """Ping protocol type to use.

    * `ICMP`: Auto-detect IPv4 or IPv6 based on hostname
    * `ICMPV4`: Force IPv4 ping
    * `ICMPV6`: Force IPv6 ping
    """
    hostname: str
    """Target hostname or IP address to ping."""
    timeout: int = Field(default=4, ge=1, le=60)
    """Timeout in seconds for each ping attempt."""
    count: int | None = None
    """Number of ping packets to send or `null` for default."""
    interface: str | None = None
    """Network interface to use for pinging or `null` for default."""
    interval: str | None = None
    """Interval between ping packets or `null` for default."""


class CorePingRemoteResult(BaseModel):
    result: bool
    """Returns `true` if the remote host responded to ping, `false` otherwise."""


@single_argument_args("options")
class CoreArpArgs(BaseModel):
    ip: str | None = None
    """IP address to look up in ARP table or `null` for all entries."""
    interface: str | None = None
    """Network interface to query or `null` for all interfaces."""


class CoreArpResult(BaseModel):
    result: dict[str, str]
    """Object mapping IP addresses to MAC addresses from the ARP table."""


class CoreDownloadArgs(BaseModel):
    method: str
    """Method name to execute for generating download content."""
    args: list
    """Array of arguments to pass to the method."""
    filename: str
    """Filename for the downloaded file."""
    buffered: bool = False
    """Non-`buffered` downloads will allow job to write to pipe as soon as download URL is requested, job will stay \
    blocked meanwhile. `buffered` downloads must wait for job to complete before requesting download URL, job's \
    pipe output will be buffered to ramfs."""


class CoreDownloadResult(BaseModel):
    result: tuple[int, str]
    """Job ID and the URL for download."""


@single_argument_args("options")
class CoreDebugArgs(BaseModel):
    bind_address: str = "0.0.0.0"
    """IP address to bind the debug server to."""
    bind_port: int = 3000
    """Port number to bind the debug server to."""
    threaded: bool = False
    """Whether to enable threaded debugging support."""


class CoreDebugResult(BaseModel):
    result: None
    """Returns `null` when the debug server is successfully started."""


class CoreBulkArgs(BaseModel):
    method: str
    """Method name to execute for each parameter set."""
    params: list[list]
    """Array of parameter arrays, each representing one method call."""
    description: str | None = None
    """Format string for job progress (e.g. \"Deleting snapshot {0[dataset]}@{0[name]}\")."""


class CoreBulkResultItem(BaseModel):
    job_id: int | None
    """Job ID for this bulk operation item or `null` if it failed to start."""
    error: LongString | None
    """Error message if this item failed or `null` on success."""
    result: Any
    """Result data returned by this bulk operation item."""


class CoreBulkResult(BaseModel):
    result: list[CoreBulkResultItem]
    """Array of results for each bulk operation item."""


class CoreOptions(BaseModel, metaclass=ForUpdateMetaclass):
    # We can't use `extra="forbid"` here because newer version clients might try to set more options than we support
    model_config = ConfigDict(
        strict=True,
        str_max_length=1024,
        use_attribute_docstrings=True,
        extra="ignore",
    )

    legacy_jobs: bool
    """Whether to enable legacy job behavior for backward compatibility."""
    private_methods: bool
    """Whether to expose private methods in API introspection."""
    py_exceptions: bool
    """Whether to include Python exception details in error responses."""


class CoreSetOptionsArgs(BaseModel):
    options: CoreOptions
    """Core system options to update."""


class CoreSetOptionsResult(BaseModel):
    result: CoreOptions
    """The updated core system options."""

    @classmethod
    def to_previous(cls, value):
        return {"result": None}


class CoreSubscribeArgs(BaseModel):
    event: str
    """Event name to subscribe to for real-time updates."""


CoreSubscribeResult = single_argument_result(str, "CoreSubscribeResult")


class CoreUnsubscribeArgs(BaseModel):
    id_: str
    """Subscription ID to cancel."""


CoreUnsubscribeResult = single_argument_result(None, "CoreUnsubscribeResult")
