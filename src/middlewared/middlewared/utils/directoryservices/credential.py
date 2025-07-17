import errno
import gssapi
import ldap
import subprocess

from middlewared.service_exception import CallError, ValidationErrors
from .ad import get_domain_info
from .constants import DSCredType, DSType
from .krb5 import (
    gss_get_current_cred,
    gss_acquire_cred_principal,
    gss_acquire_cred_user,
    gss_dump_cred,
    ktutil_list_impl,
    kdc_saf_cache_set,
)
from .krb5_conf import KRB5Conf
from .krb5_constants import (
    krb5ccache, KRB_Keytab, MAX_TIME_OFFSET, PERSISTENT_KEYRING_PREFIX, KRB_LibDefaults,
    KRB_TKT_CHECK_INTERVAL,
)
from .krb5_error import KRB5Error, KRB5ErrCode
from .ldap_client import LdapClient


def __kinit_with_principal(kerberos_principal: str, ccache: str, lifetime: int | None) -> gssapi.Credentials:
    try:
        return gss_acquire_cred_principal(kerberos_principal, ccache, lifetime)
    except gssapi.exceptions.BadNameError:
        raise CallError(f'{kerberos_principal}: not a valid kerberos principal name.', errno.EINVAL)
    except gssapi.exceptions.MissingCredentialsError as exc:
        if exc.min_code & 0xFF:
            # Kerberos error wrapped up in GSSAPI error
            raise KRB5Error(gss_major=exc.maj_code, gss_minor=exc.min_code, errmsg=exc.gen_message())

        # A more unfortunate GSSAPI error
        raise CallError(str(exc))
    except Exception as exc:
        raise CallError(str(exc))


def __kinit_with_user(username: str, password: str, ccache: str, lifetime: int | None) -> gssapi.Credentials:
    try:
        return gss_acquire_cred_user(username, password, ccache, lifetime)
    except gssapi.exceptions.BadNameError:
        raise CallError(f'{username}: not a valid kerberos principal name.', errno.EINVAL)
    except gssapi.exceptions.MissingCredentialsError as exc:
        if exc.min_code & 0xFF:
            # Kerberos error wrapped up in GSSAPI error
            raise KRB5Error(gss_major=exc.maj_code, gss_minor=exc.min_code, errmsg=exc.gen_message())

        # A more unfortunate GSSAPI error
        raise CallError(str(exc))
    except Exception as exc:
        raise CallError(str(exc))


def __get_current_cred(cred_name, ccache):
    if (current_cred := gss_get_current_cred(ccache, False)) is None:
        return None

    if str(current_cred.name) == cred_name:
        if current_cred.lifetime > (KRB_TKT_CHECK_INTERVAL * 2):
            return current_cred

    # Expired / Expiring credential. We need to call kdestroy because ccache is
    # in kernel keyring
    kdestroy = subprocess.run(['kdestroy', '-c', ccache], check=False, capture_output=True)
    if kdestroy.returncode != 0:
        raise CallError(f'Kdestroy failed with error: {kdestroy.stderr.decode()}')

    return None


def kinit_with_cred(
    cred: dict, *,
    lifetime: int | None = None,
    ccache: str = krb5ccache.SYSTEM.value
) -> dict:
    """
    Higher level API around the GSSAPI libraries to perform kinit with credentials provided
    by `credential` key in `directoryservices.config`. This will convert GSSAPI errors to
    KRB5Error when applicable and dump a dictionary containing the resulting kerberos
    credential information.
    """
    cred_type = DSCredType(cred.get('credential_type'))
    match cred_type:
        case DSCredType.KERBEROS_PRINCIPAL:
            if not __get_current_cred(cred['principal'], ccache):
                __kinit_with_principal(cred['principal'], ccache, lifetime)
        case DSCredType.KERBEROS_USER:
            if not __get_current_cred(cred['username'], ccache):
                __kinit_with_user(cred['username'], cred['password'], ccache, lifetime)
        case _:
            raise ValueError(f'{cred_type}: not a kerberos credential type')

    return gss_dump_cred(gss_get_current_cred(ccache))


