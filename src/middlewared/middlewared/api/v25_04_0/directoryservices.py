from annotated_types import Ge, Le
from typing import Literal, Self
from typing_extensions import Annotated

from pydantic import Field, model_validator, Secret

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString,
    LdapDn, SID, single_argument_args,
)

from middlewared.utils.directoryservices.constants import (
    DSCredentialType, DSLdapSsl, DSLdapNssInfo, DSActiveDirectoryNssInfo, DSStatus,
    DSType,
)

__all__ = [
    'DirectoryServicesEntry', 'DirectoryServicesUpdateArgs',
    'DirectoryServicesStatusArgs', 'DirectoryServicesStatusResult',
    'DirectoryServicesGetStateArgs', 'DirectoryServicesGetStateResult',
]

DS_Timeout = Annotated[int, Ge(5), Le(120)]
DS_DNSTimeout = Annotated[int, Ge(5), Le(40)]
DS_SSLChoices = Literal[
    DSLdapSsl.OFF,
    DSLdapSsl.LDAPS,
    DSLdapSsl.STARTTLS,
]
DS_LDAP_NSS_INFO = Literal[
    DSLdapNssInfo.RFC2307,
    DSLdapNssInfo.RFC2307BIS
]
DS_AD_NSS_INFO = Literal[
    DSActiveDirectoryNssInfo.TEMPLATE,
    DSActiveDirectoryNssInfo.SFU,
    DSActiveDirectoryNssInfo.SFU20,
    DSActiveDirectoryNssInfo.RFC2307,
]
DS_TYPE = Literal[
    DSType.STANDALONE,
    DSType.AD,
    DSType.IPA,
    DSType.LDAP,
]
DS_STATUS = Literal[
    DSStatus.DISABLED,
    DSStatus.FAULTED,
    DSStatus.LEAVING,
    DSStatus.JOINING,
    DSStatus.HEALTHY,
]


class DSCredUsernamePassword(BaseModel):
    bindname: NonEmptyString
    bindpw: Secret[NonEmptyString | None]
    credential_type: Literal[DSCredentialType.USERNAME_PASSWORD]


class DSCredKerberosPrincipal(BaseModel):
    kerberos_principal: NonEmptyString
    credential_type: Literal[DSCredentialType.KERBEROS_PRINCIPAL]


class DSCredClientCert(BaseModel):
    client_certificate: NonEmptyString
    credential_type: Literal[DSCredentialType.CERTIFICATE]


class DSSSLConfig(BaseModel):
    ssl: DS_SSLChoices = Field(default=DSLdapSsl.LDAPS)
    validate_certificates: bool = Field(default=True)


class DSCredBindDnPasword(BaseModel):
    binddn: LdapDn
    bindpw: Secret[NonEmptyString]
    credential_type: Literal[DSCredentialType.LDAPDN_PASSWORD]


class DSCredAnonymous(BaseModel):
    credential_type: Literal[DSCredentialType.ANONYMOUS]


class DSTimeouts(BaseModel):
    service: DS_Timeout = Field(default=60)
    dns: DS_DNSTimeout = Field(default=10)


class DirectoryServiceBase(BaseModel):
    enable: bool
    enable_cache: bool = Field(default=True)


class DirectoryServiceActiveDirectory(BaseModel):
    domainname: NonEmptyString
    credential: DSCredUsernamePassword | DSCredKerberosPrincipal | None
    site: str | None
    """Active directory site is automatically detected on domain join"""
    kerberos_realm: str | None
    computer_account_ou: str
    allow_dns_updates: bool = True
    allow_trusted_domains: bool = False
    use_default_domain: bool = True
    nss_info: DS_AD_NSS_INFO = DSActiveDirectoryNssInfo.TEMPLATE


class DirectoryServiceIPA(BaseModel):
    domainname: NonEmptyString
    target_server: NonEmptyString
    """Preferred IPA server to use for IPA operations"""
    netbios_domainname: NonEmptyString | None
    """NetBIOS domain is automatically detected on IPA join"""
    basedn: LdapDn
    credential: DSCredUsernamePassword | DSCredKerberosPrincipal | None
    ssl_config: DSSSLConfig = Field(default=DSSSLConfig())
    kerberos_realm: str | None
    domain_sid: SID | None
    """domain SID is automatically detected on IPA join"""
    allow_dns_updates: bool = True


class DSLdapSearchBases(BaseModel):
    base_user: NonEmptyString | None = None
    base_group: NonEmptyString | None = None
    base_netgroup: NonEmptyString | None = None


