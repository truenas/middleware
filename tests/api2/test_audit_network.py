from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls


def test_network_globalconfig_audit():
    '''
    Test the auditing of network global configuration changes
    '''
    initial_network_config = call('network.configuration.config')
    try:
        # UPDATE
        temp_hostname = '-'.join([initial_network_config['hostname'], 'temporary'])
        payload = {
            'hostname': temp_hostname
        }
        with expect_audit_method_calls([{
            'method': 'network.configuration.update',
            'params': [payload],
            'description': 'Update network global configuration',
        }]):
            call('network.configuration.update', payload)
    finally:
        # Restore initial state
        restore_payload = {
            'hostname': initial_network_config['hostname'],
        }
        call('network.configuration.update', restore_payload)
