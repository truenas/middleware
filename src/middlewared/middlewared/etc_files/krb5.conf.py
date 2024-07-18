import logging

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils import filter_list
from middlewared.utils.directoryservices.constants import DSType
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
    krbconf.add_realms(realms)

    appdefaults = {}
    libdefaults = {
        str(KRB_LibDefaults.DEFAULT_CCACHE_NAME): PERSISTENT_KEYRING_PREFIX + '%{uid}',
        str(KRB_LibDefaults.DNS_LOOKUP_REALM): 'true',
        str(KRB_LibDefaults.FORWARDABLE): 'true',
        str(KRB_LibDefaults.DNS_LOOKUP_KDC): 'true',
    }

    default_realm = None

    match directory_service['type']:
        case DSType.AD.value:
            ds_config = middleware.call_sync('activedirectory.config')
            default_realm = filter_list(realms, [['id', '=', ds_config['kerberos_realm']]])
            if not default_realm:
                logger.error(
                    '%s: no realm configuration found for active directory domain',
                    ds_config['domainname']
                )

                # Try looking up again by domainname
                default_realm = filter_list(realms, [['realm', '=', ds_config['domainname']]])
                if not default_realm:

                    # Try to recover by creating a realm stub
                    realm_id = middleware.call_sync(
                        'datastore.insert', 'directoryservice.kerberosrealm',
                        {'krb_realm': ds_config['domainname']}
                    )

                    default_realm = middleware.call_sync('kerberos.realm.get_instance', realm_id)['realm']
                else:
                    realm_id = default_realm[0]['id']
                    default_realm = default_realm[0]['realm']

                # set the kerberos realm in AD form to correct value
                middleware.call_sync(
                    'datastore.update', 'directoryservice.activedirectory',
                    ds_config['id'], {'ad_kerberos_realm': realm_id}
                )
            else:
                default_realm = default_realm[0]['realm']
        case DSType.IPA.value:
            try:
                default_realm = middleware.call_sync('ldap.ipa_config')['realm']
            except Exception:
                # This can potenitally happen if we're simultaneously disabling IPA service
                # while generating the krb5.conf file
                default_realm = None

            # This matches defaults from ipa-client-install
            libdefaults.update({
                str(KRB_LibDefaults.RDNS): 'false',
                str(KRB_LibDefaults.DNS_CANONICALIZE_HOSTNAME): 'false',
            })
        case DSType.LDAP.value:
            ds_config = middleware.call_sync('ldap.config')
            if ds_config['kerberos_realm']:
                default_realm = filter_list(realms, [['id', '=', ds_config['kerberos_realm']]])
                if default_realm:
                    default_realm = default_realm[0]['realm']
        case _:
            pass

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
