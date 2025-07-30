from abc import ABC
from typing import Literal, TypeAlias

from pydantic import Field, field_validator

from middlewared.api.base import IPvAnyAddress, BaseModel, Excluded, ForUpdateMetaclass, NonEmptyString, excluded_field

__all__ = [
    "NVMetPortEntry",
    "NVMetPortCreateArgs",
    "NVMetPortCreateResult",
    "NVMetPortUpdateArgs",
    "NVMetPortUpdateResult",
    "NVMetPortDeleteArgs",
    "NVMetPortDeleteResult",
    "NVMetPortTransportAddressChoicesArgs",
    "NVMetPortTransportAddressChoicesResult"
]


FabricTransportType: TypeAlias = Literal['TCP', 'RDMA', 'FC']
AddressFamily: TypeAlias = Literal['IPV4', 'IPV6', 'FC']


class NVMetPortEntry(BaseModel):
    id: int
    """Unique identifier for the NVMe-oF port."""
    index: int
    """ Index of the port, for internal use. """
    addr_trtype: FabricTransportType
    """ Fabric transport technology name. """
    addr_trsvcid: int | NonEmptyString | None
    """ Transport-specific TRSVCID field.  When configured for TCP/IP or RDMA this will be the port number. """
    addr_traddr: str
    """
    A transport-specific field identifying the NVMe host port to use for the connection to the controller.

    For TCP or RDMA transports, this will be an IPv4 or IPv6 address.
    """
    addr_adrfam: AddressFamily
    """ Address family."""
    inline_data_size: int | None = None
    """Maximum size for inline data transfers or `null` for default."""
    max_queue_size: int | None = None
    """Maximum number of queue entries or `null` for default."""
    pi_enable: bool | None = None
    """Whether Protection Information (PI) is enabled or `null` for default."""
    # Not supported at this time
    # addr_tsas: str | None = None
    # """ Transport Specific Address Subtype. """
    # addr_treq: Literal['Not specified', 'Required', 'Not Required'] = 'Not specified'
    # """ Transport Requirements codes for Discovery Log Page entry TREQ field. """
    enabled: bool = True
    """ Port enabled.  When NVMe target is running, cannot make changes to an enabled port. """


class NVMetPortCreateTemplate(NVMetPortEntry, ABC):
    id: Excluded = excluded_field()
    index: Excluded = excluded_field()
    addr_adrfam: Excluded = excluded_field()


class NVMetPortCreateRDMATCP(NVMetPortCreateTemplate):
    addr_trtype: Literal['TCP', 'RDMA']
    addr_trsvcid: int = Field(ge=1024, le=65535)
    addr_traddr: IPvAnyAddress

    @field_validator('addr_traddr')
    @classmethod
    def normalize_addr_traddr(cls, value: str) -> str:
        if not value:
            raise ValueError('addr_traddr is required')
        return value


class NVMetPortCreateFC(NVMetPortCreateTemplate):
    addr_trtype: Literal['FC']
    """Fabric transport technology name."""
    addr_traddr: NonEmptyString
    """A transport-specific field identifying the NVMe host port to use for the connection to the controller."""
    addr_trsvcid: Excluded = excluded_field()


class NVMetPortCreateArgs(BaseModel):
    nvmet_port_create: NVMetPortCreateRDMATCP | NVMetPortCreateFC = Field(discriminator='addr_trtype')
    """NVMe-oF port configuration data for creation (TCP/RDMA or Fibre Channel)."""


class NVMetPortCreateResult(BaseModel):
    result: NVMetPortEntry
    """The created NVMe-oF port configuration."""


class NVMetPortUpdateRDMATCP(NVMetPortCreateRDMATCP, metaclass=ForUpdateMetaclass):
    pass


class NVMetPortUpdateFC(NVMetPortCreateFC, metaclass=ForUpdateMetaclass):
    pass


class NVMetPortUpdateArgs(BaseModel):
    id: int
    """ID of the NVMe-oF port to update."""
    nvmet_port_update: NVMetPortUpdateRDMATCP | NVMetPortUpdateFC
    """Updated NVMe-oF port configuration data."""


class NVMetPortUpdateResult(BaseModel):
    result: NVMetPortEntry
    """The updated NVMe-oF port configuration."""


class NVMetPortDeleteOptions(BaseModel):
    force: bool = False
    """ Optional `boolean` to force port deletion, even if currently associated with one or more subsystems. """


class NVMetPortDeleteArgs(BaseModel):
    id: int
    """ID of the NVMe-oF port to delete."""
    options: NVMetPortDeleteOptions = Field(default_factory=NVMetPortDeleteOptions)
    """Options controlling port deletion behavior."""


class NVMetPortDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the NVMe-oF port is successfully deleted."""


class NVMetPortTransportAddressChoicesArgs(BaseModel):
    addr_trtype: FabricTransportType
    """ Fabric transport technology name.  """
    force_ana: bool = False
    """ Return information as if ANA was enabled. """


class NVMetPortTransportAddressChoicesResult(BaseModel):
    result: dict[str, str]
    """Object mapping transport addresses to their descriptions."""
