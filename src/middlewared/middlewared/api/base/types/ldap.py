from ldap import dn
from pydantic import AfterValidator
from typing import Annotated


__all__ = ["LDAP_DN", "LDAP_URL",]


def validate_ldap_dn(value: str) -> str:
    if not dn.is_dn(value):
        raise ValueError('Invalid LDAP DN')

    return value


def validate_ldap_url(value: str) -> str:
    if not value.startswith(('ldap://', 'ldaps://')):
        raise ValueError('LDAP URI must begin with either ldap:// or ldaps://')

    return value


LDAP_DN = Annotated[str, AfterValidator(validate_ldap_dn)]
LDAP_URL = Annotated[str, AfterValidator(validate_ldap_url)]
