from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_args


__all__ = [
    "ISCSIGlobalEntry",
    "ISCSIGlobalUpdateArgs",
    "ISCSIGlobalUpdateResult",
    "ISCSIGlobalAluaEnabledArgs",
    "ISCSIGlobalAluaEnabledResult",
    "ISCSIGlobalIserEnabledArgs",
    "ISCSIGlobalIserEnabledResult",
    "ISCSIGlobalClientCountArgs",
    "ISCSIGlobalClientCountResult",
    "ISCSIGlobalSessionsItem",
]


class ISCSIGlobalEntry(BaseModel):
    id: int
    """Unique identifier for the global iSCSI configuration."""
    basename: str
    """Base name prefix for iSCSI target IQNs."""
    isns_servers: list[str]
    """Array of iSNS (Internet Storage Name Service) server addresses."""
    listen_port: int = Field(ge=1025, le=65535, default=3260)
    """TCP port number for iSCSI connections."""
    pool_avail_threshold: int | None = Field(ge=1, le=99, default=None)
    """Pool available space threshold percentage or `null` to disable."""
    alua: bool
    """Whether Asymmetric Logical Unit Access (ALUA) is enabled. Enabling is limited to TrueNAS Enterprise-licensed \
    high availability systems. ALUA only works when configured on both the client and server."""
    iser: bool
    """Whether iSCSI Extensions for RDMA (iSER) are enabled. Enabling is limited to TrueNAS Enterprise-licensed \
    systems and requires the system and network environment have Remote Direct Memory Access (RDMA)-capable hardware."""
    direct_config: bool | None
    """Whether configuration is written into the kernel directly by middlewared."""


@single_argument_args('iscsi_update')
class ISCSIGlobalUpdateArgs(ISCSIGlobalEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ISCSIGlobalUpdateResult(BaseModel):
    result: ISCSIGlobalEntry
    """The updated global iSCSI configuration."""


class ISCSIGlobalAluaEnabledArgs(BaseModel):
    pass


class ISCSIGlobalAluaEnabledResult(BaseModel):
    result: bool
    """Returns `true` if ALUA is enabled, `false` otherwise."""


class ISCSIGlobalIserEnabledArgs(BaseModel):
    pass


class ISCSIGlobalIserEnabledResult(BaseModel):
    result: bool
    """Returns `true` if iSER is enabled, `false` otherwise."""


class ISCSIGlobalClientCountArgs(BaseModel):
    pass


class ISCSIGlobalClientCountResult(BaseModel):
    result: int
    """Number of currently connected iSCSI clients."""


class ISCSIGlobalSessionsItem(BaseModel):
    initiator: str
    """iSCSI Qualified Name (IQN) of the initiator."""
    initiator_addr: str
    """IP address of the initiator."""
    initiator_alias: str | None
    """Alias name of the initiator or `null` if not set."""
    target: str
    """iSCSI Qualified Name (IQN) of the target."""
    target_alias: str
    """Alias name of the target."""
    header_digest: str | None
    """Header digest algorithm used for the session or `null`."""
    data_digest: str | None
    """Data digest algorithm used for the session or `null`."""
    max_data_segment_length: int | None
    """Maximum data segment length for the session or `null`."""
    max_receive_data_segment_length: int | None
    """Maximum receive data segment length or `null`."""
    max_xmit_data_segment_length: int | None
    """Maximum transmit data segment length or `null`."""
    max_burst_length: int | None
    """Maximum burst length for the session or `null`."""
    first_burst_length: int | None
    """First burst length for the session or `null`."""
    immediate_data: bool
    """Whether immediate data transfer is enabled."""
    iser: bool
    """Whether this session is using iSER (iSCSI Extensions for RDMA)."""
    offload: bool
    """Whether hardware offload is enabled for this session."""
