# -*- coding=utf-8 -*-
import contextlib
import logging
import os
import secrets
import string
import sys

from dataclasses import dataclass
from middlewared.test.integration.utils import call, fail

__all__ = [
    'directoryservice', 'override_nameservers', 'get_nameservers', 'get_directory_services_account',
]


try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import ha, hostname
except ImportError:
    ha = False
    hostname = None

try:
    from config import (
        AD_DOM2_DOMAIN, AD_DOM2_WORKGROUP, AD_DOM2_DC1, AD_DOM2_DC2,
        AD_DOM2_USERNAME, AD_DOM2_PASSWORD, AD_DOM2_COMPUTER_OU,
        AD_DOM2_LIMITED_USER, AD_DOM2_LIMITED_USER_PASSWORD
    )
except ImportError:
    AD_DOM2_DOMAIN = None
    AD_DOM2_WORKGROUP = None
    AD_DOM2_DC1 = None
    AD_DOM2_DC2 = None
    AD_DOM2_USERNAME = None
    AD_DOM2_PASSWORD = None
    AD_DOM2_LIMITED_USER = None
    AD_DOM2_LIMITED_USER_PASSWORD = None
    AD_DOM2_COMPUTER_OU = None

try:
    from config import (
        LDAPBASEDN,
        LDAPBINDDN,
        LDAPBINDPASSWORD,
        LDAPHOSTNAME,
        LDAPUSER,
        LDAPADMIN,
        LDAPPASSWORD
    )
except ImportError:
    LDAPBASEDN = None
    LDAPBINDDN = None
    LDAPBINDPASSWORD = None
    LDAPHOSTNAME = None
    LDAPADMIN = None
    LDAPUSER = None
    LDAPPASSWORD = None

try:
    from config import (
        FREEIPA_IP,
        FREEIPA_BASEDN,
        FREEIPA_USERNAME,
        FREEIPA_BINDDN,
        FREEIPA_BINDPW,
        FREEIPA_REALM,
        FREEIPA_ADMIN_USERNAME,
        FREEIPA_ADMIN_BINDDN,
        FREEIPA_ADMIN_BINDPW,
        FREEIPA_HOSTNAME,
    )
except ImportError:
    FREEIPA_IP = None
    FREEIPA_BASEDN = None
    FREEIPA_USERNAME = None
    FREEIPA_BINDDN = None
    FREEIPA_BINDPW = None
    FREEIPA_REALM = None
    FREEIPA_ADMIN_USERNAME = None
    FREEIPA_ADMIN_BINDDN = None
    FREEIPA_ADMIN_BINDPW = None
    FREEIPA_HOSTNAME = None


logger = logging.getLogger(__name__)

if ha and "hostname_virtual" in os.environ:
    hostname = os.environ["hostname_virtual"]


@dataclass(slots=True)
class directoryservices_user:
    username: str
    password: str
    user_obj: dict


@contextlib.contextmanager
def override_nameservers(_nameserver1='', _nameserver2='', _nameserver3=''):
    nameservers_changed = False
    net_config = call('network.configuration.config')
    nameserver1 = net_config['nameserver1']
    nameserver2 = net_config['nameserver2']
    nameserver3 = net_config['nameserver3']

    try:
        if not any([_nameserver1, _nameserver2, _nameserver3]):
            yield
        else:
            nameservers_changed = True
            yield call('network.configuration.update', {
                'nameserver1': _nameserver1,
                'nameserver2': _nameserver2,
                'nameserver3': _nameserver3
            })
    finally:
        if nameservers_changed:
            call('network.configuration.update', {
                'nameserver1': nameserver1,
                'nameserver2': nameserver2,
                'nameserver3': nameserver3,
            })


@contextlib.contextmanager
def override_netbiosname(new_name):
    old_name = call('smb.config')['netbiosname']
    try:
        call('datastore.update', 'services.cifs', 1, {'cifs_srv_netbiosname': new_name or old_name})
        yield
    finally:
        call('datastore.update', 'services.cifs', 1, {'cifs_srv_netbiosname': old_name})


def get_nameservers(service_type: str) -> tuple:
    match service_type:
        case 'ACTIVEDIRECTORY':
            return (AD_DOM2_DC1, AD_DOM2_DC2, '')
        case 'IPA':
            return (FREEIPA_IP, '', '')
        case 'LDAP':
            return ('', '', '')
        case _:
            raise ValueError(f'{service_type}: unexpected service type')


