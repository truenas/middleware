from middlewared.api.base import BaseModel
from typing import Literal

__all__ = [
    "RdmaLinkConfig",
    "RDMAGetCardChoicesArgs", "RDMAGetCardChoicesResult",
    "RDMACapableProtocolsArgs", "RDMACapableProtocolsResult"
]


class RdmaLinkConfig(BaseModel):
    rdma: str
    netdev: str


class RDMAGetCardChoicesArgs(BaseModel):
    pass


class RdmaCardConfig(BaseModel):
    name: str
    serial: str
    product: str
    part_number: str
    links: list[RdmaLinkConfig]


class RDMAGetCardChoicesResult(BaseModel):
    result: list[RdmaCardConfig]


class RDMACapableProtocolsArgs(BaseModel):
    pass


class RDMACapableProtocolsResult(BaseModel):
    result: list[Literal["ISER", "NFS", "NVMET"]]
