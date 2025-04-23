from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, excluded_field, single_argument_args

__all__ = [
    "NVMetGlobalEntry",
    "NVMetGlobalUpdateArgs",
    "NVMetGlobalUpdateResult",
    "NVMetGlobalAnaEnabledArgs",
    "NVMetGlobalAnaEnabledResult",
    "NVMetGlobalRDMAEnabledArgs",
    "NVMetGlobalRDMAEnabledResult",
    "NVMetSession"
]


class NVMetGlobalEntry(BaseModel):
    id: int
    basenqn: str
    """
    NQN to be used as the prefix on the creation of a subsystem, if a subnqn is not supplied to `nvmet.subsys.create`.

    Modifying this value will *not* change the subnqn of any existing subsystems.
    """
    kernel: bool = True
    """
    Select the NVMe-oF backend.
    """
    ana: bool = False
    """
    Asymmetric Namespace Access (ANA) enabled.
    """
    rdma: bool = False
    """
    RDMA is enabled for NVMe-oF.

    Enabling is limited to TrueNAS Enterprise-licensed systems and requires the system and network environment have Remote Direct Memory Access (RDMA)-capable hardware.

    Once enabled one or more `ports` may be configured with RDMA selected as the transport. See `nvmet.port.create`.
    """
    xport_referral: bool = True
    """
    Controls whether cross-port referrals will be generated for ports on this TrueNAS.

    If ANA is active then referrals will always be generated between the peer ports on each TrueNAS controller node.
    """


@single_argument_args('nvmet_update')
class NVMetGlobalUpdateArgs(NVMetGlobalEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class NVMetGlobalUpdateResult(BaseModel):
    result: NVMetGlobalEntry


class NVMetGlobalAnaEnabledArgs(BaseModel):
    pass


class NVMetGlobalAnaEnabledResult(BaseModel):
    result: bool
    """ `True` if Asymmetric Namespace Access (ANA) is enabled. """


class NVMetGlobalRDMAEnabledArgs(BaseModel):
    pass


class NVMetGlobalRDMAEnabledResult(BaseModel):
    result: bool
    """ `True` if Remote Direct Memory Access (RDMA) is enabled for NVMe-oF. """


class NVMetSession(BaseModel):
    host_traddr: str
    """ Address of the connected host. For example an IP address."""
    hostnqn: str
    """ NQN of the connected host. """
    subsys_id: int
    """ `id` of the subsystem on this TrueNAS that the host is connected to. """
    port_id: int
    """ `id` of the port on this TrueNAS through which the host is connected. """
    ctrl: int
    """ NVMe controller number. """