def get_default_credential(service_type: str) -> dict:
    match service_type:
        case 'ACTIVEDIRECTORY':
            return {
                'credential_type': 'KERBEROS_USER',
                'username': AD_DOM2_USERNAME,
                'password': AD_DOM2_PASSWORD,
            }
        case 'IPA':
            return {
                'credential_type': 'KERBEROS_USER',
                'username': FREEIPA_ADMIN_USERNAME,
                'password': FREEIPA_ADMIN_BINDPW,
            }
        case 'LDAP':
            return {
                'credential_type': 'LDAP_PLAIN',
                'binddn': LDAPBINDDN,
                'bindpw': LDAPBINDPASSWORD
            }
        case _:
            raise ValueError(f'{service_type}: unexpected service type')


def get_directory_services_account(service_type: str) -> directoryservices_user:
    match service_type:
        case 'ACTIVEDIRECTORY':
            username = AD_DOM2_USERNAME
            password = AD_DOM2_PASSWORD
            sid_info = True
            get_user = f'{AD_DOM2_WORKGROUP}\\{username}'
        case 'LDAP':
            username = LDAPUSER
            password = LDAPPASSWORD
            sid_info = False
            get_user = username
        case 'IPA':
            username = FREEIPA_ADMIN_USERNAME
            password = FREEIPA_ADMIN_BINDPW
            sid_info = True
            get_user = username
        case _:
            fail(f'{service_type}: unexpected service type')

    user_obj = call('user.get_user_obj', {'username': get_user, 'sid_info': sid_info})
    return directoryservices_user(username, password, user_obj)


def get_random_name():
    # netbios compatible name
    return 'TN' + ''.join(secrets.choice((string.ascii_uppercase + string.digits)) for i in range(10))


def get_default_configuration(service_type: str) -> dict:
    match service_type:
        case 'ACTIVEDIRECTORY':
            return {
                'hostname': get_random_name(),
                'domain': AD_DOM2_DOMAIN,
                'computer_account_ou': AD_DOM2_COMPUTER_OU,
            }
        case 'IPA':
            return {
                'hostname': get_random_name(),
                'target_server': FREEIPA_HOSTNAME,
                'domain': FREEIPA_REALM,
                'basedn': FREEIPA_BASEDN,
                'validate_certificates': False,
            }
        case 'LDAP':
            return {
                'server_urls': [f'ldaps://{LDAPHOSTNAME}'],
                'basedn': LDAPBASEDN,
                'validate_certificates': False,
            }
        case _:
            raise ValueError(f'{service_type}: unexpected service type')


@contextlib.contextmanager
def directoryservice(
    service_type: str, *,
    credential: dict | None = None,
    account_cache: bool = True,
    dns_updates: bool = True,
    timeout: int = 10,
    kerberos_realm: str | None = None,
    configuration=None,
    reset_config=True,
    retrieve_user=True,
):
    nameservers = get_nameservers(service_type)
    if reset_config:
        # Make sure we don't have any stale configuration from previous
        # tests
        call('directoryservices.reset')

    if not credential:
        credential = get_default_credential(service_type)

    defaults = get_default_configuration(service_type)
    if configuration:
        defaults.update(configuration)

    with override_nameservers(*nameservers):
        with override_netbiosname(defaults.get('hostname')):
            try:
                config = call('directoryservices.update', {
                    'service_type': service_type,
                    'enable': True,
                    'credential': credential,
                    'enable_account_cache': account_cache,
                    'enable_dns_updates': dns_updates,
                    'timeout': timeout,
                    'kerberos_realm': kerberos_realm,
                    'configuration': defaults
                }, job=True)
            except Exception:
                call('directoryservices.reset')
                # This may be a test of validation errors
                raise

            try:
                call('directoryservices.health.check')
                if retrieve_user:
                    ds_acct = get_directory_services_account(service_type)
                else:
                    ds_acct = None
                domain_info = call('directoryservices.domain_info')
                yield {'config': config, 'account': ds_acct, 'domain_info': domain_info}
            finally:
                if service_type in ('ACTIVEDIRECTORY', 'IPA'):
                    call('directoryservices.leave', {'credential': credential}, job=True)
                else:
                    call('directoryservices.reset')
