from middlewared.api.base import BaseModel
from typing import Literal

__all__ = [
    "RdmaLinkConfig",
    "RdmaCardConfigArgs", "RdmaCardConfigResult",
    "RdmaCapableProtocolsArgs", "RdmaCapableProtocolsResult"
]


class RdmaLinkConfig(BaseModel):
    rdma: str
    netdev: str


class RdmaCardConfigArgs(BaseModel):
    pass


class RdmaCardConfig(BaseModel):
    name: str
    serial: str
    product: str
    part_number: str
    links: list[RdmaLinkConfig]


class RdmaCardConfigResult(BaseModel):
    result: list[RdmaCardConfig]


class RdmaCapableProtocolsArgs(BaseModel):
    pass


class RdmaCapableProtocolsResult(BaseModel):
    result: list[Literal["ISER", "NFS"]]