def write_temporary_kerberos_config(schema: str, new: dict, verrors: ValidationErrors, revert: list):
    """
    This method generates a kerberos configuration file that is written in such a way as to
    force TrueNAS to only use a single KDC and to avoid DNS lookups. This is to stabilize
    operations in domains with multiple domain controllers. If DNS is used to lookup KDCs
    then TrueNAS may create an account on one domain controller and them immediately transfer
    to a different domain controller that is not aware of the TrueNAS account because it has
    not been replicated yet.
    """
    ds_type = DSType(new['service_type'])
    kdc = new.get('kdc_override', [])
    realm = new.get('kerberos_realm')
    aux = []

    match ds_type:
        case DSType.AD:
            # Force domain to upper case
            new['configuration']['domain'] = new['configuration']['domain'].upper()
            try:
                domain_info = get_domain_info(new['configuration']['domain'], retry=True)
            except CallError as e:
                verrors.add(f'{schema}.configuration.domain', e.errmsg)
                return False

            if abs(domain_info['server_time_offset']) > MAX_TIME_OFFSET:
                verrors.add(
                    f'{schema}.configuration.domain',
                    'Time offset from the domain controller exceeds the maximum permitted value.'
                )
                return False

            if not kdc:
                kdc.append(domain_info['kdc_server'])

            if not realm:
                realm = new['configuration']['domain']

            new['configuration']['idmap']['idmap_domain']['name'] = domain_info['workgroup']
            new['kerberos_realm'] = realm

        case DSType.IPA:
            if not kdc:
                kdc.append(new['configuration']['target_server'])

            if not realm:
                realm = new['configuration']['domain'].upper()

            aux.append('udp_preference_limit=0')

        case DSType.LDAP:
            pass

        case _:
            raise ValueError(f'{ds_type}: unhandled DSType')

    if not realm:
        verrors.add(f'{schema}.kerberos_realm', 'Kerberos realm is required')
        return False

    libdefaults = {
        str(KRB_LibDefaults.DEFAULT_REALM): realm,
        str(KRB_LibDefaults.DNS_LOOKUP_REALM): 'false',
        str(KRB_LibDefaults.FORWARDABLE): 'true',
        str(KRB_LibDefaults.DEFAULT_CCACHE_NAME): PERSISTENT_KEYRING_PREFIX + '%{uid}'
    }

    if kdc:
        kdc_saf_cache_set(kdc[0])
        libdefaults.update({
            str(KRB_LibDefaults.DNS_LOOKUP_KDC): 'false',
            str(KRB_LibDefaults.DNS_CANONICALIZE_HOSTNAME): 'false',
        })

    realms = [{
        'realm': realm,
        'primary_kdc': None,
        'admin_server': [],
        'kdc': kdc,
        'kpasswd_server': []
    }]

    krbconf = KRB5Conf()
    krbconf.add_libdefaults(libdefaults, '\n'.join(aux))
    krbconf.add_realms(realms)
    krbconf.write()

    # Add step to regenerate the config file
    revert.append({'method': 'etc.generate', 'args': ['kerberos']})
    return True


