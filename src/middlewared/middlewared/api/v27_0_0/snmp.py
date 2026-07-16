from typing import Annotated, Literal

from pydantic import EmailStr, Field, Secret
from pydantic.types import StringConstraints

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, excluded_field

__all__ = ["SNMPEntry", "SNMPUpdate", "SNMPUpdateArgs", "SNMPUpdateResult"]


class SNMPEntry(BaseModel):
    id: int = Field(description="Placeholder identifier.  Not used as there is only one.")
    location: str = Field(description="A comment describing the physical location of the server.")
    contact: EmailStr | Annotated[str, StringConstraints(pattern=r'^[-_a-zA-Z0-9\s]*$')] = Field(
        description="Contact information for the system administrator (email or name).",
    )
    traps: bool = Field(description="Whether SNMP traps are enabled.")
    v3: bool = Field(
        description=(
            "Whether SNMP version 3 is enabled.  Enabling version 3 also requires username, authtype and password."
        ),
    )
    community: str = Field(
        pattern=r'^[!\$%&()\+\-_={}\[\]<>,\.\?a-zA-Z0-9\s]*$',
        default='public',
        description=(
            "SNMP community string for v1/v2c access. Allows letters and numbers: a-zA-Z0-9 special characters: "
            "!$%&()+-_={}[]<>,.? and spaces. Notable excluded characters: # / \\ @."
        ),
    )
    v3_username: str = Field(max_length=20, description="Username for SNMP version 3 authentication.")
    v3_authtype: Literal['', 'MD5', 'SHA'] = Field(
        description="Authentication type for SNMP version 3 (empty string means no authentication).",
    )
    v3_password: Secret[str] = Field(description="Password for SNMP version 3 authentication.")
    v3_privproto: Literal[None, 'AES', 'DES'] | None = Field(
        description=(
            "Privacy protocol for SNMP version 3 encryption. `null` means no encryption. If set, ['AES'|'DES'], a "
            "`privpassphrase` must be supplied."
        ),
    )
    v3_privpassphrase: Secret[str | None] = Field(
        default=None,
        description="Privacy passphrase for SNMP version 3 encryption. This field is required when `privproto` is set.",
    )
    options: str = Field(
        description=(
            "Additional SNMP daemon configuration options. Manual settings should be used with caution as they may "
            "render the SNMP service non-functional."
        ),
    )
    zilstat: bool = Field(description="Whether to enable ZFS dataset statistics collection for SNMP.")

    @classmethod
    def to_previous(cls, value):
        value["loglevel"] = 4  # -LOw
        return value


class SNMPUpdate(SNMPEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class SNMPUpdateArgs(BaseModel):
    snmp_update: SNMPUpdate = Field(description="Data to update the SNMP service configuration.")


class SNMPUpdateResult(BaseModel):
    result: SNMPEntry = Field(description="The updated SNMP service configuration.")
