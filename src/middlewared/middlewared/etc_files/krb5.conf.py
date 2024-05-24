import logging

from middlewared.plugins.directoryservices_.all import get_enabled_ds
from middlewared.utils import filter_list
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.krb5_conf import KRB5Conf
from middlewared.utils.directoryservices.krb5_constants import (
    KRB_LibDefaults, krb5ccache
)

logger = logging.getLogger(__name__)


def add_directory_service(
    middleware: object,
    libdefaults: dict,
    ds_obj: object,
    realms: list
):
    """ Add directory service related kerberos configuration """
    default_realm_name = None
    ds_config = ds_obj.config

    match ds_obj.ds_type:
        case DSType.AD:
            if ds_config['kerberos_realm'] is None:
                # User somehow managed to sneak behind our normal
                # validation and remove the kerberos realm
                logger.error(
                    '%s: no realm configuration found for active directory domain ',
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

                    default_realm = middleware.call_sync('kerberos.realm.get_instance', realm_id)
                else:
                    realm_id = default_realm['id']

                # set the kerberos realm in AD form to correct value
                middleware.call_sync(
                    'datastore.update', 'directoryservice.activedirectory',
                    ds_config['id'], {'ad_kerberos_realm': realm_id}
                )
                logger.debug('Fixed activedirectory configuration')
                ds_obj.update_config()
                ds_config = ds_obj.config

            default_realm_name = ds_config['kerberos_realm']['krb_realm']

        case DSType.LDAP:
            if ds_config['kerberos_realm']:
                default_realm_name = ds_config['kerberos_realm']['krb_realm']

        case DSType.IPA:
            ipa_conf = ds_obj.setup_legacy()
            default_realm_name = ipa_conf['realm']

            # this matches defaults from ipa-client-install
            libdefaults.update({
                str(KRB_LibDefaults.RDNS): 'false',
                str(KRB_LibDefaults.DNS_CANONICALIZE_HOSTNAME): 'false',
            })

    if default_realm_name:
        libdefaults[str(KRB_LibDefaults.DEFAULT_REALM)] = default_realm_name


def generate_krb5_conf(
    middleware: object,
    ds_obj: object,
    krb_config: dict,
    realms: list
):
    krbconf = KRB5Conf()
    krbconf.add_realms(realms)

    appdefaults = {}
    libdefaults = {
        str(KRB_LibDefaults.DEFAULT_CCACHE_NAME): 'FILE:' + krb5ccache.SYSTEM.value,
        str(KRB_LibDefaults.DNS_LOOKUP_REALM): 'true',
        str(KRB_LibDefaults.DNS_LOOKUP_KDC): 'true',
        str(KRB_LibDefaults.FORWARDABLE): 'true',
    }

    default_realm = None

    if ds_obj is not None:
        add_directory_service(middleware, libdefaults, ds_obj, realms)

    krbconf.add_libdefaults(libdefaults, krb_config['libdefaults_aux'])
    krbconf.add_appdefaults(appdefaults, krb_config['appdefaults_aux'])

    return krbconf.generate()


def render(service, middleware, render_ctx):
    ds_obj = get_enabled_ds()
    return generate_krb5_conf(
        middleware, ds_obj,
        render_ctx['kerberos.config'],
        render_ctx['kerberos.realm.query']
    )
