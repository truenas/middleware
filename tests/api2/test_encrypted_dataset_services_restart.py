import contextlib

import pytest
from pytest_dependency import depends
from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.pool import dataset

import os
import sys
sys.path.append(os.getcwd())


PASSPHRASE = 'testing123'
pytestmark = pytest.mark.zfs


@contextlib.contextmanager
def enable_auto_start(service_name):
    service = call('service.query', [['service', '=', service_name]], {'get': True})
    try:
        yield call('service.update', service['id'], {'enable': True})
    finally:
        call('service.update', service['id'], {'enable': False})


@contextlib.contextmanager
def start_service(service_name):
    try:
        yield call('service.start', service_name)
    finally:
        call('service.stop', service_name)


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


def test_service_restart_on_unlock_dataset(request):
    service_name = 'smb'
    registered_name = 'cifs'
    with dataset('testsvcunlock', data={
        'encryption': True,
        'encryption_options': {
            'algorithm': 'AES-256-GCM',
            'pbkdf2iters': 350000,
            'passphrase': PASSPHRASE,
        },
        'inherit_encryption': False
    }) as ds:
        path = f'/mnt/{ds}'
        share = call(f'sharing.{service_name}.create', {'path': path, 'name': 'smb-dataset'})
        assert share['locked'] is False

        with start_service(registered_name) as service_started:
            assert service_started is True

            call('service.stop', registered_name)
            assert call('service.started', registered_name) is False
            with enable_auto_start(registered_name):
                with lock_dataset(ds):
                    assert call(f'sharing.{service_name}.get_instance', share['id'])['locked'] is True
                    assert call('service.started', registered_name) is False

                assert call(f'sharing.{service_name}.get_instance', share['id'])['locked'] is False
                assert call('service.started', registered_name) is True
