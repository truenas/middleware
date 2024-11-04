from ldap import dn
from pydantic.functional_validators import AfterValidator
from typing_extensions import Annotated

__all__ = ['LdapDn']


def validate_ldap_dn(value: str) -> str:
    if not value:
        return value

    if not dn.is_dn(value):
        raise ValueError(f'{value}: not a valid LDAP DN')

    return value


LdapDn = Annotated[str, AfterValidator(validate_ldap_dn)]
