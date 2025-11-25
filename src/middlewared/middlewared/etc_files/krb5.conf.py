import logging

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.filter_list import filter_list
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.krb5 import kdc_saf_cache_get
from middlewared.utils.directoryservices.krb5_conf import KRB5Conf
from middlewared.utils.directoryservices.krb5_constants import KRB_LibDefaults, PERSISTENT_KEYRING_PREFIX

logger = logging.getLogger(__name__)


def generate_krb5_conf(
    middleware: object,
    directory_service: dict,
    krb_config: dict,
    realms: list
):
    if not realms:
        raise FileShouldNotExist

    krbconf = KRB5Conf()

    appdefaults = {}
    libdefaults = {
        str(KRB_LibDefaults.DEFAULT_CCACHE_NAME): PERSISTENT_KEYRING_PREFIX + '%{uid}',
        str(KRB_LibDefaults.DNS_LOOKUP_REALM): 'true',
        str(KRB_LibDefaults.FORWARDABLE): 'true',
        str(KRB_LibDefaults.DNS_LOOKUP_KDC): 'true',
    }

    default_realm = None
    ds_config = middleware.call_sync('directoryservices.config')
    if not ds_config['enable']:
        raise FileShouldNotExist

    default_realm = ds_config['kerberos_realm']
    kdc_override = kdc_saf_cache_get()

    match directory_service['type']:
        case DSType.AD.value | DSType.IPA.value:
            # It's possible that for some reason the kerberos realm configuration for the
            # AD / IPA domain has been lost. In almost all circumstances this will match the
            # domainname so we can recover from there
            if not default_realm:
                logger.error(
                    '%s: no realm configuration found for domain. Attempting to recover.',
                    ds_config['configuration']['domain']
                )

                # Try looking up again by domain
                default_realm = filter_list(realms, [['realm', '=', ds_config['configuration']['domain']]])
                if not default_realm:
                    # Try to recover by creating a realm stub
                    if not ds_config['configuration']['domain']:
                        # We have an invalid directory services configuration (no domain, no realm)
                        # log an error message and prevent kerberos config generation

                        logger.error("Configuration for domain lacks required options to properly "
                                     "generate a kerberos configuration. Both kerberos realm and domain name "
                                     "are absent")
                        raise FileShouldNotExist

                    realm_id = middleware.call_sync(
                        'datastore.insert', 'directoryservice.kerberosrealm',
                        {'krb_realm': ds_config['configuration']['domain']}
                    )

                    default_realm = middleware.call_sync('kerberos.realm.get_instance', realm_id)['realm']
                else:
                    realm_id = default_realm[0]['id']
                    default_realm = default_realm[0]['realm']

                middleware.call_sync(
                    'datastore.update', 'directoryservices',
                    ds_config['id'], {'kerberos_realm': realm_id}
                )
        case _:
            # LDAP does not require special handling
            pass

    if default_realm:
        for realm in realms:
            if realm['realm'] != default_realm:
                continue

            if kdc_override:
                realm['kdc'] = [kdc_override]

            elif not realm['kdc']:
                # Use DNS / socket APIs to find some connectable KDCs. We only do this if the user hasn't hardcoded
                # any of them.
                realm['kdc'] = middleware.call_sync('directoryservices.connection.dns_lookup_kdcs')

            if realm['kdc']:
                # We've hard-coded some KDCs in the configuration and so we don't want to have krb5 try
                # to look them up.
                libdefaults.update({
                    str(KRB_LibDefaults.DNS_LOOKUP_KDC): 'false',
                })

    krbconf.add_realms(realms)

    if directory_service['type'] in (DSType.IPA.value, DSType.AD.value):
        libdefaults.update({
            str(KRB_LibDefaults.RDNS): 'false',
            str(KRB_LibDefaults.DNS_CANONICALIZE_HOSTNAME): 'false',
        })

    if default_realm:
        libdefaults[str(KRB_LibDefaults.DEFAULT_REALM)] = default_realm

    krbconf.add_libdefaults(libdefaults, krb_config['libdefaults_aux'])
    krbconf.add_appdefaults(appdefaults, krb_config['appdefaults_aux'])

    return krbconf.generate()


def render(service, middleware, render_ctx):

    return generate_krb5_conf(
        middleware,
        render_ctx['directoryservices.status'],
        render_ctx['kerberos.config'],
        render_ctx['kerberos.realm.query']
    )
