import pytest

from truenas_api_client import ValidationErrors
from middlewared.service_exception import ValidationErrors as exception_validation_error
from middlewared.test.integration.assets.nfs import nfs_share
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, ssh, mock

SMB_SHARE_NAME = 'test_share'


@pytest.fixture(scope='module')
def test_pool():
    with another_pool() as test_pool:
        yield test_pool


def test_kubernetes_pool_of_smb_share_validation_error(test_pool):
    with smb_share(f'/mnt/{test_pool["name"]}', SMB_SHARE_NAME):
        with pytest.raises(ValidationErrors) as ve:
            call('kubernetes.update', {'pool': test_pool['name']}, job=True)
        assert ve.value.errors[0].errmsg == (
            f'The root dataset of pool `{test_pool["name"]}` is used by `SMB` services. '
            'Shares should be configured so that they export data contained in child datasets such as '
            f'`{test_pool["name"]}/SHARE`.'
        )
        assert ve.value.errors[0].attribute == 'kubernetes_update.pool'


def test_kubernetes_pool_of_nfs_share_validation_error(test_pool):
    with nfs_share(test_pool['name']):
        with pytest.raises(ValidationErrors) as ve:
            call('kubernetes.update', {'pool': test_pool['name']}, job=True)
        assert ve.value.errors[0].errmsg == (
            f'The root dataset of pool `{test_pool["name"]}` is used by `NFS` services. '
            'Shares should be configured so that they export data contained in child datasets such as '
            f'`{test_pool["name"]}/SHARE`.'
        )
        assert ve.value.errors[0].attribute == 'kubernetes_update.pool'


def test_kubernetes_pool_of_nfs_and_smb_share_validation_error(test_pool):
    with smb_share(f'/mnt/{test_pool["name"]}', SMB_SHARE_NAME):
        with nfs_share(test_pool['name']):
            with pytest.raises(ValidationErrors) as ve:
                call('kubernetes.update', {'pool': test_pool['name']}, job=True)

            assert 'NFS' in ve.value.errors[0].errmsg
            assert 'SMB' in ve.value.errors[0].errmsg
            assert ve.value.errors[0].attribute == 'kubernetes_update.pool'


def test_smb_validation_error_on_app_pool(test_pool):
    with mock('kubernetes.config', return_value={'dataset': f'{test_pool["name"]}/ix-applications'}):
        with pytest.raises(exception_validation_error) as ve:
            with smb_share(f'/mnt/{test_pool["name"]}', SMB_SHARE_NAME):
                pass

    assert ve.value.errors[0].errmsg == 'SMB shares containing the apps dataset are not permitted'
    assert ve.value.errors[0].attribute == 'sharingsmb_create.path_local'


def test_nfs_validation_error_on_app_pool(test_pool):
    with mock('kubernetes.config', return_value={'dataset': f'{test_pool["name"]}/ix-applications'}):
        with pytest.raises(exception_validation_error) as ve:
            with nfs_share(test_pool['name']):
                pass

        assert ve.value.errors[0].errmsg == 'NFS shares containing the apps dataset are not permitted'
        assert ve.value.errors[0].attribute == 'sharingnfs_create.path'
