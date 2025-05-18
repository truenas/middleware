from middlewared.api.base import (
    BaseModel,
    excluded_field,
    Excluded,
    ForUpdateMetaclass,
    LongNonEmptyString,
    NonEmptyString,
    single_argument_args,
    single_argument_result,
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
    'DirectoryServicesCacheRefreshArgs', 'DirectoryServicesCacheRefreshResult',
    'DirectoryServicesStatusArgs', 'DirectoryServicesStatusResult',
    'DirectoryServicesEntry', 'DirectoryServicesUpdateArgs', 'DirectoryServicesUpdateResult',
    'DirectoryServicesLeaveArgs', 'DirectoryServicesLeaveResult',
    'CredKRBUser', 'CredKRBPrincipal', 'CredLDAPPlain', 'CredLDAPAnonymous', 'CredLDAPMTLS',
]

IdmapId = Annotated[int, Field(ge=TRUENAS_IDMAP_DEFAULT_LOW, le=TRUENAS_IDMAP_MAX)]

DSStatus = Literal['DISABLED', 'FAULTED', 'LEAVING', 'JOINING', 'HEALTHY']
DSType = Literal['ACTIVEDIRECTORY', 'IPA', 'LDAP']


class DirectoryServicesStatusArgs(BaseModel):
    pass


@single_argument_result
class DirectoryServicesStatusResult(BaseModel):
    dstype: DSType | None = Field(alias='type')
    """ The type of enabled directory service. """
    status: DSStatus | None = None
    """ The status of the directory service as of the last health check. The status will be None if directory services
    are disabled. """
    status_msg: str | None = None
    """ This field is populated with the reason why the directory service is in a faulted state if a periodic health
    check failed. If the directory service is not faulted then it will be None. """


class DirectoryServicesCacheRefreshArgs(BaseModel):
    pass


class DirectoryServicesCacheRefreshResult(BaseModel):
    result: Literal[None]


# idmap domains are a configuration feature of winbindd when joined to an active directory domain

class IdmapDomainBase(BaseModel):
    name: NetbiosDomain | None = Field(default=None, example='IXDOM')
    """ short-form name for the trusted domain. This should match the NetBIOS domain name for active directory domains.
    May be None if the domain configuration is for base idmap for Active Directory configuration. """
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
    """ This is a special idmap backend for when TrueNAS is joined to an IPA domain. The configuration information is
    provided by the remote IPA server and auto-detected during the IPA domain join process. This information is based
    on the IPA server's response to service_add_smb command.
    """
    idmap_backend: Literal['SSS']
    domain_name: NonEmptyString | None = Field(default=None, example='IXDOM.INTERNAL')
    """ Name of the SMB domain as defined in the IPA configuration for the IPA domain to
    which TrueNAS is joined. """
    domain_sid: SID | None = Field(default=None, example='S-1-5-21-3696504179-2855309571-923743039')
    """ The domain SID for the IPA domain to which TrueNAS is joined. """


class AD_Idmap(IdmapDomainBase):
    """ The AD backend reads UID and GID mappings from an Active Directory server that uses pre-existing RFC2307 / SFU
    schema extensions. Mappings must be provided in advance by the dministrator by adding the uidNumber attributes for
    users and gidNumber attributes for groups in Active Directory. """
    idmap_backend: Literal['AD']
    schema_mode: Literal['RFC2307', 'SFU', 'SFU20']
    """ The schema mode that the idmap backend should use when querying Active Directory for user and group
    information. The RFC2307 schema was used in Windows Server 2003 R2 and newer. The Services for Unix (SFU) schema
    was used for versions prior to Windows Server 2003 R2."""
    unix_primary_group: bool = False
    """ Defines whether the user's primary group is fetched from the SFU attributes or the Active Directory primary
    group. If True, the primary group membership is fetched based on the gidNumber LDAP attribute, if set to False the
    primary group membership is calculated via the primaryGroupID LDAP attribute. """
    unix_nss_info: bool = False
    """ If set to True the login shell and home directory will be retrieved from the LDAP attributes. If set to False
    or if the Active Directory LDAP entry lacks SFU attribute, then the homedir will default to `/var/empty`. """


