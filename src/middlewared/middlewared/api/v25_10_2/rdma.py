from middlewared.api.base import BaseModel
from typing import Literal

__all__ = [
    "RdmaLinkConfig",
    "RDMAGetCardChoicesArgs", "RDMAGetCardChoicesResult",
    "RDMACapableProtocolsArgs", "RDMACapableProtocolsResult"
]


class RdmaLinkConfig(BaseModel):
    rdma: str
    """Name of the RDMA device."""
    netdev: str
    """Name of the corresponding network device."""


class RDMAGetCardChoicesArgs(BaseModel):
    pass


class RdmaCardConfig(BaseModel):
    name: str
    """Name of the RDMA card."""
    serial: str
    """Serial number of the RDMA card."""
    product: str
    """Product name of the RDMA card."""
    part_number: str
    """Part number of the RDMA card."""
    links: list[RdmaLinkConfig]
    """Array of RDMA link configurations available on this card."""


class RDMAGetCardChoicesResult(BaseModel):
    result: list[RdmaCardConfig]
    """Array of RDMA cards available on the system."""


class RDMACapableProtocolsArgs(BaseModel):
    pass


class RDMACapableProtocolsResult(BaseModel):
    result: list[Literal["ISER", "NFS", "NVMET"]]
    """Array of protocols that support RDMA acceleration."""
