from typing import Literal, Optional

from pydantic import IPvAnyAddress, field_validator

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass

__all__ = [
    "RdmaInterfaceEntry",
    "RdmaInterfaceCreateArgs",
    "RdmaInterfaceCreateResult",
    "RdmaInterfaceUpdateArgs",
    "RdmaInterfaceUpdateResult",
    "RdmaInterfaceDeleteArgs",
    "RdmaInterfaceDeleteResult",
]


class RdmaInterfaceEntry(BaseModel):
    id: str
    node: str = ''
    ifname: str
    address: IPvAnyAddress
    prefixlen: int
    mtu: int = 5000

    @field_validator('address')
    @classmethod
    def normalize_address(cls, value: IPvAnyAddress) -> str:
        return str(value.ip)


class RdmaInterfaceCreateCheck(BaseModel):
    ping_ip: str
    ping_mac: str


class RdmaInterfaceCreate(RdmaInterfaceEntry):
    id: Excluded = excluded_field()
    check: Optional[RdmaInterfaceCreateCheck] = None


class RdmaInterfaceCreateArgs(BaseModel):
    data: RdmaInterfaceCreate


class RdmaInterfaceCreateResult(BaseModel):
    result: RdmaInterfaceEntry


class RdmaInterfaceUpdate(RdmaInterfaceCreate, metaclass=ForUpdateMetaclass):
    pass


class RdmaInterfaceUpdateArgs(BaseModel):
    id: int
    data: RdmaInterfaceUpdate


class RdmaInterfaceUpdateResult(BaseModel):
    result: RdmaInterfaceEntry


class RdmaInterfaceDeleteArgs(BaseModel):
    id: int


class RdmaInterfaceDeleteResult(BaseModel):
    result: Literal[True]
