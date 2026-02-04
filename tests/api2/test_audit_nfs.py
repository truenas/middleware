import pytest
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls

@pytest.fixture(scope='module')
def nfs_audit_dataset(request):
    with dataset('audit-test-nfs') as ds:
        try:
            yield ds
        finally:
            pass


def test_nfs_config_audit():
    '''
    Test the auditing of NFS configuration changes
    '''
    bogus_user = 'bogus_user'
    bogus_password = 'boguspassword123'
    initial_nfs_config = call('nfs.config')
    try:
        # UPDATE
        payload = {
            'mountd_log': not initial_nfs_config['mountd_log'],
            'mountd_port': 618,
            'protocols': ["NFSV4"]
        }
        with expect_audit_method_calls([{
            'method': 'nfs.update',
            'params': [payload],
            'description': 'Update NFS configuration',
        }]):
            call('nfs.update', payload)
    finally:
        # Restore initial state
        restore_payload = {
            'mountd_log': initial_nfs_config['mountd_log'],
            'mountd_port': initial_nfs_config['mountd_port'],
            'protocols': initial_nfs_config['protocols']
        }
        call('nfs.update', restore_payload)


def test_nfs_share_audit(nfs_audit_dataset):
    '''
    Test the auditing of NFS share operations
    '''
    nfs_export_path = f"/mnt/{nfs_audit_dataset}"
    try:
        # CREATE
        payload = {
            "comment": "My Test Share",
            "path": nfs_export_path,
            "security": ["SYS"]
        }
        with expect_audit_method_calls([{
            'method': 'sharing.nfs.create',
            'params': [payload],
            'description': f'NFS share create {nfs_export_path}',
        }]):
            share_config = call('sharing.nfs.create', payload)

        # Verify dataset and relative_path resolution
        assert share_config['dataset'] == nfs_audit_dataset
        assert share_config['relative_path'] == ''

        # UPDATE
        payload = {
            "security": []
        }
        with expect_audit_method_calls([{
            'method': 'sharing.nfs.update',
            'params': [
                share_config['id'],
                payload,
            ],
            'description': f'NFS share update {nfs_export_path}',
        }]):
            share_config = call('sharing.nfs.update', share_config['id'], payload)
    finally:
        if share_config is not None:
            # DELETE
            id_ = share_config['id']
            with expect_audit_method_calls([{
                'method': 'sharing.nfs.delete',
                'params': [id_],
                'description': f'NFS share delete {nfs_export_path}',
            }]):
                call('sharing.nfs.delete', id_)
