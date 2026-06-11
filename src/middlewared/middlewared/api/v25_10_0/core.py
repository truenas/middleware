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
    target: Literal['WS', 'CLI', 'REST'] = Field(
        default='WS',
        description=(
            "Target interface to get services for.\n"
            "\n"
            "`WS` for WebSocket, `CLI` for command line, `REST` for HTTP API."
        ),
    )


class CoreGetServicesResult(BaseModel):
    result: dict[str, Any] = Field(
        description="Object mapping service names to their configuration and available methods.",
    )


class CoreGetMethodsArgs(BaseModel):
    service: str | None = Field(default=None, description="Filters the result for a single service.")
    target: Literal['WS', 'CLI', 'REST'] = Field(
        default='WS',
        description=(
            "Target interface to get methods for.\n"
            "\n"
            "`WS` for WebSocket, `CLI` for command line, `REST` for HTTP API."
        ),
    )


class CoreGetMethodsResult(BaseModel):
    result: dict[str, Any] = Field(
        description="Object mapping method names to their signatures, documentation, and metadata.",
    )


class CoreGetJobsItemProgress(BaseModel):
    percent: int | None = Field(description="Completion percentage of the job. `null` if not available.")
    description: LongString | None = Field(
        description="Human-readable description of the current progress. `null` if not available.",
    )
    extra: Any = Field(description="Additional progress information specific to the job type.")


class CoreGetJobsItemExcInfo(BaseModel):
    repr: LongString | None = Field(
        description="String representation of the exception. `null` if no exception occurred.",
    )
    type: str | None = Field(description="Exception type name. `null` if no exception occurred.")
    errno: int | None = Field(description="System error number if applicable. `null` otherwise.")
    extra: Any = Field(description="Additional exception information.")


class CoreGetJobsItemCredentials(BaseModel):
    type: str = Field(description="Authentication type used for the job.")
    data: dict = Field(description="Authentication data and credentials for the job.")


class CoreGetJobsItem(BaseModel):
    id: int = Field(description="Unique identifier for this job.")
    message_ids: list = Field(description="Array of message IDs associated with this job.")
    method: str = Field(description="Name of the method/service being executed by this job.")
    arguments: list = Field(description="Array of arguments passed to the job method.")
    transient: bool = Field(description="Whether this is a temporary job that will be automatically cleaned up.")
    description: LongString | None = Field(
        description="Human-readable description of what this job does. `null` if not provided.",
    )
    abortable: bool = Field(description="Whether this job can be cancelled/aborted.")
    logs_path: str | None = Field(description="File system path to detailed job logs. `null` if no logs available.")
    logs_excerpt: LongString | None = Field(
        description="Brief excerpt from job logs for quick preview. `null` if no logs available.",
    )
    progress: CoreGetJobsItemProgress = Field(description="Current progress information for the job.")
    result: Any = Field(description="The result data returned by the job upon successful completion.")
    result_encoding_error: Any = Field(description="Encoding error information if result serialization failed.")
    error: LongString | None = Field(description="Error message if the job failed. `null` if no error occurred.")
    exception: LongString | None = Field(
        description="Exception details if the job encountered an exception. `null` if no exception occurred.",
    )
    exc_info: CoreGetJobsItemExcInfo | None = Field(
        description="Detailed exception information. `null` if no exception occurred.",
    )
    state: str = Field(
        examples=["WAITING", "RUNNING", "SUCCESS", "FAILED", "ABORTED"],
        description="Current execution state of the job.",
    )
    time_started: datetime | None = Field(
        description="Timestamp when the job started execution. `null` if not yet started.",
    )
    time_finished: datetime | None = Field(
        description="Timestamp when the job completed execution. `null` if still running or not started.",
    )
    credentials: CoreGetJobsItemCredentials | None = Field(
        description="Authentication credentials used for this job. `null` if no authentication required.",
    )


class CoreGetJobsAddedEvent(BaseModel):
    id: int = Field(description="ID of the job that was added.")
    fields: CoreGetJobsItem = Field(description="Complete job information for the newly added job.")


class CoreGetJobsChangedEvent(BaseModel):
    id: int = Field(description="ID of the job that was updated.")
    fields: CoreGetJobsItem = Field(description="Updated job information with changes.")


class CoreResizeShellArgs(BaseModel):
    id: str = Field(description="Shell session identifier.")
    cols: int = Field(description="New terminal width in columns.")
    rows: int = Field(description="New terminal height in rows.")


class CoreResizeShellResult(BaseModel):
    result: None = Field(description="Returns `null` when the shell is successfully resized.")


class CoreJobDownloadLogsArgs(BaseModel):
    id: int = Field(description="ID of the job to download logs for.")
    filename: str = Field(description="Filename for the downloaded log file.")
    buffered: bool = Field(default=False, description="Whether to buffer the entire log file before download.")


class CoreJobDownloadLogsResult(BaseModel):
    result: str = Field(description="URL for downloading the job log file.")


class CoreJobWaitArgs(BaseModel):
    id: int = Field(description="ID of the job to wait for completion.")


