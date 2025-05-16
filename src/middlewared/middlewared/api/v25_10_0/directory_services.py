from middlewared.api.base import (
    BaseModel,
    excluded_field,
    Excluded,
    ForUpdateMetaclass,
    LongNonEmptyString,
    NonEmptyString,
    single_argument_args,
    LDAP_DN,
    LDAP_URL,
    NetbiosDomain,
    SID,
)
from middlewared.utils.directoryservices.credential import DSCredType
from middlewared.utils.lang import undefined
from middlewared.plugins.idmap_.idmap_constants import TRUENAS_IDMAP_MAX, TRUENAS_IDMAP_DEFAULT_LOW

from pydantic import Field, Secret, model_validator, field_validator
from typing import Annotated, Literal

__all__ = [
    'DirectoryServicesEntry', 'DirectoryServicesUpdateArgs', 'DirectoryServicesUpdateResult',
    'DirectoryServicesLeaveArgs', 'DirectoryServicesLeaveResult',
    'CredKRBUser', 'CredKRBPrincipal', 'CredLDAPPlain', 'CredLDAPAnonymous', 'CredLDAPMTLS',
]

IdmapId = Annotated[int, Field(ge=TRUENAS_IDMAP_DEFAULT_LOW, le=TRUENAS_IDMAP_MAX)]


# idmap domains are a configuration feature of winbindd when joined to an active
# directory domain

class IdmapDomainBase(BaseModel):
    name: NetbiosDomain | None = Field(default=None, example='IXDOM')
    """ short-form name for the trusted domain. This should match the NetBIOS
    domain name for active directory domains. May be None if the domain configuration
    is for base idmap for Active Directory configuration. """
    range_low: IdmapId = 100000001
    """ The lowest UID or GID that the idmap backend may assign. """
    range_high: IdmapId = 200000000
    """ The highest UID or GID that the idmap backend may assign. """

    @model_validator(mode='after')
    def check_ranges(self):
        if self.range_low >= self.range_high:
            raise ValueError("Low range must be less than high range")

        if (self.range_high - self.range_low) < 10000:
            raise ValueError("Range for domain must contain at least 10000 IDs")

        return self


class IPA_SMBDomain(IdmapDomainBase):
    """ This is a special idmap backend for when TrueNAS is joined to an IPA domain.
    The configuration information is provided by the remote IPA server and auto-detected
    during the IPA domain join process. This information is based on the IPA server's
    response to service_add_smb command.
    """
    idmap_backend: Literal['SSS']
    domain_name: NonEmptyString | None = Field(default=None, example='IXDOM.INTERNAL')
    """ Name of the SMB domain as defined in the IPA configuration for the IPA domain to
    which TrueNAS is joined. """
    domain_sid: SID | None = Field(default=None, example='S-1-5-21-3696504179-2855309571-923743039')
    """ The domain SID for the IPA domain to which TrueNAS is joined. """


class AD_Idmap(IdmapDomainBase):
    """ The AD backend reads UID and GID mappings from an Active Directory server that
    uses pre-existing RFC2307 / SFU schema extensions. Mappings must be provided in advance
    by the dministrator by adding the uidNumber attributes for users and gidNumber attributes
    for groups in Active Directory. """
    idmap_backend: Literal['AD']
    schema_mode: Literal['RFC2307', 'SFU', 'SFU20']
    """ The schema mode that the idmap backend should use when querying Active Directory
    for user and group information. The RFC2307 schema was used in Windows Server 2003 R2 and
    newer. The Services for Unix (SFU) schema was used for versions prior to Windows Server 2003
    R2."""
    unix_primary_group: bool = False
    """ Defines whether the user's primary group is fetched from the SFU attributes or the
    Active Directory primary group. If True, the primary group membership is fetched
    based on the gidNumber LDAP attribute, if set to False the primary group membership is
    calculated via the primaryGroupID LDAP attribute. """
    unix_nss_info: bool = False
    """ If set to True the login shell and home directory will be retrieved from the LDAP attributes.
    If set to False or if the Active Directory LDAP entry lacks SFU attribute, then the homedir
    will default to `/var/empty`. """