class Autorid_Idmap(IdmapDomainBase):
    """ The AUTORID backend provides a way to use an algoritmic mapping scheme to map UIDs and
    GIDs to SIDs in a way similar to the RID backend, but automatically configures the range to be
    used for each domain in the forest. """
    idmap_backend: Literal['AUTORID']
    rangesize: int = Field(default=100000, ge=10000, le=1000000000)
    """ Defines the number of uids / gids available per domain range. SIDs with RIDs larger than this value will be
    mapped into extension ranges depending on the number of available ranges."""
    readonly: bool = False
    """ Turn the module into read-only mode. No new ranges or mappings will be created in the idmap pool. """
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
    """ If set to False TrueNAS will not validate certificates presented by the remote LDAP server. Generally, it is a
    better strategy to use valid certificates or to import relevant certificates into the certificate trusted store in
    TrueNAS. """


class RFC2307_Idmap(IdmapDomainBase):
    """ The RFC2307 backend provides a way to read ID mappings from RFC2307 attributes provided by a standalone LDAP
    server. This backend is read only. If the target server is an Active Directory domain controller, then the AD
    backend should be used instead. """
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
    """ If set to False TrueNAS will not validate certificates presented by the remote LDAP server. Generally, it is a
    better strategy to use valid certificates or to import relevant certificates into the certificate trusted store in
    TrueNAS. """


class RID_Idmap(IdmapDomainBase):
    """ The RID backend provides an algorithmic mapping scheme to map UIDs and GIDs to SIDs. The UID or GID is
    determined by taking the RID value from the Windows Account SID and adding it to the base value specified by
    `range_low`. RID values in an Active Directory domain can large, especially as the domain ages, and so
    administrators should configure a range large enough to accomodate the current RID values being assigned by the RID
    master. One way to do this is to look review the RID assigned to a recently created account in Active Directory. If
    the RID is 500000, then the range specified for this backend must contain at least 500000 unix IDs (for example
    1000000 - 2000000). """
    idmap_backend: Literal['RID']
    sssd_compat: bool = False
    """ Generate an idmap low range based on the algorithm used by SSSD to allocate IDs. This is sufficient if the
    domain is configured in such a way that it only consumes a
    single SSSD idmap slice."""


class BuiltinDomainTdb(IdmapDomainBase):
    """ Idmap ranges and information for BUILTIN, system accounts, and other accounts that are not explicitly mapped
    for a known domain. """
    range_low: IdmapId = 90000001
    """ The lowest UID or GID that the idmap backend may assign. """
    range_high: IdmapId = 100000000
    """ The highest UID or GID that the idmap backend may assign. """


DomainIdmap = Annotated[
    AD_Idmap | LDAP_Idmap | RFC2307_Idmap | RID_Idmap,
    Field(discriminator='idmap_backend', default=RID_Idmap(idmap_backend='RID'))
]


class PrimaryDomainIdmap(BaseModel):
    builtin: BuiltinDomainTdb = Field(default=BuiltinDomainTdb())
    """ uid/gid range configuration for automatically-generated accounts that are associated with well-known and
    builtin accounts on Windows servers. """
    idmap_domain: DomainIdmap
    """ Configuration for how accounts in the domain to which TrueNAS is joined are mapped into Unix uids and gids on
    the TrueNAS server. The majority of TrueNAS deployments use the RID backend which algorithmically assigns uids and
    gids based on the active directory account SID. Another common configuration is the `AD` backend which reads
    pre-defined active directory LDAP schema attributes that assign explicit uid and gid numbers to accounts."""


class PrimaryDomainIdmapAutoRid(BaseModel):
    idmap_domain: Autorid_Idmap


class CredKRBPrincipal(BaseModel):
    credential_type: Literal[DSCredType.KERBEROS_PRINCIPAL]
    principal: NonEmptyString
    """ A kerberos principal is a unique identity to which Kerberos can assign tickets.
    The specified kerberos principal must have an entry within a keytab on the TrueNAS server."""


class CredKRBUser(BaseModel):
    credential_type: Literal[DSCredType.KERBEROS_USER]
    username: NonEmptyString
    """ Username of the account to use to create a kerberos ticket for authentication to directory services. This
    account must exist on the domain controller. """
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


