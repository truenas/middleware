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


class CoreGetServicesResult(BaseModel):
    result: dict[str, Any]


class CoreGetMethodsArgs(BaseModel):
    service: str | None = None
    """Filters the result for a single service."""
    target: Literal['WS', 'CLI', 'REST'] = 'WS'


class CoreGetMethodsResult(BaseModel):
    result: dict[str, Any]


class CoreGetJobsItemProgress(BaseModel):
    percent: int | None
    description: LongString | None
    extra: Any


class CoreGetJobsItemExcInfo(BaseModel):
    repr: LongString | None
    type: str | None
    errno: int | None
    extra: Any


class CoreGetJobsItemCredentials(BaseModel):
    type: str
    data: dict


class CoreGetJobsItem(BaseModel):
    id: int
    message_ids: list
    method: str
    arguments: list
    transient: bool
    description: LongString | None
    abortable: bool
    logs_path: str | None
    logs_excerpt: LongString | None
    progress: CoreGetJobsItemProgress
    result: Any
    result_encoding_error: Any
    error: LongString | None
    exception: LongString | None
    exc_info: CoreGetJobsItemExcInfo | None
    state: str
    time_started: datetime | None
    time_finished: datetime | None
    credentials: CoreGetJobsItemCredentials | None


class CoreGetJobsAddedEvent(BaseModel):
    id: int
    fields: CoreGetJobsItem


class CoreGetJobsChangedEvent(BaseModel):
    id: int
    fields: CoreGetJobsItem


class CoreResizeShellArgs(BaseModel):
    id: str
    cols: int
    rows: int


class CoreResizeShellResult(BaseModel):
    result: None


class CoreJobDownloadLogsArgs(BaseModel):
    id: int
    filename: str
    buffered: bool = False


class CoreJobDownloadLogsResult(BaseModel):
    result: str


class CoreJobWaitArgs(BaseModel):
    id: int


class CoreJobWaitResult(BaseModel):
    result: Any


class CoreJobAbortArgs(BaseModel):
    id: int


class CoreJobAbortResult(BaseModel):
    result: None


class CorePingArgs(BaseModel):
    pass


class CorePingResult(BaseModel):
    result: Literal["pong"]


@single_argument_args("options")
class CorePingRemoteArgs(BaseModel):
    type: Literal["ICMP", "ICMPV4", "ICMPV6"] = "ICMP"
    hostname: str
    timeout: int = Field(default=4, ge=1, le=60)
    count: int | None = None
    interface: str | None = None
    interval: str | None = None


class CorePingRemoteResult(BaseModel):
    result: bool


@single_argument_args("options")
class CoreArpArgs(BaseModel):
    ip: str | None = None
    interface: str | None = None


class CoreArpResult(BaseModel):
    result: dict[str, str]


class CoreDownloadArgs(BaseModel):
    method: str
    args: list
    filename: str
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
    bind_port: int = 3000
    threaded: bool = False


class CoreDebugResult(BaseModel):
    result: None


class CoreBulkArgs(BaseModel):
    method: str
    params: list[list]
    description: str | None = None
    """Format string for job progress (e.g. \"Deleting snapshot {0[dataset]}@{0[name]}\")."""


class CoreBulkResultItem(BaseModel):
    job_id: int | None
    error: str | None
    result: Any


class CoreBulkResult(BaseModel):
    result: list[CoreBulkResultItem]


class CoreOptions(BaseModel, metaclass=ForUpdateMetaclass):
    # We can't use `extra="forbid"` here because newer version clients might try to set more options than we support
    model_config = ConfigDict(
        strict=True,
        str_max_length=1024,
        use_attribute_docstrings=True,
        extra="ignore",
    )

    legacy_jobs: bool
    private_methods: bool
    py_exceptions: bool


class CoreSetOptionsArgs(BaseModel):
    options: CoreOptions


class CoreSetOptionsResult(BaseModel):
    result: CoreOptions

    @classmethod
    def to_previous(cls, value):
        return {"result": None}


class CoreSubscribeArgs(BaseModel):
    event: str


CoreSubscribeResult = single_argument_result(str, "CoreSubscribeResult")


class CoreUnsubscribeArgs(BaseModel):
    id_: str


CoreUnsubscribeResult = single_argument_result(None, "CoreUnsubscribeResult")
