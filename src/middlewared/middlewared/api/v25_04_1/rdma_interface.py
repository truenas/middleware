from typing import Literal, Optional

from pydantic import IPvAnyAddress, field_validator

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass

__all__ = [
    "RDMAInterfaceEntry",
    "RdmaInterfaceCreateArgs",
    "RdmaInterfaceCreateResult",
    "RdmaInterfaceUpdateArgs",
    "RdmaInterfaceUpdateResult",
    "RdmaInterfaceDeleteArgs",
    "RdmaInterfaceDeleteResult",
]


class RDMAInterfaceEntry(BaseModel):
    id: str
    node: str = ''
    ifname: str
    address: IPvAnyAddress
    prefixlen: int
    mtu: int = 5000

    @field_validator('address')
    @classmethod
    def normalize_address(cls, value: IPvAnyAddress) -> str:
        return str(value)


class RdmaInterfaceCreateCheck(BaseModel):
    ping_ip: str
    ping_mac: str


class RdmaInterfaceCreate(RDMAInterfaceEntry):
    id: Excluded = excluded_field()
    check: Optional[RdmaInterfaceCreateCheck] = None


class RdmaInterfaceCreateArgs(BaseModel):
    data: RdmaInterfaceCreate


class RdmaInterfaceCreateResult(BaseModel):
    result: RDMAInterfaceEntry


class RdmaInterfaceUpdate(RdmaInterfaceCreate, metaclass=ForUpdateMetaclass):
    pass


class RdmaInterfaceUpdateArgs(BaseModel):
    id: int
    data: RdmaInterfaceUpdate


class RdmaInterfaceUpdateResult(BaseModel):
    result: RDMAInterfaceEntry


class RdmaInterfaceDeleteArgs(BaseModel):
    id: int


class RdmaInterfaceDeleteResult(BaseModel):
    result: Literal[True]