class Autorid_Idmap(IdmapDomainBase):
    """ The AUTORID backend provides a way to use an algoritmic mapping scheme to map UIDs and
    GIDs to SIDs in a way similar to the RID backend, but automatically configures the range to be
    used for each domain in the forest. """
    idmap_backend: Literal['AUTORID']
    rangesize: int = Field(default=100000, ge=10000, le=1000000000)
    """ Defines the number of uids / gids available per domain range. SIDs with RIDs larger than
    this value will be mapped into extension ranges depending on the number of available ranges."""
    readonly: bool = False
    """ Turn the module into read-only mode. No new ranges or mappings will be created in the
    idmap pool. """
    ignore_builtin: bool = False
    """ Ignore any mapping requests for the BUILTIN domain. """


class LDAP_Idmap(IdmapDomainBase):
    """ The LDAP backend reads and writes UID / GID mapping tables from an external LDAP server. """
    idmap_backend: Literal['LDAP']
    ldap_base_dn: LDAP_DN
    """ Directory base suffix to use for mapping UIDs and GIDs to SIDs. """
    ldap_user_dn: LDAP_DN
    """ Defines the user DN to be used for authentication to the LDAP server. """
    ldap_user_dn_password: Secret[NonEmptyString]
    """ Secret to use for authenticating the user specified by `ldap_user_dn`. """
    ldap_url: LDAP_URL
    """ LDAP server to use for the idmap entries """
    readonly: bool = False
    """ If readonly is set to True then TrueNAS will not attempt to write new idmap entries. """
    validate_certificates: bool = True
    """ If set to False TrueNAS will not validate certificates presented by the remote LDAP server.
    Generally, it is a better strategy to use valid certificates or to import relevant certificates
    into the certificate trusted store in TrueNAS. """


class RFC2307_Idmap(IdmapDomainBase):
    """ The RFC2307 backend provides a way to read ID mappings from RFC2307 attributes provided by
    a standalone LDAP server. This backend is read only. If the target server is an Active
    Directory domain controller, then the AD backend should be used instead. """
    idmap_backend: Literal['RFC2307']
    ldap_server: Literal["STANDALONE"]
    ldap_url: LDAP_URL
    """ The LDAP URL for accessing the LDAP server. """
    ldap_user_dn: LDAP_DN
    """ Defines the DN used for authentication to the LDAP server. """
    ldap_user_dn_password: Secret[NonEmptyString]
    """ Secret to use for authenticating the account specified as ldap_user_dn. """
    bind_path_user: LDAP_DN
    """ The search base where user objects can be found in the LDAP server. """
    bind_path_group: LDAP_DN
    """ The search base where group objects can be found in the LDAP server. """
    user_cn: bool = False
    """ Query the CN attribute instead of UID attribute for the user name in LDAP. """
    ldap_realm: bool = False
    """ Append @realm to the CN for groups (and users if `user_cn` is specified) """
    validate_certificates: bool = True
    """ If set to False TrueNAS will not validate certificates presented by the remote LDAP server.
    Generally, it is a better strategy to use valid certificates or to import relevant certificates
    into the certificate trusted store in TrueNAS. """


class RID_Idmap(IdmapDomainBase):
    """ The RID backend provides an algorithmic mapping scheme to map UIDs and GIDs to SIDs.
    The UID or GID is determined by taking the RID value from the Windows Account SID and
    adding it to the base value specified by `range_low`. RID values in an Active Directory
    domain can large, especially as the domain ages, and so administrators should configure
    a range large enough to accomodate the current RID values being assigned by the RID master.
    One way to do this is to look review the RID assigned to a recently created account in
    Active Directory. If the RID is 500000, then the range specified for this backend must
    contain at least 500000 unix IDs (for example 1000000 - 2000000). """
    idmap_backend: Literal['RID']
    sssd_compat: bool = False
    """ Generate an idmap low range based on the algorithm used by SSSD to allocate IDs.
    This is sufficient if the domain is configured in such a way that it only consumes a
    single SSSD idmap slice."""


