from typing import Annotated, Literal

from pydantic.types import StringConstraints
from pydantic import EmailStr, Field, Secret

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_args
)

__all__ = ["SNMPEntry",
           "SNMPUpdateArgs", "SNMPUpdateResult"]


class SNMPEntry(BaseModel):
    location: str
    """A comment describing the physical location of the server."""
    contact: EmailStr | Annotated[str, StringConstraints(pattern=r'^[-_a-zA-Z0-9\s]*$')]
    """Contact information for the system administrator (email or name)."""
    traps: bool
    """Whether SNMP traps are enabled."""
    v3: bool
    """Whether SNMP version 3 is enabled.  Enabling version 3 also requires username, authtype and password."""
    community: str = Field(pattern=r'^[!\$%&()\+\-_={}\[\]<>,\.\?a-zA-Z0-9\s]*$', default='public')
    """SNMP community string for v1/v2c access. Allows \
        letters and numbers: a-zA-Z0-9  \
        special characters: !$%&()+-_={}[]<>,.?  \
        and spaces. Notable excluded characters: # / \\ @"""
    v3_username: str = Field(max_length=20)
    """Username for SNMP version 3 authentication."""
    v3_authtype: Literal['', 'MD5', 'SHA']
    """Authentication type for SNMP version 3 (empty string means no authentication)."""
    v3_password: Secret[str]
    """Password for SNMP version 3 authentication."""
    v3_privproto: Literal[None, 'AES', 'DES'] | None
    """Privacy protocol for SNMP version 3 encryption. `null` means no encryption.  \
    If set, ['AES'|'DES'], a `privpassphrase` must be supplied."""
    v3_privpassphrase: Secret[str | None] = None
    """Privacy passphrase for SNMP version 3 encryption. This field is required when `privproto` is set."""
    loglevel: int = Field(ge=0, le=7)
    """Logging level for SNMP daemon (0=emergency to 7=debug)."""
    options: str
    """Additional SNMP daemon configuration options. \
    Manual settings should be used with caution as they may render the SNMP service non-functional."""
    zilstat: bool
    """Whether to enable ZFS dataset statistics collection for SNMP."""
    id: int
    """Placeholder identifier.  Not used as there is only one."""


@single_argument_args('snmp_update')
class SNMPUpdateArgs(SNMPEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class SNMPUpdateResult(BaseModel):
    result: SNMPEntry
    """The updated SNMP service configuration."""
