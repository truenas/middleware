# -*- coding=utf-8 -*-
import contextlib
import logging
import os
import sys

from middlewared.test.integration.utils import call, fail

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import ha, hostname
except ImportError:
    ha = False
    hostname = None

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer, AD_COMPUTER_OU
except ImportError:
    AD_DOMAIN = None
    ADPASSWORD = None
    ADUSERNAME = None
    ADNameServer = None
    AD_COMPUTER_OU = None

try:
    from config import (
        LDAPBASEDN,
        LDAPBINDDN,
        LDAPBINDPASSWORD,
        LDAPHOSTNAME,
    )
except ImportError:
    LDAPBASEDN = None
    LDAPBINDDN = None
    LDAPBINDPASSWORD = None
    LDAPHOSTNAME = None

try:
    from config import (
        FREEIPA_IP,
        FREEIPA_BASEDN,
        FREEIPA_BINDDN,
        FREEIPA_BINDPW,
        FREEIPA_ADMIN_BINDDN,
        FREEIPA_ADMIN_BINDPW,
        FREEIPA_HOSTNAME,
    )
except ImportError:
    FREEIPA_IP = None
    FREEIPA_BASEDN = None
    FREEIPA_BINDDN = None
    FREEIPA_BINDPW = None
    FREEIPA_ADMIN_BINDDN = None
    FREEIPA_ADMIN_BINDPW = None
    FREEIPA_HOSTNAME = None


logger = logging.getLogger(__name__)

__all__ = ['active_directory', 'ldap', 'override_nameservers', 'ipa']

if ha and "hostname_virtual" in os.environ:
    hostname = os.environ["hostname_virtual"]


@contextlib.contextmanager
def override_nameservers(_nameserver1=ADNameServer, _nameserver2='', _nameserver3=''):
    net_config = call('network.configuration.config')
    nameserver1 = net_config['nameserver1']
    nameserver2 = net_config['nameserver2']
    nameserver3 = net_config['nameserver3']

    try:
        yield call('network.configuration.update', {
            'nameserver1': _nameserver1,
            'nameserver2': _nameserver2,
            'nameserver3': _nameserver3
        })
    finally:
        call('network.configuration.update', {
            'nameserver1': nameserver1,
            'nameserver2': nameserver2,
            'nameserver3': nameserver3,
        })


def clear_ad_info():
    call('activedirectory.update', {
        "domainname": "",
        "bindname": "",
        "verbose_logging": False,
        "allow_trusted_doms": False,
        "use_default_domain": False,
        "allow_dns_updates": True,
        "disable_freenas_cache": False,
        "restrict_pam": False,
        "site": None,
        "timeout": 60,
        "dns_timeout": 10,
        "nss_info": None,
        "enable": False,
        "kerberos_principal": "",
        "createcomputer": "",
        "kerberos_realm": None,
    }, job=True)


@contextlib.contextmanager
def active_directory(
    domain=AD_DOMAIN,
    username=ADUSERNAME,
    password=ADPASSWORD,
    hostname=hostname,
    nameserver=ADNameServer,
    computerou=AD_COMPUTER_OU,
    **kwargs
):
    payload = {
        'domainname': domain,
        'bindname': username,
        'bindpw': password,
        'netbiosname': hostname,
        'createcomputer': computerou,
        'kerberos_principal': '',
        'use_default_domain': False,
        'enable': True,
        **kwargs
    }

    with override_nameservers(nameserver):
        try:
            config = call('activedirectory.update', payload, job=True)
        except Exception:
            clear_ad_info()
            # we may be testing ValidationErrors
            raise

        try:
            domain_info = call('activedirectory.domain_info')
        except Exception:
            # This is definitely unexpected and not recoverable
            fail('Failed to retrieve domain information')

        dc_info = call('activedirectory.lookup_dc', domain)
        u = f'{dc_info["Pre-Win2k Domain"]}\\{ADUSERNAME.lower()}'

        try:
            user_obj = call('user.get_user_obj', {'username': u, 'sid_info': True})
        except Exception:
            # This is definitely unexpected and not recoverable
            fail(f'{username}: failed to retrieve information about user')

        try:
            yield {
                'config': config,
                'domain_info': domain_info,
                'dc_info': dc_info,
                'user_obj': user_obj,
            }
        finally:
            call('activedirectory.leave', {'username': username, 'password': password}, job=True)

        clear_ad_info()


def clear_ldap_info():
    call('ldap.update', {
        "hostname": [],
        "basedn": "",
        "binddn": "",
        "bindpw": "",
        "ssl": "ON",
        "enable": False,
        "kerberos_principal": "",
        "kerberos_realm": None,
        "anonbind": False,
        "validate_certificates": True,
        "disable_freenas_cache": False,
        "certificate": None,
        "auxiliary_parameters": ""
    }, job=True)


@contextlib.contextmanager
def ldap(
    basedn=LDAPBASEDN,
    binddn=LDAPBINDDN,
    bindpw=LDAPBINDPASSWORD,
    hostname=LDAPHOSTNAME,
    **kwargs
):
    config = call('ldap.update', {
        "basedn": basedn,
        "binddn": binddn,
        "bindpw": bindpw,
        "hostname": [hostname],
        "ssl": "ON",
        "auxiliary_parameters": "",
        "validate_certificates": True,
        "enable": True,
        **kwargs
    }, job=True)

    try:
        config['bindpw'] = None
        yield {
            'config': config,
        }
    finally:
        clear_ldap_info()


def clear_ipa_info():
    clear_ldap_info()
    keytabs = call('kerberos.keytab.query')
    for kt in keytabs:
        call('kerberos.keytab.delete', kt['id'])


@contextlib.contextmanager
def ipa(
    basedn=FREEIPA_BASEDN,
    binddn=FREEIPA_ADMINDN,
    bindpw=FREEIPA_ADMINPW,
    hostname=FREEIPA_HOSTNAME,
    nameserver=FREEIPA_IP,
    **kwargs
):
    with override_nameservers(nameserver):
        try:
            config = call('ldap.update', {
                "basedn": basedn,
                "binddn": binddn,
                "bindpw": bindpw,
                "hostname": [hostname],
                "ssl": "ON",
                "auxiliary_parameters": "",
                "validate_certificates": False,
                "enable": True,
                **kwargs
            }, job=True)
            config['bindpw'] = None
            yield config
        finally:
            clear_ipa_info()
