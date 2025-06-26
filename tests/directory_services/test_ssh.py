import pytest
from functions import SSH_TEST

from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls


@pytest.mark.parametrize('service_type', ['ACTIVEDIRECTORY', 'IPA', 'LDAP'])
def test_directory_services_ssh(service_type):
    with directoryservice(service_type) as ds:
        userobj = ds['account'].user_obj
        groupobj = call('group.get_group_obj', {'gid': userobj['pw_gid']})
        payload = {"password_login_groups": [groupobj['gr_name']]}
        try:
            with expect_audit_method_calls([{
                'method': 'ssh.update',
                'params': [payload],
                'description': 'Update SSH configuration'
            }]):
                call('ssh.update', payload)

            results = SSH_TEST('ls -la', userobj['pw_name'], ds['account'].password)
        finally:
            call('ssh.update', {"password_login_groups": []})

        assert results['result'] is True, f'{userobj}: SSH test failed: {results}'
