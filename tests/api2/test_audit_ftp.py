import os
import sys

import pytest
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls

sys.path.append(os.getcwd())
from functions import PUT


@pytest.fixture(scope='module')
def nfs_audit_dataset(request):
    with dataset('audit-test-nfs') as ds:
        try:
            yield ds
        finally:
            pass


@pytest.mark.parametrize('api', ['ws', 'rest'])
def test_ftp_config_audit(api):
    '''
    Test the auditing of FTP configuration changes
    '''
    initial_ftp_config = call('ftp.config')
    try:
        # UPDATE
        payload = {
            'clients': 1000,
            'rootlogin': True,
            'banner': "Hello, from New York"
        }
        with expect_audit_method_calls([{
            'method': 'ftp.update',
            'params': [payload],
            'description': 'Update FTP configuration',
        }]):
            if api == 'ws':
                call('ftp.update', payload)
            elif api == 'rest':
                result = PUT('/ftp/', payload)
                assert result.status_code == 200, result.text
            else:
                raise ValueError(api)
    finally:
        # Restore initial state
        restore_payload = {
            'clients': initial_ftp_config['clients'],
            'onlyanonymous': initial_ftp_config['onlyanonymous'],
            'banner': initial_ftp_config['banner']
        }
        if api == 'ws':
            call('ftp.update', restore_payload)
        elif api == 'rest':
            result = PUT('/ftp/', restore_payload)
            assert result.status_code == 200, result.text
        else:
            raise ValueError(api)
