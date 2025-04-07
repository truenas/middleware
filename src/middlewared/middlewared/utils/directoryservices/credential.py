import errno
import gssapi

from middlewared.service_execption import CallError, ValidationErrors
from .ad import get_domain_info, lookup_dc
from .constants import DSCredType, DSType
from .krb5 import (
    gss_get_current_cred,
    gss_acquire_cred_principal,
    gss_acquire_cred_user,
    gss_dump_cred,
    ktutil_list_impl,
)
from .krb5_conf import KRB5Conf
from .krb5_constants import (
    krb5ccache, KRB_Keytab, MAX_TIME_OFFSET, PERSISTENT_KEYRING_PREFIX, KRB_LibDefaults,
    KRB_TKT_CHECK_INTERVAL,
)
from .krb5_error import KRB5Error


def __kinit_with_principal(kerberos_principal: str, ccache: str, lifetime: int | None) -> gssapi.Credentials:
    try:
        return gss_acquire_cred_principal(cred['kerberos_principal'], ccache)
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
    if kdestroy.returnconde != 0:
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
            if (krbcred := __get_current_cred(cred['kerberos_principal'])) is None:
                krbcred = __kinit_with_principal(cred['kerberos_principal'], ccache, lifetime)
        case DSCredType.KERBEROS_USER:
            if (krbcred := __get_current_cred(cred['username'])) is None:
                krbcred = __kinit_with_user(cred['username'], cred['password'], ccache, lifetime)
        case _:
            raise ValueError(f'{cred_type}: not a kerberos credential type')

    return gss_dump_cred(krbcred)


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

        case DSType.IPA:
            if not kdc:
                kdc.append(new['configuration']['host']) 

            if not realm:
                realm = new['configuration']['domain']

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
        libdefaults.update({
            str(KRB_LibDefaults.DNS_LOOKUP_KDC): 'false',
            str(KRB_LibDefaults.DNS_CANONICALIZE_HOSTNAME): 'false',
        })

    realms = [{
        'realm': realm,
        'admin_server' = [],
        'kdc' = kdc,
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

    # if we already have a kerberos ticket as the requried user, then don't bother
    # trying to re-validate it.
    if krb_cred := gss_get_current_cred(krb5ccache.SYSTEM.value, False):
        dump = gss_dump_cred(krb_cred)
        if dump['name_type'] == cred['credential_type']:
            match cred['credential_type']:
                case DSCredType.KERBEROS_PRINCIPAL:
                    if cred['kerberos_principal'] == cred['name']:
                        return
                case DSCredType.KERBEROS_USER:
                    if cred['username'] == cred['name']:
                        return
                case _:
                    raise ValueError(f'{cred}: unhandled DSCredType')

    # Write out a temporary kerberos config that gives the best chance of
    # success in finding a domain controller
    if not write_temporary_kerberos_config(schema, new, verrors, revert):
        # Failed to write our kerberos config so we'll bail
        return

    # Now try to kinit
    if krb_cred == DSCredType.KERBEROS_PRINCIPAL:
        # check that kerberos principal exists in our keytab
        if not any([k['principal'] == cred['kerberos_principal'] for k in ktutil_list_impl(KRB_Keytab.SYSTEM.value)]):
            verrors.add(
                f'{schema}.credential.kerberos_principal',
                'Specified kerberos principal does not exist on the TrueNAS server.'
            )
            return

        key = f'{schema}.credential.kerberos_principal'
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
                    msg = f'Account password for {cred["username"]} is expired'
            case KRB5ErrCode.KRB5KDC_ERR_CLIENT_REVOKED:
                msg = 'Account is locked.'
            case KRB5ErrCode.KRB5_CC_NOTFOUND:
                if krb_cred == DSCredType.KERBEROS_PRINCIPAL:
                    # We should have already checked this above, but may be TOCTOU
                    msg = 'System keytab lacks an entry for the specified kerberos principal.'
                else:
                    # This shouldn't happen with user kinit
                    msg = str(krb_err)
            case KRB5ErrCode.KRB5KDC_ERR_POLICY:
                msg = (
                    'The domain controller security policy has rejected the request to obtain '
                    'a kerberos ticket. This may occur if the bind account has been configured '
                    'to deny interactive logins or if it requires two-factor authentication.'
                )
            case KRB5ErrCode.KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN:
                msg = (
                    'The specified credentials were not found on the remote domain controller. '
                    'This may indicate a typo in the user or principal name or that the account '
                    'has been deleted from the remote domain controller.'
                )
            case KRB5ErrCode.KRB5KRB_AP_ERR_SKEW:
                # This may be more restrictive than our hard-coded 3 minute default
                msg = (
                    'The time offset from the domain controller exceeds the maximum value '
                    'allowed by the domain controller.'
                )
            case KRB5ErrCode.KRB5KDC_ERR_PREAUTH_FAILED:
                if krb_cred == DSCredType.KERBEROS_PRINCIPAL:
                    msg = 'Kerberos principal credentials are no longer valid. Domain rejoin is required.'
                else:
                    msg = 'Bind password is incorrect.'
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
            __validate_ldap_credential(schema, new, verrors, revert)
        case _:
            raise ValueError(f'{cred}: unhandled DSCredType')
