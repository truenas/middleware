import pytest
from functions import SSH_TEST

from middlewared.test.integration.assets.directory_service import active_directory, ldap
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)

try:
    from config import (
        LDAPUSER,
        LDAPPASSWORD
    )
except ImportError:
    Reason = 'LDAP* variable are not setup in config.py'
    pytestmark = pytest.mark.skipif(True, reason=Reason)


@pytest.fixture(scope="function")
def do_ad_connection(request):
    with active_directory() as ad:
        yield ad


@pytest.fixture(scope="function")
def do_ldap_connection(request):
    with ldap() as ldap_conn:
        yield ldap_conn


def test_08_test_ssh_ad(do_ad_connection):
    userobj = do_ad_connection['user_obj']
    groupobj = call('group.get_group_obj', {'gid': userobj['pw_gid']})

    payload = {"password_login_groups": [groupobj['gr_name']]}

    try:
        with expect_audit_method_calls([{
            'method': 'ssh.update',
            'params': [payload],
            'description': 'Update SSH configuration'
        }]):
            call('ssh.update', payload)

        results = SSH_TEST('ls -la', f'{ADUSERNAME}@{AD_DOMAIN}', ADPASSWORD)
    finally:
        call('ssh.update', {"password_login_groups": []})

    assert results['result'] is True, results


def test_09_test_ssh_ldap(do_ldap_connection):
    userobj = call('user.get_user_obj', {'username': LDAPUSER})
    groupobj = call('group.get_group_obj', {'gid': userobj['pw_gid']})
    call('ssh.update', {"password_login_groups": [groupobj['gr_name']]})
    cmd = 'ls -la'
    results = SSH_TEST(cmd, LDAPUSER, LDAPPASSWORD)
    call('ssh.update', {"password_login_groups": []})
    assert results['result'] is True, results