class DSLdapPasswdMap(BaseModel):
    user_object_class: NonEmptyString | None = None
    user_name: NonEmptyString | None = None
    user_uid: NonEmptyString | None = None
    user_gid: NonEmptyString | None = None
    user_gecos: NonEmptyString | None = None
    user_home_directory: NonEmptyString | None = None
    user_shell: NonEmptyString | None = None


class DSLdapShadowMap(BaseModel):
    shadow_object_class: NonEmptyString | None = None
    shadow_last_change: NonEmptyString | None = None
    shadow_min: NonEmptyString | None = None
    shadow_max: NonEmptyString | None = None
    shadow_warning: NonEmptyString | None = None
    shadow_inactive: NonEmptyString | None = None
    shadow_expire: NonEmptyString | None = None


class DSLdapGroupMap(BaseModel):
    group_object_class: NonEmptyString | None = None
    group_gid: NonEmptyString | None = None
    group_member: NonEmptyString | None = None


class DSLdapNetgroupMap(BaseModel):
    netgroup_object_class: NonEmptyString | None = None
    netgroup_member: NonEmptyString | None = None
    netgroup_triple: NonEmptyString | None = None


class DSLdapAttributeMap(BaseModel):
    passwd: DSLdapPasswdMap = Field(default=DSLdapPasswdMap())
    shadow: DSLdapShadowMap = Field(default=DSLdapShadowMap())
    group: DSLdapGroupMap = Field(default=DSLdapGroupMap())
    netgroup: DSLdapNetgroupMap = Field(default=DSLdapNetgroupMap())


class DirectoryServiceLDAP(BaseModel):
    server_hostnames: list[NonEmptyString]
    credential: DSCredBindDnPasword | DSCredKerberosPrincipal | DSCredClientCert | DSCredAnonymous | None
    ssl_config: DSSSLConfig = Field(default=DSSSLConfig())
    kerberos_realm: str | None
    auxiliary_parameters: str | None
    schema: DS_LDAP_NSS_INFO = Field(default=DSLdapNssInfo.RFC2307)
    search_bases: DSLdapSearchBases = Field(default=DSLdapSearchBases())
    attribute_maps: DSLdapAttributeMap = Field(default=DSLdapAttributeMap())


class DirectoryServicesEntry(DirectoryServiceBase):
    id: int
    dstype: DS_TYPE
    enable: bool
    enable_cache: bool = Field(default=True)
    configuration: DirectoryServiceActiveDirectory | DirectoryServiceLDAP | DirectoryServiceIPA | None
    timeout: DSTimeouts = Field(default=DSTimeouts())


@single_argument_args('directory_services_update_args')
class DirectoryServicesUpdateArgs(DirectoryServicesEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()

    @model_validator(mode='after')
    def check_ds_type_configuration(self) -> Self:
        # Make sure that configuration type matches the directory service type
        match self.type:
            case DSType.STANDALONE:
                if self.enable:
                    raise ValueError('Directory services may not be enabled in STANDALONE mode')

                if self.configuration is not None:
                    raise ValueError('Configuration must be None when setting STANDALONE mode')

            case DSType.AD:
                if not isinstance(self.configuration, DirectoryServiceActiveDirectory):
                    raise ValueError('Active directory configuration required')
            case DSType.IPA:
                if not isinstance(self.configuration, DirectoryServiceIPA):
                    raise ValueError('IPA configuration required')
            case DSType.LDAP:
                if not isinstance(self.configuration, DirectoryServiceLDAP):
                    raise ValueError('LDAP configuration required')
            case _:
                # this shouldn't happen, but we have potential to get mismatchy here.
                raise ValueError(f'{self.type}: unexpected directory service type')

        return self


@single_argument_args('directory_services_status')
class DirectoryServicesStatusArgs(BaseModel):
    pass


class StatusResult(BaseModel):
    type: DS_TYPE | None
    status: DSStatus
    status_msg: str | None


class DirectoryServicesStatusResult(BaseModel):
    result: StatusResult


@single_argument_args('directory_services_get_state')
class DirectoryServicesGetStateArgs(BaseModel):
    pass


class GetStateResult(BaseModel):
    """ Legacy response -- will be deleted before 25.04 beta """
    activedirectory: DSStatus
    ldap: DSStatus


class DirectoryServicesGetStateResult(BaseModel):
    result: GetStateResult