def __validate_kerberos_credential(schema: str, new: dict, verrors: ValidationErrors, revert: list):
    cred = new['credential']
    krb_cred = cred['credential_type']

    # Write out a temporary kerberos config that gives the best chance of
    # success in finding a domain controller
    if not write_temporary_kerberos_config(schema, new, verrors, revert):
        # Failed to write our kerberos config so we'll bail. ValidationErrors are set by called method.
        return

    # Now try to kinit
    if krb_cred == DSCredType.KERBEROS_PRINCIPAL:
        # check that kerberos principal exists in our keytab
        if not any([k['principal'] == cred['principal'] for k in ktutil_list_impl(KRB_Keytab.SYSTEM.value)]):
            verrors.add(
                f'{schema}.credential.principal',
                'The TrueNAS server does not have the specified Kerberos principal.'
            )
            return

        key = f'{schema}.credential.principal'
    else:
        key = f'{schema}.credential.username'

    try:
        kinit_with_cred(cred)
    except KRB5Error as krb_err:
        match krb_err.krb5_code:
            case KRB5ErrCode.KRB5_LIBOS_CANTREADPWD:
                if krb_cred == DSCredType.KERBEROS_PRINCIPAL:
                    msg = 'Kerberos keytab is no longer valid.'
                else:
                    msg = f'The password for {cred["username"]} is expired.'
            case KRB5ErrCode.KRB5KDC_ERR_CLIENT_REVOKED:
                msg = 'The account is locked.'
            case KRB5ErrCode.KRB5_CC_NOTFOUND:
                if krb_cred == DSCredType.KERBEROS_PRINCIPAL:
                    # We should have already checked this above, but may be TOCTOU
                    msg = 'The system keytab does not have an entry for the specified Kerberos principal.'
                else:
                    # This shouldn't happen with user kinit
                    msg = str(krb_err)
            case KRB5ErrCode.KRB5KDC_ERR_POLICY:
                msg = (
                    'The domain controller security policy rejected the request to get a Kerberos ticket. '
                    'This can happen if the bind account is set to deny interactive logins or if it needs two-factor '
                    'authentication.'
                )
            case KRB5ErrCode.KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN:
                msg = (
                    'The remote domain controller does not have the specified credentials. '
                    'This can mean the user name or principal name is wrong, or the account was deleted.'
                )
            case KRB5ErrCode.KRB5KRB_AP_ERR_SKEW:
                # This may be more restrictive than our hard-coded 3 minute default
                msg = (
                    'The time difference from the domain controller is more than the maximum value allowed by the '
                    'domain controller.'
                )
            case KRB5ErrCode.KRB5KDC_ERR_PREAUTH_FAILED:
                if krb_cred == DSCredType.KERBEROS_PRINCIPAL:
                    msg = 'Kerberos principal credentials are not valid. You must rejoin the domain.'
                else:
                    msg = 'The bind password is not correct.'
            case _:
                # Catchall for kerberos errors
                msg = str(krb_err)

        verrors.add(key, msg)
    except CallError as exc:
        if exc.errno == errno.EINVAL:
            if krb_cred == DSCredType.KERBEROS_PRINCIPAL:
                msg = 'Not a valid principal name'
            else:
                msg = 'Not a valid username'
        else:
            # Unspecified error, possibly from GSSAPI
            msg = str(exc)

        verrors.add(key, msg)
    else:
        revert.append({'method': 'kerberos.kdestroy', 'args': []})


def dsconfig_to_ldap_client_config(data: dict) -> dict:
    """ transforms results of directoryservices.config into config for LDAP client """
    if not data['enable']:
        raise CallError('Directory services are not enabled')

    out = {
        'server_urls': None,
        'basedn': None,
        'credential': data['credential'],
        'validate_certificates': True,
        'starttls': False,
        'timeout': data['timeout']
    }

    match data['service_type']:
        case DSType.IPA.value:
            if data['credential']['credential_type'].startswith('KERBEROS'):
                out['server_urls'] = [f'ldap://{data["configuration"]["target_server"]}']
            else:
                out['server_urls'] = [f'ldaps://{data["configuration"]["target_server"]}']
            out['basedn'] = data['configuration']['basedn']
            out['validate_certificates'] = data['configuration']['validate_certificates']
        case DSType.LDAP.value:
            out['server_urls'] = data['configuration']['server_urls']
            out['basedn'] = data['configuration']['basedn']
            out['validate_certificates'] = data['configuration']['validate_certificates']
            out['starttls'] = data['configuration']['starttls']
        case _:
            raise CallError('LDAP client not supported for service type')

    return out


