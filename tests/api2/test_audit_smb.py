import os
import sys

import pytest
from middlewared.service_exception import CallError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls

sys.path.append(os.getcwd())

REDACTED_SECRET = '********'


@pytest.fixture(scope='module')
def smb_audit_dataset(request):
    with dataset('audit-test-smb') as ds:
        try:
            yield ds
        finally:
            pass


def test_smb_update_audit():
    '''
    Test the auditing of SMB configuration changes
    '''
    initial_smb_config = call('smb.config')
    payload = {'enable_smb1': True}
    try:
        with expect_audit_method_calls([{
            'method': 'smb.update',
            'params': [payload],
            'description': 'Update SMB configuration',
        }]):
            call('smb.update', payload)
    finally:
        call('smb.update', {'enable_smb1': False})


def test_smb_share_audit(smb_audit_dataset):
    '''
    Test the auditing of SMB share operations
    '''
    smb_share_path = os.path.join('/mnt', smb_audit_dataset)
    try:
        # CREATE
        payload = {
            "comment": "My Test Share",
            "path": smb_share_path,
            "options": {},
            "purpose": "DEFAULT_SHARE",
            "name": "audit_share"
        }
        with expect_audit_method_calls([{
            'method': 'sharing.smb.create',
            'params': [payload],
            'description': f'SMB share create audit_share',
        }]):
            share_config = call('sharing.smb.create', payload)

        # UPDATE
        payload = {
            "purpose": "DEFAULT_SHARE",
            "options": {"aapl_name_mangling": True}
        }
        with expect_audit_method_calls([{
            'method': 'sharing.smb.update',
            'params': [
                share_config['id'],
                payload,
            ],
            'description': f'SMB share update audit_share',
        }]):
            share_config = call('sharing.smb.update', share_config['id'], payload)

    finally:
        if share_config is not None:
            # DELETE
            share_id = share_config['id']
            with expect_audit_method_calls([{
                'method': 'sharing.smb.delete',
                'params': [share_id],
                'description': f'SMB share delete audit_share',
            }]):
                call('sharing.smb.delete', share_id)
