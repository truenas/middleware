from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls


def test_ftp_config_audit():
    '''
    Test the auditing of FTP configuration changes
    '''
    initial_ftp_config = call('ftp.config')
    try:
        # UPDATE
        payload = {
            'clients': 1000,
            'banner': "Hello, from New York"
        }
        with expect_audit_method_calls([{
            'method': 'ftp.update',
            'params': [payload],
            'description': 'Update FTP configuration',
        }]):
            call('ftp.update', payload)
    finally:
        # Restore initial state
        restore_payload = {
            'clients': initial_ftp_config['clients'],
            'banner': initial_ftp_config['banner']
        }
        call('ftp.update', restore_payload)