def validate_ldap_credential(schema, new, verrors, revert):
    """ Common synchronous method to validate LDAP client credentials """
    ldap_config = dsconfig_to_ldap_client_config(new)
    host_field = 'server_urls' if new['service_type'] == DSType.LDAP.value else 'target_server'
    try:
        # Use supplied credentials to connect to rootdse
        root = LdapClient.search(ldap_config, '', ldap.SCOPE_BASE, '(objectclass=*)')
    except ldap.CONFIDENTIALITY_REQUIRED:
        verrors.add(f'{schema}.configuration.{host_field}', 'The LDAP server needs encrypted transport.')
    except ldap.INVALID_CREDENTIALS:
        verrors.add(
            f'{schema}.credential.credential_type',
            'The LDAP server responded that the specified credentials are invalid.'
        )
    except ldap.STRONG_AUTH_NOT_SUPPORTED:
        # Past experience with user tickets has shown this as a common LDAP server response
        # to clients trying to use
        if new['credential']['credential_type'] == DSCredType.LDAP_MTLS:
            verrors.add(
                f'{schema}.credential.credential_type',
                'The LDAP server does not support mutual TLS authentication.'
            )
        else:
            verrors.add(
                f'{schema}.credential.credential_type',
                'The LDAP server does not support strong authentication.'
            )
    except ldap.SERVER_DOWN:
        # SSL libraries here don't do us a lot of favors. If the certificate is invald or
        # self-signed LDAPS connections will fail with SERVER_DOWN.
        verrors.add(
            f'{schema}.configuration.{host_field}',
            'TrueNAS cannot contact the LDAP server. This can happen if the LDAP server '
            'hostname cannot be resolved, the server does not respond, or if there is a '
            'cryptographic error such as a certificate validation failure.'
        )
    except ldap.INVALID_DN_SYNTAX as exc:
        verrors.add(
            f'{schema}.credential.basedn'
            f'Remote LDAP server returned that a specified DN ({exc[0]["matched"]}) is invalid.'
        )
    except ldap.LOCAL_ERROR as exc:
        info = exc.args[0].get('info', '')
        desc = exc.args[0].get('desc', '')
        if 'KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN' in info:
            # Past experience with user tickets has shown this to often be caused by RDNS issues
            verrors.add(
                f'{schema}.credential.credential_type',
                'The GSSAPI bind failed because the client was not found in the Kerberos database. '
                'This can happen if the Kerberos library failed to validate the Kerberos principal through reverse DNS.'
            )
        else:
            # Another local error (not from libldap)
            verrors.add(f'{schema}.credential.{host_field}', f'LDAP bind failed with error: {info} {desc}')
    except ldap.LDAPError as exc:
        verrors.add(f'{schema}.credential.{host_field}', f'LDAP bind failed with error: {exc}')
    else:
        # Check for problems in LDAP root. In theory we could check whether the server is
        # IPA based on presence of '389 Project' vendorName, but this would be a bit too agressive
        # and break some legacy users.
        if 'domainControllerFunctionality' in root:
            # Oddly enough in the past some users have tortured our LDAP configuration enough
            # to make it bind to AD and then filed tickets because SMB doesn't work properly
            # so we do a check to make sure they haven't decided to bark up the wrong tree.
            verrors.add(
                f'{schema}.server_type'
                'The remote server is an Active Directory domain controller. '
                'You must enable directory services with the ACTIVEDIRECTORY service_type to join an Active Directory '
                'domain. '
            )


def validate_credential(schema: str, new: dict, verrors: ValidationErrors, revert: list):
    """
    Validate credentials provided in `new`. This is primarily called from
    within directoryservices.update. Errors detected will be inserted into
    `verrors` and steps to revert will be appended to the `revert` list.
    """

    if new['credential'] is None:
        verrors.add(f'{schema}.credential', 'Credential is required.')
        return

    cred = DSCredType(new['credential']['credential_type'])

    match cred:
        case DSCredType.KERBEROS_USER | DSCredType.KERBEROS_PRINCIPAL:
            __validate_kerberos_credential(schema, new, verrors, revert)
        case DSCredType.LDAP_PLAIN | DSCredType.LDAP_ANONYMOUS | DSCredType.LDAP_MTLS:
            validate_ldap_credential(schema, new, verrors, revert)
        case _:
            raise ValueError(f'{cred}: unhandled DSCredType')