AD_IPA_Cred = Annotated[CredKRBUser | CredKRBPrincipal, Field(discriminator='credential_type')]


LDAP_Cred = Annotated[
    CredKRBUser | CredKRBPrincipal | CredLDAPPlain | CredLDAPAnonymous | CredLDAPMTLS,
    Field(discriminator='credential_type')
]


class DirectoryServiceBase(BaseModel):
    id: int
    enable: bool
    """ Enable the directory service. If TrueNAS has never joined the specified domain, then setting this to True will
    cause TrueNAS to attempt to join the domain. Note that the domain join process for Active Directory and IPA will
    make changes to the domain such as creating a new computer account for the TrueNAS server and creating DNS records
    for TrueNAS. """
    enable_account_cache: bool = Field(default=True)
    """ Enable backend caching for user and group lists. If enabled, then directory services users and groups will be
    presented as choices in the UI dropdowns and in API responses for user and group queries. This also controls
    whether users and groups will appear in `getent` results. In some edge cases this may be disabled in order to
    reduce load on the directory server. """
    timeout: int = Field(default=10, ge=5, le=40)
    """ The timeout value for DNS queries that are performed as part of the join process and NETWORK_TIMEOUT for LDAP
    requests. """
    kerberos_realm: NonEmptyString | None = Field(default=None)
    """ Name of kerberos realm to use for authentication to the specified directory service. If None, then kerberos
    will not be used for binding to the configured directory service. When initially joining an Active Directory or IPA
    domain, the realm will be automatically detected and configured if the realm is not specified. """


class ActiveDirectoryConfig(DirectoryServiceBase):
    """ Join the TrueNAS server to an existing Active Directory domain. """
    service_type: Literal['ACTIVEDIRECTORY']
    credential: AD_IPA_CRED | None = Field(example=[
        {
            'credential_type': 'KERBEROS_USER',
            'username': 'truenas_user',
            'password': 'Canary'
        },
        {
            'credential_type': 'KERBEROS_PRINCIPAL',
            'principal': 'truenas$@LDAP01.INTERNAL'
        }
    ])
    """ Credential to use for joining and connecting to the Active Directory domain. A KERBEROS_USER credential must be
    used to initially join the Active Directory domain, which will then be replaced by a KERBEROS_PRINCIPAL credential
    for the TrueNAS server's active directory computer account after the domain join completes. """
    hostname: NonEmptyString = Field(example='truenasnyc')
    """ Hostname of TrueNAS server to register in active directory. """
    domain: NonEmptyString = Field(example='mydomain.internal')
    """ Full DNS domain name of the Active Directory Domain. This should not be a domain controller. """
    enable_dns_updates: bool = Field(default=True)
    """ Enable automatic DNS updates for the TrueNAS server in the domain via nsupdate and gssapi / TSIG. """
    idmap: PrimaryDomainIdmap | PrimaryDomainIdmapAutoRid = Field(default=PrimaryDomainIdmap(), example=[
        {
            'builtin': {'range_low': 90000001, 'range_high': 100000000},
            'idmap_domain': {
                'name': 'MYDOMAIN',
                'idmap_backend': 'RID',
                'range_low': 100000001,
                'range_high': 200000000,
            },
        },
        {
            'idmap_domain': {
                'name': 'MYDOMAIN',
                'idmap_backend': 'AUTORID',
                'range_low': 90000001,
                'range_high': 2000000000
            }
        }
    ])
    """ Configuration for how to map Active Directory accounts into accounts on the TrueNAS server. The exact settings
    required here may vary based on how other servers and Linux clients are configured in the domain. Defaults are
    reasonable for a new deployment without existing support for unix-like operating systems. """
    site: NonEmptyString | None = Field(default=None, example='CORP-NYC')
    """ The Active Directory site in which the TrueNAS server is located. This will be auto detected during the domain
    join process. """
    computer_account_ou: NonEmptyString | None = Field(default=None, example='TRUENAS_SERVERS/NYC')
    """ Override for the default organizational unit (OU) in which to create the TrueNAS computer account during the
    domain join. This may be used to specify a custom location for TrueNAS computer accounts. """
    use_default_domain: bool = Field(default=False)
    """ Controls whether domain users and groups have a prefix prepended to the user account.  If this is enabled, then
    Active Directory users will appear as "administrator" instead of "EXAMPLE\\administrator". In most circumstances
    this should be disabled as collisions between active directory and local user account names can result in undefined
    behavior. """
    enable_trusted_domains: bool = Field(default=False)
    """ Enable support for trusted domains. If True, then separate trusted domain configuration must be set for all
    trusted domains. """
    trusted_domains: list[DomainIdmap] = Field(default=[], example=[
        {
            'name': 'BROOK',
            'idmap_backend': 'RID',
            'range_low': 200000001,
            'range_high': 300000000
        },
        {
            'name': 'DARVO',
            'idmap_backend': 'RID',
            'range_low': 300000001,
            'range_high': 400000000
        }
    ])
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


