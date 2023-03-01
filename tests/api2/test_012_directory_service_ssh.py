#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
from pytest_dependency import depends
from functions import SSH_TEST
from auto_config import hostname, ip

from assets.REST.directory_services import active_directory, ldap, override_nameservers
from middlewared.test.integration.utils import call

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)

try:
    from config import (
        LDAPBASEDN,
        LDAPBINDDN,
        LDAPBINDPASSWORD,
        LDAPHOSTNAME,
        LDAPUSER,
        LDAPPASSWORD
    )
except ImportError:
    Reason = 'LDAP* variable are not setup in config.py'
    pytestmark = pytest.mark.skipif(True, reason=Reason)


@pytest.fixture(scope="function")
def do_ad_connection(request):
    with override_nameservers(ADNameServer):
        with active_directory(
            AD_DOMAIN,
            ADUSERNAME,
            ADPASSWORD,
            netbiosname=hostname,
        ) as ad:
            yield (request, ad)


@pytest.fixture(scope="function")
def do_ldap_connection(request):
    with ldap(LDAPBASEDN, LDAPBINDDN, LDAPBINDPASSWORD, LDAPHOSTNAME,
         has_samba_schema=True) as ldap_conn:
        yield (request, ldap_conn)


def test_08_test_ssh_ad(do_ad_connection, request):
    depends(request, ["ssh_password"], scope="session")
    userobj = call('user.get_user_obj', {'username': f'{ADUSERNAME}@{AD_DOMAIN}'})
    groupobj = call('group.get_group_obj', {'gid': userobj['pw_gid']})
    call('ssh.update', {"password_login_groups": [groupobj['gr_name']]})
    cmd = 'ls -la'
    results = SSH_TEST(cmd, f'{ADUSERNAME}@{AD_DOMAIN}', ADPASSWORD, ip)
    assert results['result'] is True, results['output']


def test_09_test_ssh_ldap(do_ldap_connection, request):
    depends(request, ["ssh_password"], scope="session")
    userobj = call('user.get_user_obj', {'username': LDAPUSER})
    groupobj = call('group.get_group_obj', {'gid': userobj['pw_gid']})
    call('ssh.update', {"password_login_groups": [groupobj['gr_name']]})
    cmd = 'ls -la'
    results = SSH_TEST(cmd, LDAPUSER, LDAPPASSWORD, ip)
    assert results['result'] is True, results['output']
