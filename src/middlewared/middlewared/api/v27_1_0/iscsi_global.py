
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
    id: int = Field(description="Unique identifier for the global iSCSI configuration.")
    basename: str = Field(description="Base name prefix for iSCSI target IQNs.")
    isns_servers: list[str] = Field(description="Array of iSNS (Internet Storage Name Service) server addresses.")
    listen_port: int = Field(ge=1025, le=65535, default=3260, description="TCP port number for iSCSI connections.")
    pool_avail_threshold: int | None = Field(
        ge=1,
        le=99,
        default=None,
        description="Pool available space threshold percentage or `null` to disable.",
    )
    alua: bool = Field(
        description=(
            "Whether Asymmetric Logical Unit Access (ALUA) is enabled. Enabling is limited to TrueNAS "
            "Enterprise-licensed high availability systems. ALUA only works when configured on both the client and "
            "server."
        ),
    )
    iser: bool = Field(
        description=(
            "Whether iSCSI Extensions for RDMA (iSER) are enabled. Enabling is limited to TrueNAS Enterprise-licensed "
            "systems and requires the system and network environment have Remote Direct Memory Access (RDMA)-capable "
            "hardware."
        ),
    )
    direct_config: bool | None = Field(
        description="Whether configuration is written into the kernel directly by middlewared.",
    )
    mode: int = Field(ge=0, le=1, description="Internal iSCSI operational mode.")


@single_argument_args('iscsi_update')
class ISCSIGlobalUpdateArgs(ISCSIGlobalEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ISCSIGlobalUpdateResult(BaseModel):
    result: ISCSIGlobalEntry = Field(description="The updated global iSCSI configuration.")


class ISCSIGlobalAluaEnabledArgs(BaseModel):
    pass


class ISCSIGlobalAluaEnabledResult(BaseModel):
    result: bool = Field(description="Returns `true` if ALUA is enabled, `false` otherwise.")


class ISCSIGlobalIserEnabledArgs(BaseModel):
    pass


class ISCSIGlobalIserEnabledResult(BaseModel):
    result: bool = Field(description="Returns `true` if iSER is enabled, `false` otherwise.")


class ISCSIGlobalClientCountArgs(BaseModel):
    pass


class ISCSIGlobalClientCountResult(BaseModel):
    result: int = Field(description="Number of currently connected iSCSI clients.")


class ISCSIGlobalSessionsItem(BaseModel):
    initiator: str = Field(description="iSCSI Qualified Name (IQN) of the initiator.")
    initiator_addr: str = Field(description="IP address of the initiator.")
    initiator_alias: str | None = Field(description="Alias name of the initiator or `null` if not set.")
    target: str = Field(description="iSCSI Qualified Name (IQN) of the target.")
    target_alias: str = Field(description="Alias name of the target.")
    header_digest: str | None = Field(description="Header digest algorithm used for the session or `null`.")
    data_digest: str | None = Field(description="Data digest algorithm used for the session or `null`.")
    max_data_segment_length: int | None = Field(description="Maximum data segment length for the session or `null`.")
    max_receive_data_segment_length: int | None = Field(description="Maximum receive data segment length or `null`.")
    max_xmit_data_segment_length: int | None = Field(description="Maximum transmit data segment length or `null`.")
    max_burst_length: int | None = Field(description="Maximum burst length for the session or `null`.")
    first_burst_length: int | None = Field(description="First burst length for the session or `null`.")
    immediate_data: bool = Field(description="Whether immediate data transfer is enabled.")
    iser: bool = Field(description="Whether this session is using iSER (iSCSI Extensions for RDMA).")
    offload: bool = Field(description="Whether hardware offload is enabled for this session.")