class LDAPConfig(DirectoryServiceBase):
    """ Bind the TrueNAS server to an existing LDAP server and use it as an account source.
    The TrueNAS defaults expect an OpenLDAP server, but other types of LDAP servers (excluding Active
    Directory) are possible as bind targets. """
    service_type: Literal['LDAP']
    credential: LDAP_CRED | None = Field(example=[
        {
            'credential_type': 'LDAP_PLAIN',
            'binddn': 'uid=truenasserver,ou=Users,dc=ldap01,dc=internal',
            'bindpw': 'Canary'
        },
        {
            'credential_type': 'LDAP_ANONYMOUS'
        },
        {
            'credential_type': 'LDAP_MTLS',
            'client_certificate': 'ldap01_client_cert'
        },
        {
            'credential_type': 'KERBEROS_USER',
            'username': 'truenas_user',
            'password': 'Canary'
        },
        {
            'credential_type': 'KERBEROS_PRINCIPAL',
            'principal': 'truenas@LDAP01.INTERNAL'
        }
    ])
    """ Credential to use for binding to the specified LDAP server_urls. The available authentication mechanisms
    depend on the how the remote LDAP servers are configured.  If kerberos credential types are selected then GSSAPI
    binds will be performed in lieu of plain ldap binds. KERBEROS_PRINCIPAL and LDAP_MTLS authentication are
    preferred to improve server authentication security. """
    server_urls: list[LDAP_URL] = Field(example=['ldaps://myldap.domain.internal'])
    """ List of LDAP server URIs to use for LDAP binds. Each server may be a DNS name or IP address and must
    be prefixed by "ldap://" or "ldaps://". """
    starttls: bool = Field(default=False)
    """ Establish TLS by transmitting a StartTLS request to the server. """
    basedn: LDAP_DN = Field(example='dc=domain,dc=internal')
    """ The base DN to use when performing LDAP operations. """
    validate_certificates: bool = Field(default=True)
    """ If set to False TrueNAS will not validate certificates presented by the remote LDAP server. Generally, it is a
    better strategy to use valid certificates or to import relevant certificates into the certificate trusted store in
    TrueNAS. """
    ldap_schema: Literal['RFC2307', 'RFC2307BIS'] = Field(default='RFC2307', alias='schema')
    """ The LDAP attribute schema type used by the remote LDAP server. The RFC2307 schema is used by most LDAP
    servers. """
    search_bases: LDAPSearchBases = Field(default=LDAPSearchBases())
    """ Alternative LDAP search base configuration. These configuration options allow for specifying the DN in which to
    find user, group, and netgroup entries. If unspecified (the default) then all users, groups, and netgroups within
    the specified `basedn` will be available on TrueNAS.These are only required if using a non-standard LDAP schema. """
    attribute_maps: LDAPAttributeMaps = Field(default=LDAPAttributeMaps())
    """ Alertative LDAP attribute map configuration for LDAP implementations that are non-compliant with RFC2307 or
    RFC2307BIS. These are only required if using a non-standard LDAP schema. """
    auxiliary_parameters: LongNonEmptyString | None = None
    """ Additional parameters that may be inserted into the SSSD running configuration. These are not validated and may
    result in production outages on application or on upgrade. """


