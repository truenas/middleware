import logging

from middlewared.utils import filter_list
from middlewared.utils.directoryservices.krb5_conf import KRB5Conf
from middlewared.utils.directoryservices.krb5_constants import (
    KRB_LibDefaults, krb5ccache
)

logger = logging.getLogger(__name__)


def generate_krb5_conf(
    middleware: object,
    directory_service: str,
    ds_config: dict,
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
    }

    default_realm = None

    match directory_service:
        case 'ACTIVEDIRECTORY':
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

                    default_realm = middleware.call_sync('kerberos.realm.get_instance', realm_id)
                else:
                    default_realm = default_realm[0]
                    realm_id = default_realm['id']

                # set the kerberos realm in AD form to correct value
                middleware.call_sync(
                    'datastore.update', 'directoryservice.activedirectory',
                    ds_config['id'], {'ad_kerberos_realm': realm_id}
                )
            else:
                default_realm = default_realm[0]

        case 'LDAP':
            if ds_config['kerberos_realm']:
                default_realm = filter_list(realms, [['id', '=', ds_config['kerberos_realm']]])
                if default_realm:
                    default_realm = default_realm[0]

        case _:
            pass

    if default_realm:
        libdefaults[str(KRB_LibDefaults.DEFAULT_REALM)] = default_realm['realm']

    krbconf.add_libdefaults(libdefaults, krb_config['libdefaults_aux'])
    krbconf.add_appdefaults(appdefaults, krb_config['appdefaults_aux'])

    return krbconf.generate()


def render(service, middleware, render_ctx):
    if render_ctx['activedirectory.config']['enable']:
        return generate_krb5_conf(
            middleware, 'ACTIVEDIRECTORY',
            render_ctx['activedirectory.config'],
            render_ctx['kerberos.config'],
            render_ctx['kerberos.realm.query']
        )

    elif render_ctx['ldap.config']['enable']:
        return generate_krb5_conf(
            middleware, 'LDAP',
            render_ctx['ldap.config'],
            render_ctx['kerberos.config'],
            render_ctx['kerberos.realm.query']
        )

    return generate_krb5_conf(
        middleware, None, None,
        render_ctx['kerberos.config'],
        render_ctx['kerberos.realm.query']
    )
