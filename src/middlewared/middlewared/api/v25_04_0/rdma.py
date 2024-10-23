from middlewared.api.base import BaseModel, single_argument_result
from typing import Literal

__all__ = [
    "RdmaLinkConfigArgs", "RdmaLinkConfigResult",
    "RdmaCardConfigArgs", "RdmaCardConfigResult",
    "RdmaCapableServicesArgs", "RdmaCapableServicesResult"
]


class RdmaLinkConfigArgs(BaseModel):
    all: bool = False


class RdmaLinkConfig(BaseModel):
    rdma: str
    netdev: str


class RdmaLinkConfigResult(BaseModel):
    result: list[RdmaLinkConfig]


class RdmaCardConfigArgs(BaseModel):
    pass


@single_argument_result
class RdmaCardConfigResult(BaseModel):
    serial: str
    product: str
    part_number: str
    links: list[RdmaLinkConfig]


class RdmaCapableServicesArgs(BaseModel):
    pass


class RdmaCapableServicesResult(BaseModel):
    result: list[Literal["NFS"]]