class IPAConfig(DirectoryServiceBase):
    """ Join the the TrueNAS server to an existing FreeIPA domain. """
    service_type: Literal['IPA']
    credential: AD_IPA_CRED | None = Field(example=[
        {
            'credential_type': 'KERBEROS_USER',
            'username': 'truenas_user',
            'password': 'Canary'
        },
        {
            'credential_type': 'KERBEROS_PRINCIPAL',
            'principal': 'host/truenas@LDAP01.INTERNAL'
        }
    ])
    """ Credential to use for joining and connecting to the FreeIPA domain. A KERBEROS_USER credential must be used to
    initially join the FreeIPA domain, which will then be replaced by a KERBEROS_PRINCIPAL credential for the TrueNAS
    server's FreeIPA computer account after the domain join completes. """
    target_server: NonEmptyString = Field(example='ipa.example.internal')
    """ The hostname of the IPA server to use when constructing URLs during IPA operations when joining or leaving the
    IPA domain. """
    hostname: NonEmptyString = Field(example='truenasnyc')
    """ Hostname of TrueNAS server to register in IPA during the join process. """
    domain: NonEmptyString = Field(example='example.internal')
    """ The domain of the IPA server """
    basedn: LDAP_DN = Field(example='dc=example,dc=internal')
    """ The base DN to use when performing LDAP operations. """
    smb_domain: IPA_SMBDomain | None = Field(default=None)
    """ Configuration for IPA SMB domain. Not all IPA domains will have SMB schema changes present. """
    validate_certificates: bool = Field(default=True)
    """ If set to False TrueNAS will not validate certificates presented by the remote LDAP server. Generally, it is a
    better strategy to use valid certificates or to import relevant certificates into the certificate trusted store in
    TrueNAS. """
    enable_dns_updates: bool = Field(default=True)
    """ Enable automatic DNS updates for the TrueNAS server in the domain via nsupdate and gssapi / TSIG. """


class StandaloneConfig(BaseModel):
    """ The TrueNAS server has no directory services configuration. """
    id: int
    service_type: Literal[None]
    enable: bool
    """ The enable field exists for standalone directory services configuration solely for the purpose of providing
    consistent field availabilty for API consumers. The configuration may never be explicitly enabled. """


DirectoryServicesEntry = Annotated[
    ActiveDirectoryConfig | IPAConfig | LDAPConfig | StandaloneConfig,
    Field(discriminator='service_type')
]


@single_argument_args('directoryservices_update')
class DirectoryServicesUpdateArgs(DirectoryServicesEntry, metaclass=ForUpdateMetaclass):
    """ Update the directory services configuration with the specified payload. If service_type is set to None and
    enable is False, then the all existing directory service configuration will be cleared.


    Note about domain joins:
   
    IPA and Active Directory directory service types perform a join operation the first time they are enabled, which
    results in the creation of a domain account for the TrueNAS server. This account's credentials, which are in the
    form of a machine account keytab, will be used for all further domain-related operations.
    """
    id: Excluded = excluded_field()
    force: bool = Field(default=False)
    """ Bypass validation for whether a server with this hostname and netbios name is already registered in an IPA or
    Active Directory domain. This may be used, for example, to replace an existing sever with a TrueNAS server. The
    force parameter should not be used indiscriminately as doing so may result in production outages for any client
    using an existing server that conflicts with this TrueNAS server when TrueNAS overwrites the existing account. """

    @model_validator(mode='after')
    def validate_ds(self):
        if self.service_type == undefined and self.enable is not False:
            raise ValueError('service_type is required in update payloads')

        if self.enable is True:
            if self.service_type is None:
                raise ValueError('Standalone configuration may not be explicitly enabled.')
            elif self.credential in (None, undefined):
                raise ValueError('Explicit credential configuration is required when service_type is specified')

        return self


class DirectoryServicesUpdateResult(BaseModel):
    result: DirectoryServicesEntry


@single_argument_args('credential')
class DirectoryServicesLeaveArgs(BaseModel):
    credential: CredKRBUser


class DirectoryServicesLeaveResult(BaseModel):
    result: None
