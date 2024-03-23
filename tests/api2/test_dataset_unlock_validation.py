import os
import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
from middlewared.client.client import ValidationErrors


PASSPHRASE = '12345678'
pytestmark = pytest.mark.zfs


def encryption_props():
    return {
        'encryption_options': {'generate_key': False, 'passphrase': PASSPHRASE},
        'encryption': True,
        'inherit_encryption': False
    }


@pytest.mark.parametrize(
    'nested_dir,lock_dataset', [('test_dir', True), ('parent/child', True), ('test_dir', False)]
)
def test_encrypted_dataset_unlock_mount_validation(nested_dir, lock_dataset):
    with dataset('test_dataset', encryption_props()) as encrypted_ds:
        mount_point = os.path.join('/mnt', encrypted_ds)

        if lock_dataset:
            call('pool.dataset.lock', encrypted_ds, job=True)
            call('filesystem.set_immutable', False, mount_point)

        ssh(f'mkdir -p {os.path.join(mount_point, nested_dir)}')

        if lock_dataset:
            with pytest.raises(ValidationErrors) as ve:
                call(
                    'pool.dataset.unlock', encrypted_ds.split('/')[0],
                    {'datasets': [{'passphrase': PASSPHRASE, 'name': encrypted_ds}], 'recursive': True}, job=True
                )

            assert ve.value.errors[0].attribute == 'unlock_options.datasets.0.force'
            assert ve.value.errors[0].errmsg == f'\'{mount_point}\' directory is not empty (please provide' \
                                                ' "force" flag to override this error and file/directory will be' \
                                                ' renamed once the dataset is unlocked)'
        else:
            call(
                'pool.dataset.unlock', encrypted_ds.split('/')[0],
                {'datasets': [{'passphrase': PASSPHRASE, 'name': encrypted_ds}], 'recursive': True}, job=True
            )

    ssh(f'rm -rf {mount_point}')
