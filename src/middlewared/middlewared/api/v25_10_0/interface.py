from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, IPv4Address, single_argument_args, NotRequired, UniqueList, IPvAnyAddress


__all__ = ["InterfaceEntry",]


class InterfaceAlias(BaseModel):
    type: Literal["INET", "INET6"] = "INET"
    address: IPvAnyAddress
    netmask: int


class InterfaceEntryStateAlias(InterfaceAlias):
    broadcast: str


class InterfaceEntryStatePort(BaseModel):
    name: str
    flags: list[str]


class InterfaceEntryState(BaseModel):
    name: str
    orig_name: str
    description: str
    mtu: int
    cloned: bool
    flags: list[str]
    nd6_flags: list
    capabilities: list
    link_state: str
    media_type: str
    media_subtype: str
    active_media_type: str
    active_media_subtype: str
    supported_media: list
    media_options: list | None
    link_address: str
    permanent_link_address: str | None
    hardware_link_address: str
    rx_queues: int
    tx_queues: int
    aliases: list[InterfaceEntryStateAlias]
    vrrp_config: list | None
    # lagg section
    protocol: str | None
    ports: list[InterfaceEntryStatePort]
    xmit_hash_policy: str | None = None
    lacpdu_rate: str | None = None
    # vlan section
    parent: str | None
    tag: int | None
    pcp: int | None


class InterfaceEntry(BaseModel):
    id: str
    name: str
    fake: bool
    type: str
    state: InterfaceEntryState
    aliases: list[InterfaceAlias]
    ipv4_dhcp: bool
    ipv6_auto: bool
    description: str
    mtu: int | None
    vlan_parent_interface: str | None
    vlan_tag: int | None
    vlan_pcp: int | None
    lag_protocol: str
    lag_ports: list[str]
    bridge_members: list[str]
    enable_learning: bool

    class Config:
        extra = "allow"


class InterfaceCommitOptions(BaseModel):
    rollback: bool = True
    checkin_timeout: int = 60


################   Args and Results   ###############


class InterfaceCancelRollbackArgs(BaseModel):
    pass


class InterfaceCancelRollbackResult(BaseModel):
    result: None


class InterfaceCheckinArgs(BaseModel):
    pass


class InterfaceCheckinResult(BaseModel):
    result: None


class InterfaceCheckinWaitingArgs(BaseModel):
    pass


class InterfaceCheckinWaitingResult(BaseModel):
    result: int | None


class InterfaceCommitArgs(BaseModel):
    options: InterfaceCommitOptions = Field(default_factory=InterfaceCommitOptions)


class InterfaceCommitResult(BaseModel):
    result: None


@single_argument_args("data")
class InterfaceCreateArgs(BaseModel):
    name: str = NotRequired
    description: str = ""
    type: Literal["BRIDGE", "LINK_AGGREGATION", "VLAN"]
    ipv4_dhcp: bool = False
    ipv6_auto: bool = False
    aliases: UniqueList[InterfaceAlias] = []


class InterfaceDefaultRouteWillBeRemovedArgs(BaseModel):
    pass


class InterfaceDefaultRouteWillBeRemovedResult(BaseModel):
    result: bool


class InterfaceHasPendingChangesArgs(BaseModel):
    pass


class InterfaceHasPendingChangesResult(BaseModel):
    result: bool


class InterfaceRollbackArgs(BaseModel):
    pass


class InterfaceRollbackResult(BaseModel):
    result: None


class InterfaceSaveDefaultRouteArgs(BaseModel):
    gateway: IPv4Address


class InterfaceSaveDefaultRouteResult(BaseModel):
    result: None


