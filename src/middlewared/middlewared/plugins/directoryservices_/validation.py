import errno
import ldap

from middlewared.service import Service, private
from middlewared.service_exception import CallError, ValidationErrors
from middlewared.utils.directoryservices.ad import get_domain_info
from middlewared.utils.directoryservices.constants import DSCredentialType, DSType
from middlewared.utils.directoryservices.ldap_utils import (
    ds_config_to_ldap_client_config,
)
from middlewared.utils.directoryservices.ldap_client import LdapClient
from middlewared.utils.directoryservices.krb5_constants import MAX_TIME_OFFSET
from middlewraed.utils.directoryservices.krb5_error import KRB5Error, KRB5ErrCode

SCHEMA_PREFIX = 'directoryservices.update'
SCHEMA_CONF_PREFIX = f'{SCHEMA_PREFIX}.configuration'
AD_ENABLED_SAFE_KEYS = frozenset(['allow_trusted_doms', 'use_default_domain'])


class DirectoryServices(Service):
    class Config:
        service = 'directoryservices'

    def __validate_dstype(self, old: dict, new: dict, verrors: ValidationErrors) -> None:
        """ very basic validation to prevent egregious errors related to dstype key """
        if old['enable']:
            # Force user to cleanly disable / stop directory services before
            # allowing changing directory services type. This is not a normal
            # admin operation and so taking the extra step to require clean stop is OK.
            if new['dstype'] and new['dstype'] != old['dstype']:
                verrors.add(
                    f'{SCHEMA_PREFIX}.dstype',
                    'dstype may not be changed while directory services are enabled.'
                )

        if new['enable'] and new['dstype'] == DSType.STANDALONE:
            verrors.add(
                f'{SCHEMA_PREFIX}.dstype',
                'STANDALONE configuration may not be explicitly enabled'
            )

    def __validate_kerberos_credentials(
        self,
        creds: dict,
        realm: str,
        target_server: str | None,
        verrors: ValidationErrors
    ) -> None:
        """
        Check that we can kinit with supplied credentials

        NOTE: when we exit this method we will have valid tgt.
        """
        match creds['credential_type']:
            case DSCredentialType.KERBEROS_PRINCIPAL:
                kinit_cred = {'kerberos_principal': creds['kerberos_principal']}
                cred_key = f'{SCHEMA_CONF_PREFIX}.credential.kerberos_principal'
            case DSCredentialType.USERNAME_PASSWORD:
                kinit_cred = {
                    'username': f'{creds["bindname"]}@{realm}',
                    'password': creds['bindpw']
                }
                cred_key = f'{SCHEMA_CONF_PREFIX}.credential.bindname'
            case DSCredentialType.LDAPDN_PASSWORD:
                # Try to guess at turning our binddn into a kerberos account
                first_dn = creds['binddn'].split(',')[0]
                username = first_dn.split('=')[1]
                kinit_cred = {
                    'username': f'{username}@{realm}',
                    'password': creds['bindpw']
                }
                cred_key = f'{SCHEMA_CONF_PREFIX}.credential.binddn'
            case _:
                verrors.add(
                    f'{SCHEMA_CONF_PREFIX}.credential.credential_type',
                    'Unsupported credential type for kerberos authentication.'
                )
                return

        try:
            self.middleware.call_sync('kerberos.do_kinit', {
                'krb5_cred': kinit_cred,
                'kinit_options': {'kdc_override': {'domain': realm, 'kdc': target_server}}
            })
        except KRB5Error as e:
            match e.krb5_code:
                case KRB5ErrCode.KRB5_LIBOS_CANTREADPWD:
                    if creds['credential_type'] == DSCredentialType.KERBEROS_PRINCIPAL:
                        msg = 'Kerberos keytab is no longer valid.'
                    else:
                        msg = 'Account password is expired.'
                case KRB5ErrCode.KRB5KDC_ERR_CLIENT_REVOKED:
                    msg = 'Account is locked.'
                case KRB5ErrCode.KRB5_CC_NOTFOUND:
                    if creds['credential_type'] == DSCredentialType.KERBEROS_PRINCIPAL:
                        # possibly toctou issue on concurrent system keytab changes
                        choices = self.middleware.call_sync('kerberos.keytab.kerberos_principal_choices')
                        msg = (
                            'System keytab lacks an entry for the specified kerberos principal. '
                            f'Please select a valid kerberos principal from available choices: {", ".join(choices)}'
                        )
                    else:
                        msg = str(e)
                case KRB5ErrCode.KRB5KDC_ERR_POLICY:
                    msg = (
                        'Domain controller security policy rejected request to obtain kerberos ticket. '
                        'This may occur if the bind account has been configured to deny interactive '
                        'logons or require two-factor authentication. Depending on organizational '
                        'security policies, one may be required to pre-generate a kerberos keytab '
                        'and upload to TrueNAS server for use during join process.'
                    )
                case KRB5ErrCode.KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN:
                    # We're dealing with a missing account
                    msg = (
                        'Client\'s credentials were not found on remote domain controller. The most '
                        'common reasons for the domain controller to return this response is due to a '
                        'typo in the service account name or the service or the computer account being '
                        'deleted from the domain.'
                    )
                case KRB5ErrCode.KRB5KRB_AP_ERR_SKEW:
                    # Domain permitted clock skew may be more restrictive than our basic
                    # check of no greater than 3 minutes.
                    msg = (
                        'The time offset between the TrueNAS server and the domain controller exceeds '
                        'the maximum value permitted by the domain configuration. This may occur if '
                        'NTP is improperly configured on the TrueNAS server or if the hardware clock '
                        'on the TrueNAS server is configured for a local timezone instead of UTC.'
                    )
                case KRB5ErrCode.KRB5KDC_ERR_PREAUTH_FAILED:
                    if creds['credential_type'] == DSCredentialType.KERBEROS_PRINCIPAL:
                        msg = (
                            'Kerberos principal credentials are no longer valid. Rejoining active directory '
                            'may be required.'
                        )
                    else:
                        msg = 'Preauthentication failed. This typically indicates an incorrect bind password.'
                case _:
                    # Catchall for kerberos errors. This will expand as we have
                    msg = str(e)

            verrors.add(cred_key, msg)

        except CallError as ce:
            # This may be an encapsulated GSSAPI library error
            if ce.errno == errno.EINVAL:
                # GSSAPI BadName exception
                if creds['credential_type'] == DSCredentialType.KERBEROS_PRINCIPAL:
                    msg = 'Not a valid principal name.'
                else:
                    msg = 'Not a valid username.'

                verrors.add(cred_key, msg)

            else:
                # No meaningful way to convert into a ValidationError, simply re-raise
                raise ce

    def __validate_ldap_credentials(self, new: dict, verrors: ValidationErrors) -> None:
        dsconfig = new['configuration']

        if dsconfig['kerberos_realm']:
            self.__validate_kerberos_credentials(
                dsconfig['credentials'],
                dsconfig['kerberos_realm'],
                dsconfig['server_hostnames'][0],
                verrors
            )
            # Make sure we catch kerberos errors early before trying GSSAPI bind
            verrors.check()

        client_config = ds_config_to_ldap_client_config(new)
        match new['configuration']['credentials']['credential_type']:
            case DSCredentialType.KERBEROS_PRINCIPAL:
                cred_key = f'{SCHEMA_CONF_PREFIX}.credential.kerberos_principal'
            case DSCredentialType.LDAPDN_PASSWORD:
                cred_key = f'{SCHEMA_CONF_PREFIX}.credential.binddn'
            case DSCredentialType.CERTIFICATE:
                cred_key = f'{SCHEMA_CONF_PREFIX}.credential.client_certificate'
            case DSCredentialType.ANONYMOUS:
                cred_key = f'{SCHEMA_CONF_PREFIX}.credential'
            case _:
                raise ValueError('Unexpected credential type')
        try:
            LdapClient.open(client_config, True)
        except ldap.INVALID_CREDENTIALS:
            verrors.add(cred_key, 'Remote LDAP server returned response that credentials were invalid.')
        except ldap.NO_SUCH_OBJECT:
            verrors.add(f'{SCHEMA_CONF_PREFIX}.basedn', 'basedn does not exist on LDAP server.')
        except ldap.INVALID_DN_SYNTAX:
            verrors.add(f'{SCHEMA_CONF_PREFIX}.basedn', 'basedn is syntactically invalid.')
        except ldap.STRONG_AUTH_NOT_SUPPORTED:
            verrors.add(cred_key, 'Certificate-based authentication is not supported by LDAP server.')
        except ldap.SERVER_DOWN:
            verrors.add(f'{SCHEMA_CONF_PREFIX}.server_hostnames', 'LDAP server is unreachable')
        except ldap.CONFIDENTIALITY_REQUIRED:
            verrors.add(f'{SCHEMA_CONF_PREFIX}.ssl_config.ssl', 'SSL/TLS encrypted transport is required.')
        except Exception as e:
            verrors.add(cred_key, str(e))

    def __validate_remote_credentials(self, new: dict, target_server: str | None, verrors: ValidationErrors) -> None:
        """ validate supplied credentials are sufficient for DS operations """
        match new['dstype']:
            case DSType.STANDALONE:
                return
            case DSType.AD | DSType.IPA:
                self.__validate_kerberos_credentials(
                    new['configuration']['credentials'],
                    new['configuration']['domainname'],
                    target_server,
                    verrors
                )
            case _:
                # LDAP will be handled separately
                raise ValueError(f'{new["dstype"]}: unexpected dstype')

    def __validate_activedirectory(self, old: dict, new: dict, verrors: ValidationErrors) -> None:
        dsconfig = new['configuration']

        # If we're not enabling the service we can exit early. This is for
        # convenience of admin who may be doing offline changes and wants to avoid
        # performing remote checks on incomplete information.
        if not new['enable']:
            return

        failover_licensed = self.middleware.call_sync('failover_licensed')

        if dsconfig['allow_trusted_doms'] and not self.middleware.call_sync('idmap.may_enable_trusted_domains'):
            verrors.add(
                f'{SCHEMA_CONF_PREFIX}.allow_trusted_doms',
                'Configuration for trusted domains requires that the idmap backend '
                'be configured to handle these domains. There are two possible strategies to '
                'achieve this. The first strategy is to use the AUTORID backend for the domain '
                'to which TrueNAS is joined. The second strategy is to separately configure idmap '
                'ranges for every domain that has a trust relationship with the domain to which '
                'TrueNAS is joined and which has accounts that will be used on the TrueNAS server. '
                'NOTE: the topic of how to properly map Windows SIDs to Unix IDs is complex and '
                'may require consultation with administrators of other Unix servers in the '
                'Active Directory domain to properly coordinate a comprehensive ID mapping strategy.'
            )

        if failover_licensed and self.middleware.call_sync('systemdataset.is_boot_pool'):
            verrors.add(
                f'{SCHEMA_PREFIX}.enable',
                'Active directory integration may not be enabled while system dataset is on boot pool'
            )

        if new['enable'] is True and old['enable'] is True:
            for key in new['configuration'].keys():
                if key in AD_ENABLED_SAFE_KEYS or old['configuration'][key] == new['configuration'][key]:
                    continue

                verrors.add(
                    f'{SCHEMA_CONF_PREFIX}.{key}',
                    'Parameter may not be changed while Active Directory service is enabled'
                )

            # We're already running / enabled and so don't need further validation
            return

        # The below checks may variously return early because success is required for the next
        # validation step.
        try:
            domain_info = get_domain_info(dsconfig['domainname'])
        except CallError as ce:
            verrors.add(f'{SCHEMA_CONF_PREFIX}.domainname', ce.errmsg)
            return

        if abs(domain_info['server_time_offset']) > MAX_TIME_OFFSET:
            verrors.add(
                f'{SCHEMA_CONF_PREFIX}.domainname',
                f'Time offset from Active Directory domain (domain_info["server_time_offset]) '
                f'exceeds maximum permitted value of ({MAX_TIME_OFFSET}). This may indicate an NTP '
                'misconfiguration.'
            )
            return

        self.__validate_remote_credentials(dsconfig['credential'], domain_info['kdc_server'], verrors)

    def __validate_ldap(self, old: dict, new: dict, verrors: ValidationErrors) -> None:
        if not new['enable']:
            return

        self.__validate_ldap_credentials(new, verrors)

    def __clean_config(self, old: dict, new: dict) -> dict:
        cleaned = {
            'dstype': new['dstype'],
            'enable': new['enable'],
            'enable_cache': new['enable_cache'],
            'configuration': None,
            'timeout': old['timeout'].copy() | new['timeout']
        }

        if old['dstype'] != new['dstype']:
            # we've changed type so no config is preserved
            cleaned['configuration'] = new['configuration']
            return cleaned

        if not new['credential']:
            new['credential'] = old['credential']

        for key in ('ssl_config', 'server_hostnames'):
            if key in old['configuration'] and not new[configuration]:
                new['configuration'][key] = old['configuration'][key]

        # We don't want to pass any explicit None to backend
        # on update.
        """
        for key in list(old['configuration'].keys()):
            if new['configuration'][key] is None:
                del new['configuration'][key]
        """

        cleaned['configuration'] = old['configuration'] | new['configuration']
        return cleaned

    @private
    def validate_and_clean(self, old: dict, data: dict) -> dict:
        """ Validate and normalize payload """
        verrors = ValidationErrors()
        new = self.__clean_config(old, data)
        self.__validate_dstype(old, new, verrors)
        verrors.check()

        # Initialize the key to None because we automatically create realm when
        # joining AD or IPA.
        new['configuration']['kerberos_realm_id'] = None

        if new['configuration']['kerberos_realm']:
            # We need to look up case-insensitive in case user has fat-fingered
            # input. There will be no case in which there are two kerberos realms on
            # network that are only differentiated by case. This would significantly
            # break some kerberos clients.
            kerberos_realm = self.middleware.call('kerberos.realm.query', [
                ['realm', 'C=', new['configuration']['kerberos_realm']]
            ])
            if not kerberos_realm:
                verrors.add(
                    f'{SCHEMA_CONF_PREFIX}.kerberos_realm',
                    'Kerberos realm does not exist'
                )
            else:
                new['configuration']['kerberos_realm_id'] = kerberos_realm[0]['id']

        if new['configuration']['credential']['credential_type'] == DSCredentialType.CERTIFICATE:
            cert_name = new['configuration']['credential']['client_certificate']
            certificate = self.middleware.call_sync('certificate.query', [['cert_name', '=', cert_name]])
            if not certificate:
                verrors.add(
                    f'{SCHEMA_CONF_PREFIX}.credential.client_certificate',
                    f'{cert_name}: certificate does not exist'
                )
                new['configuration']['credential']['client_certificate_id'] = None
            else:
                new['configuration']['credential']['client_certificate_id'] = certificate[0]['id']

        # catch realm and client cert errors before trying to validate remote server
        verrors.check()

        match new['dstype']:
            case DSType.AD:
                self.__validate_activedirectory(old, new, verrors)
            case DSType.IPA:
                self.__validate_ipa(old, new, verrors)
            case DSType.LDAP:
                self.__validate_ldap(old, new, verrors)

        verrors.check()

        return new
