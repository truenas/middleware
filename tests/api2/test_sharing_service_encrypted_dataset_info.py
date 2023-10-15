import contextlib
import pytest

from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.pool import dataset


PASSPHRASE = 'testing123'
ENCRYPTION_PARAMETERS = {
    'encryption': True,
    'encryption_options': {
        'algorithm': 'AES-256-GCM',
        'pbkdf2iters': 350000,
        'passphrase': PASSPHRASE,
    },
    'inherit_encryption': False,
}


@contextlib.contextmanager
def lock_dataset(dataset_name):
    try:
        yield call('pool.dataset.lock', dataset_name, {'force_umount': True}, job=True)
    finally:
        call(
            'pool.dataset.unlock', dataset_name, {
                'datasets': [{'passphrase': PASSPHRASE, 'name': dataset_name}]
            },
            job=True,
        )


@pytest.mark.parametrize('namespace,dataset_creation_params,share_create_params,path_field', [
    ('sharing.smb', {}, {'name': 'test_smb_share'}, 'path'),
    ('sharing.nfs', {}, {},  'path'),
    ('iscsi.extent', {'type': 'VOLUME', 'volsize': 268451840, 'volblocksize': '16K'}, {'name': 'test-extend'}, 'disk'),
])
def test_service_encrypted_dataset_default_info(namespace, dataset_creation_params, share_create_params, path_field):
    with dataset('test_sharing_locked_ds_info', data={
        **ENCRYPTION_PARAMETERS,
        **dataset_creation_params,
    }) as ds:
        path = f'zvol/{ds}' if dataset_creation_params.get('type') == 'VOLUME' else f'/mnt/{ds}'
        share_create_params[path_field] = path
        share = call(f'{namespace}.create', share_create_params)
        assert share['locked'] is False

        with lock_dataset(ds):
            assert call(f'{namespace}.get_instance', share['id'])['locked'] is True

        assert call(f'{namespace}.get_instance', share['id'])['locked'] is False