class CoreJobWaitResult(BaseModel):
    result: Any = Field(description="The result data returned by the completed job.")


class CoreJobAbortArgs(BaseModel):
    id: int = Field(description="ID of the job to abort.")


class CoreJobAbortResult(BaseModel):
    result: None = Field(description="Returns `null` when the job is successfully aborted.")


class CorePingArgs(BaseModel):
    pass


class CorePingResult(BaseModel):
    result: Literal["pong"] = Field(description="Always returns `pong` to confirm system responsiveness.")


@single_argument_args("options")
class CorePingRemoteArgs(BaseModel):
    type: Literal["ICMP", "ICMPV4", "ICMPV6"] = Field(
        default="ICMP",
        description=(
            "Ping protocol type to use.\n"
            "\n"
            "* `ICMP`: Auto-detect IPv4 or IPv6 based on hostname\n"
            "* `ICMPV4`: Force IPv4 ping\n"
            "* `ICMPV6`: Force IPv6 ping"
        ),
    )
    hostname: str = Field(description="Target hostname or IP address to ping.")
    timeout: int = Field(default=4, ge=1, le=60, description="Timeout in seconds for each ping attempt.")
    count: int | None = Field(default=None, description="Number of ping packets to send or `null` for default.")
    interface: str | None = Field(
        default=None,
        description="Network interface to use for pinging or `null` for default.",
    )
    interval: str | None = Field(default=None, description="Interval between ping packets or `null` for default.")


class CorePingRemoteResult(BaseModel):
    result: bool = Field(description="Returns `true` if the remote host responded to ping, `false` otherwise.")


@single_argument_args("options")
class CoreArpArgs(BaseModel):
    ip: str | None = Field(default=None, description="IP address to look up in ARP table or `null` for all entries.")
    interface: str | None = Field(default=None, description="Network interface to query or `null` for all interfaces.")


class CoreArpResult(BaseModel):
    result: dict[str, str] = Field(description="Object mapping IP addresses to MAC addresses from the ARP table.")


class CoreDownloadArgs(BaseModel):
    method: str = Field(description="Method name to execute for generating download content.")
    args: list = Field(description="Array of arguments to pass to the method.")
    filename: str = Field(description="Filename for the downloaded file.")
    buffered: bool = Field(
        default=False,
        description=(
            "Non-`buffered` downloads will allow job to write to pipe as soon as download URL is requested, job will "
            "stay blocked meanwhile. `buffered` downloads must wait for job to complete before requesting download URL,"
            " job's pipe output will be buffered to ramfs."
        ),
    )


class CoreDownloadResult(BaseModel):
    result: tuple[int, str] = Field(description="Job ID and the URL for download.")


@single_argument_args("options")
class CoreDebugArgs(BaseModel):
    bind_address: str = Field(default="0.0.0.0", description="IP address to bind the debug server to.")
    bind_port: int = Field(default=3000, description="Port number to bind the debug server to.")
    threaded: bool = Field(default=False, description="Whether to enable threaded debugging support.")


class CoreDebugResult(BaseModel):
    result: None = Field(description="Returns `null` when the debug server is successfully started.")


class CoreBulkArgs(BaseModel):
    method: str = Field(description="Method name to execute for each parameter set.")
    params: list[list] = Field(description="Array of parameter arrays, each representing one method call.")
    description: str | None = Field(
        default=None,
        description="Format string for job progress (e.g. \"Deleting snapshot {0[dataset]}@{0[name]}\").",
    )


class CoreBulkResultItem(BaseModel):
    job_id: int | None = Field(description="Job ID for this bulk operation item or `null` if it failed to start.")
    error: LongString | None = Field(description="Error message if this item failed or `null` on success.")
    result: Any = Field(description="Result data returned by this bulk operation item.")


class CoreBulkResult(BaseModel):
    result: list[CoreBulkResultItem] = Field(description="Array of results for each bulk operation item.")


class CoreOptions(BaseModel, metaclass=ForUpdateMetaclass):
    # We can't use `extra="forbid"` here because newer version clients might try to set more options than we support
    model_config = ConfigDict(
        strict=True,
        str_max_length=1024,
        extra="ignore",
    )

    legacy_jobs: bool = Field(description="Whether to enable legacy job behavior for backward compatibility.")
    private_methods: bool = Field(description="Whether to expose private methods in API introspection.")
    py_exceptions: bool = Field(description="Whether to include Python exception details in error responses.")


class CoreSetOptionsArgs(BaseModel):
    options: CoreOptions = Field(description="Core system options to update.")


class CoreSetOptionsResult(BaseModel):
    result: CoreOptions = Field(description="The updated core system options.")

    @classmethod
    def to_previous(cls, value):
        return {"result": None}


class CoreSubscribeArgs(BaseModel):
    event: str = Field(description="Event name to subscribe to for real-time updates.")


CoreSubscribeResult = single_argument_result(str, "CoreSubscribeResult")


class CoreUnsubscribeArgs(BaseModel):
    id_: str = Field(description="Subscription ID to cancel.")


CoreUnsubscribeResult = single_argument_result(None, "CoreUnsubscribeResult")
