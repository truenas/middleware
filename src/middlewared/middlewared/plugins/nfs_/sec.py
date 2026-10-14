from typing import Literal

from middlewared.api.base import BaseModel
from middlewared.api.current import NFSEntry

from .utils import NFSProtocol

NfsSecurityFlavor = Literal["sys", "krb5", "krb5i", "krb5p"]


class NFSSecArgs(BaseModel):
    config: NFSEntry
    has_nfs_principal: bool


class NFSSecResult(BaseModel):
    result: list[NfsSecurityFlavor]


def security_flavors(config: NFSEntry, has_nfs_principal: bool) -> list[NfsSecurityFlavor]:
    if NFSProtocol.NFSv4 not in config.protocols:
        return []

    if config.v4_krb:
        return ["krb5", "krb5i", "krb5p"]

    if has_nfs_principal:
        return ["sys", "krb5", "krb5i", "krb5p"]

    return ["sys"]
