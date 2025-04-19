import ipaddress
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, NonEmptyString, excluded_field

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
    addr_traddr: NonEmptyString
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

    @model_validator(mode='after')
    def validate_nvmet_port(self):
        match self.addr_trtype:
            case 'TCP' | 'RDMA':
                try:
                    ipaddress.ip_address(self.addr_traddr)
                except ValueError:
                    raise ValueError('addr_traddr must be a valid IP address')
                if not isinstance(self.addr_trsvcid, int):
                    raise ValueError('For TCP or RDMA addr_trsvcid must be a port number integer')
                if self.addr_trsvcid < 1024 or self.addr_trsvcid > 65535:
                    raise ValueError('addr_trsvcid port number must be an integer in the range 1024..65535')

        return self


class NVMetPortCreate(NVMetPortEntry):
    id: Excluded = excluded_field()
    index: Excluded = excluded_field()
    addr_adrfam: Excluded = excluded_field()


class NVMetPortCreateArgs(BaseModel):
    nvmet_port_create: NVMetPortCreate


class NVMetPortCreateResult(BaseModel):
    result: NVMetPortEntry


class NVMetPortUpdate(NVMetPortCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetPortUpdateArgs(BaseModel):
    id: int
    nvmet_port_update: NVMetPortUpdate


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
