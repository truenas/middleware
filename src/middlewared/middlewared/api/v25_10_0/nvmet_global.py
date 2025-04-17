from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, excluded_field, single_argument_args
from .common import QueryFilters, QueryOptions

__all__ = [
    "NVMetGlobalEntry",
    "NVMetGlobalUpdateArgs",
    "NVMetGlobalUpdateResult",
    "NVMetGlobalAnaEnabledArgs",
    "NVMetGlobalAnaEnabledResult",
    "NVMetGlobalRDMAEnabledArgs",
    "NVMetGlobalRDMAEnabledResult",
    "NVMetGlobalSessionsArgs",
    "NVMetGlobalSessionsResult",
]


class NVMetGlobalEntry(BaseModel):
    id: int
    basenqn: str
    kernel: bool = True
    ana: bool = False
    rdma: bool = False
    xport_referral: bool = True


@single_argument_args('nvmet_update')
class NVMetGlobalUpdateArgs(NVMetGlobalEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class NVMetGlobalUpdateResult(BaseModel):
    result: NVMetGlobalEntry


class NVMetGlobalAnaEnabledArgs(BaseModel):
    pass


class NVMetGlobalAnaEnabledResult(BaseModel):
    result: bool


class NVMetGlobalRDMAEnabledArgs(BaseModel):
    pass


class NVMetGlobalRDMAEnabledResult(BaseModel):
    result: bool


class NVMetSession(BaseModel):
    host_traddr: str
    hostnqn: str
    subsys_id: int
    port_id: int
    ctrl: int


class NVMetGlobalSessionsArgs(BaseModel):
    query_filters: QueryFilters = []
    query_options: QueryOptions = QueryOptions()


class NVMetGlobalSessionsResult(BaseModel):
    result: list[NVMetSession]
