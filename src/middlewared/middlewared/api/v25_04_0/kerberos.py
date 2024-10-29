from middlewared.api.base import (
    BaseModel,
    NonEmptyString,
    single_argument_args,
)
from middlewared.utils.directoryservices.krb5_constants import (
    krb5ccache,
)
from pydantic import Field, Secret
from typing import Literal


__all__ = [
    'KerberosKdestroyArgs', 'KerberosKdestroyResult',
    'KerberosKinitArgs', 'KerberosKinitResult',
    'KerberosKlistArgs', 'KerberosKlistResult',
    'KerberosCheckTicketArgs', 'KerberosCheckTicketResult',
    'KerberosGetCredArgs', 'KerberosGetCredResult',
]


class KerberosCredentialUsernamePassword(BaseModel):
    """ Private API entry defined for normalization purposes """
    username: NonEmptyString
    password: Secret[NonEmptyString]


class KerberosCredentialKeytab(BaseModel):
    """ Private API entry defined for normalization purposes """
    kerberos_principal: NonEmptyString


class KerberosCcacheOptions(BaseModel):
    """ Private API entry defined for normalization purposes """
    ccache: Literal[
        krb5ccache.SYSTEM.value,
        krb5ccache.TEMP.value,
        krb5ccache.USER.value,
    ] = krb5ccache.SYSTEM.value
    cache_uid: int = 0


class KerberosKinitKdcOverride(BaseModel):
    """ Private API entry defined for normalization purposes """
    domain: str | None = None
    kdc: str | None = None
    libdefaults_aux: list[str] | None = None


class KerberosKinitOptions(KerberosCcacheOptions):
    """ Private API entry defined for normalization purposes """
    renewal_period: int = 7
    lifetime: int = 0
    kdc_override: KerberosKinitKdcOverride = Field(default=KerberosKinitKdcOverride())


class KerberosKlistOptions(KerberosCcacheOptions):
    """ Private API entry defined for normalization purposes """
    timeout: int = 10


@single_argument_args('kerberos_kinit')
class KerberosKinitArgs(BaseModel):
    """ Private API entry defined for normalization purposes """
    krb5_cred: KerberosCredentialUsernamePassword | KerberosCredentialKeytab
    kinit_options: KerberosKinitOptions = Field(alias='kinit-options', default=KerberosKinitOptions())


class KerberosKinitResult(BaseModel):
    """ Private API entry defined for normalization purposes """
    result: Literal[None]


class KerberosKlistArgs(BaseModel):
    """ Private API entry defined for normalization purposes """
    klist_options: KerberosKlistOptions


class KerberosKlistEntry(BaseModel):
    """ Private API entry defined for normalization purposes """
    issued: int
    expires: int
    renew_until: int
    client: NonEmptyString
    server: NonEmptyString
    etype: NonEmptyString
    flags: list[str]


class KerberosKlistFull(BaseModel):
    """ Private API entry defined for normalization purposes """
    default_principal: NonEmptyString
    ticket_cache: NonEmptyString
    tickets: list[KerberosKlistEntry]


class KerberosKlistResult(BaseModel):
    """ Private API entry defined for normalization purposes """
    result: KerberosKlistFull


class KerberosKdestroyArgs(KerberosCcacheOptions):
    """ Private API entry defined for normalization purposes """
    pass


class KerberosKdestroyResult(BaseModel):
    """ Private API entry defined for normalization purposes """
    result: Literal[None]


class KerberosCheckTicketArgs(BaseModel):
    """ Private API entry defined for normalization purposes """
    kerberos_options: KerberosCcacheOptions = Field(alias='kerberos-options', default=KerberosCcacheOptions())
    raise_error: bool = True


class KerberosGssCred(BaseModel):
    """ Private API entry defined for normalization purposes """
    name: NonEmptyString
    name_type: NonEmptyString
    name_type_oid: str
    lifetime: int


class KerberosCheckTicketResult(BaseModel):
    """ Private API entry defined for normalization purposes """
    result: KerberosGssCred


class ADKinitParameters(BaseModel):
    """ Private API entry defined for normalization purposes """
    bindname: NonEmptyString
    bindpw: Secret[NonEmptyString]
    domainname: NonEmptyString
    kerberos_principal: NonEmptyString


class LDAPKinitParameters(BaseModel):
    """ Private API entry defined for normalization purposes """
    binddn: NonEmptyString | None
    bindpw: Secret[NonEmptyString | None]
    kerberos_realm: int
    kerberos_principal: str | None


@single_argument_args('kerberos_get_cred')
class KerberosGetCredArgs(BaseModel):
    """ Private API entry defined for normalization purposes """
    ds_type: Literal['ACTIVEDIRECTORY', 'LDAP', 'IPA']
    conf: ADKinitParameters | LDAPKinitParameters


class KerberosGetCredResult(BaseModel):
    """ Private API entry defined for normalization purposes """
    result: KerberosCredentialUsernamePassword | KerberosCredentialKeytab