class BuiltinDomainTdb(IdmapDomainBase):
    """ Idmap ranges and information for BUILTIN, system accounts, and other accounts
    that are not explicitly mapped for a known domain. """
    range_low: IdmapId = 90000001
    """ The lowest UID or GID that the idmap backend may assign. """
    range_high: IdmapId = 100000000
    """ The highest UID or GID that the idmap backend may assign. """


class PrimaryDomainIdmap(BaseModel):
    builtin: BuiltinDomainTdb = Field(default=BuiltinDomainTdb())
    idmap_domain: AD_Idmap | LDAP_Idmap | RFC2307_Idmap | RID_Idmap = Field(default=RID_Idmap(idmap_backend='RID'))


class PrimaryDomainIdmapAutoRid(BaseModel):
    idmap_domain: Autorid_Idmap


class KerberosConfiguration(BaseModel):
    realm: int | None = None
    """ Primary key of kerberos realm to use for authentication to the specified directory
    service. If None, then kerberos will not be used for binding to the configured directory
    service. When initially joining an Active Directory or IPA domain, the realm will be
    automatically detected and configured if the realm is not specified. """
    principal: NonEmptyString | None = None
    """ The kerberos principal to use for authentication to the specified directory service.
    If this is None, then TrueNAS will attempt to obtain a kerberos ticket using credentials
    specified in the payload. This will be automatically set while joining an Active Directory
    or IPA domain. """


class CredKRBPrincipal(BaseModel):
    credential_type: Literal[DSCredType.KERBEROS_PRINCIPAL]
    principal: NonEmptyString
    """ A kerberos principal is a unique identity to which Kerberos can assign tickets.
    The specified kerberos principal must have an entry within a keytab on the TrueNAS server."""


class CredKRBUser(BaseModel):
    credential_type: Literal[DSCredType.KERBEROS_USER]
    username: NonEmptyString
    """ Username of the account to use to create a kerberos ticket for authentication to
    directory services. This account must exist on the domain controller. """
    password: Secret[NonEmptyString]
    """ The password for the user account that will obtain the kerberos ticket. """


class CredLDAPPlain(BaseModel):
    credential_type: Literal[DSCredType.LDAP_PLAIN]
    binddn: LDAP_DN
    bindpw: Secret[NonEmptyString]


class CredLDAPAnonymous(BaseModel):
    credential_type: Literal[DSCredType.LDAP_ANONYMOUS]


class CredLDAPMTLS(BaseModel):
    credential_type: Literal[DSCredType.LDAP_MTLS]
    client_certificate: NonEmptyString
    """ Client certificate name that will be used for mutual TLS authentication to the
    remote LDAP server. """


