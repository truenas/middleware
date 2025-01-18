from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_args
from .common import QueryFilters, QueryOptions

__all__ = [
    "IscsiGlobalEntry",
    "IscsiGlobalUpdateArgs",
    "IscsiGlobalUpdateResult",
    "IscsiGlobalAluaEnabledArgs",
    "IscsiGlobalAluaEnabledResult",
    "IscsiGlobalClientCountArgs",
    "IscsiGlobalClientCountResult",
    "IscsiGlobalSessionsArgs",
    "IscsiGlobalSessionsResult"
]


class IscsiGlobalEntry(BaseModel):
    id: int
    basename: str
    isns_servers: list[str]
    listen_port: int = Field(ge=1025, le=65535, default=3260)
    pool_avail_threshold: int | None = Field(ge=1, le=99, default=None)
    alua: bool


@single_argument_args('iscsi_update')
class IscsiGlobalUpdateArgs(IscsiGlobalEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class IscsiGlobalUpdateResult(BaseModel):
    result: IscsiGlobalEntry


class IscsiGlobalAluaEnabledArgs(BaseModel):
    pass


class IscsiGlobalAluaEnabledResult(BaseModel):
    result: bool


class IscsiGlobalClientCountArgs(BaseModel):
    pass


class IscsiGlobalClientCountResult(BaseModel):
    result: int


class IscsiSession(BaseModel):
    initiator: str
    initiator_addr: str
    initiator_alias: str | None
    target: str
    target_alias: str
    header_digest: str | None
    data_digest: str | None
    max_data_segment_length: int | None
    max_receive_data_segment_length: int | None
    max_xmit_data_segment_length: int | None
    max_burst_length: int | None
    first_burst_length: int | None
    immediate_data: bool
    iser: bool
    offload: bool


class IscsiGlobalSessionsArgs(BaseModel):
    query_filters: QueryFilters = []
    query_options: QueryOptions = QueryOptions()


class IscsiGlobalSessionsResult(BaseModel):
    result: list[IscsiSession]
