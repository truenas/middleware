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
    index: int
    """ Index of the port, for internal use. """
    addr_trtype: FabricTransportType
    """ Fabric transport technology name. """
    addr_trsvcid: int | NonEmptyString
    """ Transport-specific TRSVCID field.  When configured for TCP/IP or RDMA this will be the port number. """
    addr_traddr: str
    """
    A transport-specific field identifying the NVMe host port to use for the connection to the controller.

    For TCP or RDMA transports, this will be an IPv4 or IPv6 address.
    """
    addr_adrfam: AddressFamily
    """ Address family."""
    inline_data_size: int | None = None
    max_queue_size: int | None = None
    pi_enable: bool | None = None
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
    addr_trsvcid: NonEmptyString
    addr_traddr: NonEmptyString


class NVMetPortCreateArgs(BaseModel):
    nvmet_port_create: NVMetPortCreateRDMATCP | NVMetPortCreateFC = Field(discriminator='addr_trtype')


class NVMetPortCreateResult(BaseModel):
    result: NVMetPortEntry


class NVMetPortUpdateRDMATCP(NVMetPortCreateRDMATCP, metaclass=ForUpdateMetaclass):
    pass


class NVMetPortUpdateFC(NVMetPortCreateFC, metaclass=ForUpdateMetaclass):
    pass


class NVMetPortUpdateArgs(BaseModel):
    id: int
    nvmet_port_update: NVMetPortUpdateRDMATCP | NVMetPortUpdateFC


class NVMetPortUpdateResult(BaseModel):
    result: NVMetPortEntry


class NVMetPortDeleteOptions(BaseModel):
    force: bool = False
    """ Optional `boolean` to force port deletion, even if currently associated with one or more subsystems. """


class NVMetPortDeleteArgs(BaseModel):
    id: int
    options: NVMetPortDeleteOptions = Field(default_factory=NVMetPortDeleteOptions)


class NVMetPortDeleteResult(BaseModel):
    result: Literal[True]


class NVMetPortTransportAddressChoicesArgs(BaseModel):
    addr_trtype: FabricTransportType
    """ Fabric transport technology name.  """
    force_ana: bool = False
    """ Return information as if ANA was enabled. """


class NVMetPortTransportAddressChoicesResult(BaseModel):
    result: dict[str, str]