class ActiveDirectoryConfig(BaseModel):
    hostname: NonEmptyString = Field(example='truenasnyc')
    """ Hostname of TrueNAS server to register in active directory. """
    domain: NonEmptyString = Field(example='mydomain.internal')
    """ Full DNS domain name of the Active Directory Domain. This should not be a domain
    controller. """
    idmap: PrimaryDomainIdmap | PrimaryDomainIdmapAutoRid = Field(default=PrimaryDomainIdmap())
    """ Configuration for how to map Active Directory accounts into accounts on the
    TrueNAS server. The exact settings required here may vary based on how other servers and
    Linux clients are configured in the domain. Defaults are reasonable for a new deployment
    without existing support for unix-like operating systems. """
    site: NonEmptyString | None = Field(default=None)
    """ The Active Directory site in which the TrueNAS server is located. This will be auto
    detected during the domain join process. """
    computer_account_ou: NonEmptyString | None = Field(default=None, example='TRUENAS_SERVERS/NYC')
    """ Override for the default organizational unit (OU) in which to create the TrueNAS
    computer account during the domain join. This may be used to specify a custom location
    for TrueNAS computer accounts. """
    use_default_domain: bool = Field(default=False)
    """ Controls whether domain users and groups have a prefix prepended to the user account.
    If this is enabled, then Active Directory users will appear as "administrator" instead of
    "EXAMPLE\\administrator". In most circumstances this should be disabled as collisions
    between active directory and local user account names can result in undefined behavior. """
    enable_trusted_domains: bool = Field(default=False)
    """ Enable support for trusted domains. If True, then separate trusted domain
    configuration must be set for all trusted domains. """
    trusted_domains: list[AD_Idmap | LDAP_Idmap | RFC2307_Idmap | RID_Idmap] = []
    """ Configuration for trusted domains. """

    @field_validator('trusted_domains')
    @classmethod
    def validate_trusted_domains(cls, value):
        # Check for range overlaps between trusted domains
        if any([entry['name'] is None for entry in value]):
            raise ValueError('Domain name is required for trusted domains')

        for idx, entry in enumerate(value):
            for idx2, entry2 in enumerate(value.copy()):
                if idx == idx2:
                    # skip ourselves
                    continue

                if entry['range_low'] >= entry2['range_low'] or entry['range_low'] <= entry2['range_high']:
                    raise ValueError(f'Low range for {entry["name"]} conflicts with range for {entry2["name"]}.')

                if entry['range_high'] >= entry2['range_low'] or entry['range_high'] <= entry2['range_high']:
                    raise ValueError(f'High range for {entry["name"]} conflicts with range for {entry2["name"]}.')

        return value


class LDAPSearchBases(BaseModel):
    """ Optional search bases to restrict LDAP searches for attribute types """
    base_user: LDAP_DN | None = None
    base_group: LDAP_DN | None = None
    base_netgroup: LDAP_DN | None = None


class LDAPMapPasswd(BaseModel):
    """ Optional mappings for non-compliant LDAP servers to generate passwd entries """
    user_object_class: LDAP_DN | None = None
    user_name: LDAP_DN | None = None
    user_uid: LDAP_DN | None = None
    user_gid: LDAP_DN | None = None
    user_gecos: LDAP_DN | None = None
    user_home_directory: LDAP_DN | None = None
    user_shell: LDAP_DN | None = None


class LDAPMapShadow(BaseModel):
    """ Optional mappings for non-compliant LDAP servers to generate shadow entries """
    shadow_object_class: LDAP_DN | None = None
    shadow_last_change: LDAP_DN | None = None
    shadow_min: LDAP_DN | None = None
    shadow_max: LDAP_DN | None = None
    shadow_warning: LDAP_DN | None = None
    shadow_inactive: LDAP_DN | None = None
    shadow_expire: LDAP_DN | None = None


class LDAPMapGroup(BaseModel):
    """ Optional mappings for non-compliant LDAP servers to generate group entries """
    group_object_class: LDAP_DN | None = None
    group_gid: LDAP_DN | None = None
    group_member: LDAP_DN | None = None


class LDAPMapNetgroup(BaseModel):
    """ Optional mappings for non-compliant LDAP servers to generate netgroup entries """
    netgroup_object_class: LDAP_DN | None = None
    netgroup_member: LDAP_DN | None = None
    netgroup_triple: LDAP_DN | None = None


class LDAPAttributeMaps(BaseModel):
    passwd: LDAPMapPasswd = Field(default=LDAPMapPasswd())
    shadow: LDAPMapShadow = Field(default=LDAPMapShadow())
    group: LDAPMapGroup = Field(default=LDAPMapGroup())
    netgroup: LDAPMapNetgroup = Field(default=LDAPMapNetgroup())


