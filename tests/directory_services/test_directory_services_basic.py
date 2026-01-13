import pytest
from functions import SSH_TEST

from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls
from middlewared.service_exception import ValidationErrors

from middlewared.utils.network import DEFAULT_NETWORK_DOMAIN


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


@pytest.mark.parametrize('service_type', ['ACTIVEDIRECTORY', 'IPA', 'LDAP'])
def test_directory_services_network_domain(service_type):
    """
    While configured for directory services, confirm:
        if not LDAP
            1) Reported network domain matches the actual joined domain
            2) Cannot change the network domain
        else
            3) Network domain can be modified

        After leaving domain, confirm:
            1) Network reported domain returns to (if LDAP, remains)  default (local)
            2) Network domain can be modified.
    """

    ds_config = call('directoryservices.config')
    print(f"\nMCG DEBUG: ds_config=\n{ds_config}")

    with directoryservice(service_type) as ds_config:
        # ds_config = call('directoryservices.config')
        if service_type != 'LDAP':
            net_config = call('network.configuration.config')
            assert net_config['domain'] == ds_config['configuration']['domain']

            with pytest.raises(ValidationErrors, match="cannot change this parameter"):
                call('network.configuration.update', {'domain': 'block.me'})
        else:
            call('network.configuration.update', {'domain': 'accept.me'})

    # Test after leaving directory services
    net_config = call('network.configuration.config')
    assert net_config['configuration']['domain'] == DEFAULT_NETWORK_DOMAIN

    try:
        call('network.configuration.update', {'domain': 'accept.me'})
    finally:
        # Restore default
        call('network.configuration.update', {'domain': DEFAULT_NETWORK_DOMAIN})
