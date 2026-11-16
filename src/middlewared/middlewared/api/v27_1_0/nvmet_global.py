
from pydantic import Field

from middlewared.api.base import NQN, BaseModel, Excluded, ForUpdateMetaclass, excluded_field, single_argument_args

__all__ = [
    "NVMetGlobalEntry",
    "NVMetGlobalUpdateArgs",
    "NVMetGlobalUpdateResult",
    "NVMetGlobalSessionsItem"
]


class NVMetGlobalEntry(BaseModel):
    id: int = Field(description="Unique identifier for the NVMe-oF global configuration.")
    basenqn: str = Field(
        description=(
            "NQN to be used as the prefix on the creation of a subsystem, if a subnqn is not supplied to "
            "`nvmet.subsys.create`.\n"
            "\n"
            "Modifying this value will *not* change the subnqn of any existing subsystems."
        ),
    )
    kernel: bool = Field(description="Select the NVMe-oF backend.")
    ana: bool = Field(description="Asymmetric Namespace Access (ANA) enabled.")
    rdma: bool = Field(
        description=(
            "RDMA is enabled for NVMe-oF.\n"
            "\n"
            "Enabling is limited to TrueNAS Enterprise-licensed systems and requires the system and network environment"
            " have Remote Direct Memory Access (RDMA)-capable hardware.\n"
            "\n"
            "Once enabled one or more `ports` may be configured with RDMA selected as the transport. See "
            "`nvmet.port.create`."
        ),
    )
    xport_referral: bool = Field(
        description=(
            "Controls whether cross-port referrals will be generated for ports on this TrueNAS.\n"
            "\n"
            "If ANA is active then referrals will always be generated between the peer ports on each TrueNAS controller"
            " node."
        ),
    )


@single_argument_args('nvmet_update')
class NVMetGlobalUpdateArgs(NVMetGlobalEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    basenqn: NQN = Field(
        description=(
            "NQN to be used as the prefix on the creation of a subsystem, if a subnqn is not supplied to "
            "`nvmet.subsys.create`.\n"
            "\n"
            "Modifying this value will *not* change the subnqn of any existing subsystems."
        ),
    )


class NVMetGlobalUpdateResult(BaseModel):
    result: NVMetGlobalEntry = Field(description="The updated NVMe-oF global configuration.")


class NVMetGlobalSessionsItem(BaseModel):
    host_traddr: str = Field(description="Address of the connected host. For example an IP address.")
    hostnqn: str = Field(description="NQN of the connected host.")
    subsys_id: int = Field(description="`id` of the subsystem on this TrueNAS that the host is connected to.")
    port_id: int = Field(description="`id` of the port on this TrueNAS through which the host is connected.")
    ctrl: int = Field(description="NVMe controller number.")