class LDAPConfig(BaseModel):
    server_urls: list[LDAP_URL] = Field(example=['ldaps://myldap.domain.internal'])
    """ List of LDAP server URIs to use for LDAP binds. Each server may be a DNS name or IP address and must
    be prefixed by "ldap://" or "ldaps://". """
    starttls: bool = Field(default=False)
    """ Establish TLS by transmitting a StartTLS request to the server. """
    basedn: LDAP_DN = Field(example='dc=domain,dc=internal')
    """ The base DN to use when performing LDAP operations. """
    validate_certificates: bool = Field(default=True)
    """ If set to False TrueNAS will not validate certificates presented by the remote LDAP server.
    Generally, it is a better strategy to use valid certificates or to import relevant certificates
    into the certificate trusted store in TrueNAS. """
    ldap_schema: Literal['RFC2307', 'RFC2307BIS'] = Field(default='RFC2307', alias='schema')
    """ The LDAP attribute schema type used by the remote LDAP server. The RFC2307 schema is used by
    most LDAP servers. """
    search_bases: LDAPSearchBases = Field(default=LDAPSearchBases())
    """ Alternative LDAP search base configuration. These configuration options allow for specifying
    the DN in which to find user, group, and netgroup entries. If unspecified (the default) then all
    users, groups, and netgroups within the specified `basedn` will be available on TrueNAS. """
    attribute_maps: LDAPAttributeMaps = Field(default=LDAPAttributeMaps())
    """ Alertative LDAP attribute map configuration for LDAP implementations that are non-compliant
    with RFC2307 or RFC2307BIS. These are only required if using a non-standard LDAP implementaiton. """
    auxiliary_parameters: LongNonEmptyString | None = None
    """ Additional parameters that may be inserted into the SSSD running configuration. These are not
    validated and may result in production outages on application or on upgrade. """


class IPAConfig(BaseModel):
    target_server: NonEmptyString = Field(example='ipa.example.internal')
    """ The hostname of the IPA server to use when constructing URLs during IPA operations when
    joining or leaving the IPA domain. """
    hostname: NonEmptyString = Field(example='truenasnyc')
    """ Hostname of TrueNAS server to register in IPA during the join process. """
    domain: NonEmptyString = Field(example='example.internal')
    """ The domain of the IPA server """
    basedn: LDAP_DN = Field(example='dc=example,dc=internal')
    """ The base DN to use when performing LDAP operations. """
    smb_domain: IPA_SMBDomain | None = Field(default=None)
    """ Configuration for IPA SMB domain. Not all IPA domains will have SMB schema changes
    present. """
    validate_certificates: bool = Field(default=True)
    """ If set to False TrueNAS will not validate certificates presented by the remote LDAP server.
    Generally, it is a better strategy to use valid certificates or to import relevant certificates
    into the certificate trusted store in TrueNAS. """


class DirectoryServicesEntry(BaseModel):
    id: int
    service_type: Literal['ACTIVEDIRECTORY', 'IPA', 'LDAP'] | None
    """ The pre-existing directory service type to which to bind TrueNAS. ACTIVEDIRECTORY should
    be selected when joining TrueNAS to an Active Directory domain, IPA should be selected when
    joining TrueNAS to a FreeIPA domain, and LDAP should be selected when joining to one or more
    OpenLDAP compatible servers."""
    credential: CredKRBUser | CredKRBPrincipal | CredLDAPPlain | CredLDAPAnonymous | CredLDAPMTLS | None
    """ Credential to use for binding to the specified directory service. Kerberos credentials
    are required for Active Directory or IPA domains. There is more variety of potential
    authentication methods for generic LDAP environments, but the available authentication
    mechanisms depend on the how the remote LDAP server is configured.  If kerberos credential
    types are selected for the LDAP service type then GSSAPI binds will be performed in lieu of
    plain LDAP binds. """
    enable: bool
    """ Enable the directory service. If TrueNAS has never joined the specified domain, then
    setting this to True will cause TrueNAS to attempt to join the domain. Note that the domain
    join process for Active Directory and IPA will make changes to the domain such as creating
    a new computer account for the TrueNAS server and creating DNS records for TrueNAS. """
    enable_account_cache: bool = Field(default=True)
    """ Enable backend caching for user and group lists. If enabled, then directory services
    users and groups will be presented as choices in the UI dropdowns and in API responses
    for user and group queries. This also controls whether users and groups will appear in
    `getent` results. In some edge cases this may be disabled in order to reduce load on the
    directory server. """
    enable_dns_updates: bool = Field(default=True)
    """ Enable automatic DNS updates for the TrueNAS server in the domain via nsupdate and
    gssapi / TSIG. """
    timeout: int = Field(default=10, ge=5, le=40)
    """ The timeout value for DNS queries that are performed as part of the join process and
    NETWORK_TIMEOUT for LDAP requests. """
    kerberos_realm: NonEmptyString | None = Field(default=None)
    """ Name of kerberos realm to use for authentication to the specified directory
    service. If None, then kerberos will not be used for binding to the configured directory
    service. When initially joining an Active Directory or IPA domain, the realm will be
    automatically detected and configured if the realm is not specified. """
    configuration: ActiveDirectoryConfig | IPAConfig | LDAPConfig | None = Field(default=None)


@single_argument_args('directoryservices_update')
class DirectoryServicesUpdateArgs(DirectoryServicesEntry, metaclass=ForUpdateMetaclass):
    """ Update the directory services configuration with the specified payload.
    If service_type is set to None and enable is False, then the all existing directory
    service configuration will be cleared.

    Note about domain joins:
    IPA and Active Directory directory service types perform a join operation the
    first time they are enabled, which results in the creation of a domain account for
    the TrueNAS server. This account's credentials, which are in the form of a machine
    account keytab, will be used for all further domain-related operations.
    """
    id: Excluded = excluded_field()
    force: bool = Field(default=False)
    """ Bypass validation for whether a server with this hostname and netbios name is
    already registered in an IPA or Active Directory domain. This may be used, for example,
    to replace an existing sever with a TrueNAS server. The force parameter should not be used
    indiscriminately as doing so may result in production outages for any client using an
    existing server that conflicts with this TrueNAS server when TrueNAS overwrites the
    existing account. """

    def __check_configuration_type(self, service_type, configuration):
        match service_type:
            case 'ACTIVEDIRECTORY':
                if not isinstance(configuration, ActiveDirectoryConfig):
                    raise ValueError('Active Directory configuration is required')
            case 'IPA':
                if not isinstance(configuration, IPAConfig):
                    raise ValueError('IPA configuration is required')

            case 'LDAP':
                if not isinstance(configuration, LDAPConfig):
                    raise ValueError('LDAP configuration is required')

            case None:
                if configuration is not None:
                    raise ValueError('configuration must be set to None when setting service type to None')
            case _:
                raise ValueError(f'{service_type}: unexpected service_type')

    def __check_credential_type(self, service_type, credential_type, has_realm):
        match service_type:
            case 'LDAP':
                if credential_type.startswith('KERBEROS') and not has_realm:
                    raise ValueError(
                        'Kerberos realm is required for using kerberos credentials with a plain LDAP server'
                    )

            case _:
                if credential_type.startswith('LDAP'):
                    raise ValueError('LDAP authentication methods are only supported for the LDAP service type.')

    @model_validator(mode='after')
    def validate_ds(self):
        if self.service_type == undefined and self.enable is not False:
            raise ValueError('service_type is required in update payloads')

        if self.enable is True and self.service_type is not None:
            if self.configuration in (None, undefined):
                raise ValueError('Explicit configuration is required when service_type is specified')

            if self.credential in (None, undefined):
                raise ValueError('Explicit credential configuration is required when service_type is specified')

            self.__check_credential_type(
                self.service_type,
                self.credential.credential_type,
                self.kerberos_realm is not None
            )

        if self.enable is True:
            self.__check_configuration_type(self.service_type, self.configuration)

        return self


class DirectoryServicesUpdateResult(BaseModel):
    result: DirectoryServicesEntry


@single_argument_args('credential')
class DirectoryServicesLeaveArgs(BaseModel):
    credential: CredKRBUser


class DirectoryServicesLeaveResult(BaseModel):
    result: None
