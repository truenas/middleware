import contextlib
import secrets

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh
from truenas_api_client.exc import ClientException


# genrated token_hex 32bit for
pool_token_hex = secrets.token_hex(32)
dataset_token_hex = secrets.token_hex(32)

encrypted_pool_name = 'test_encrypted'
dataset = f'{encrypted_pool_name}/encrypted'
child_dataset = f'{dataset}/child'
passphrase = 'my_passphrase'


def check_log_for(*phrases, should_find=False):
    search_string = '|'.join(phrases)
    cmd = f'grep -R -E "{search_string}" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is should_find, str(results['output'])


def verify_lock_status(ds, *, locked):
    job_status_result = call('pool.dataset.encryption_summary', ds, job=True)
    for dictionary in job_status_result:
        if dictionary['name'] == ds:
            assert dictionary['unlock_successful'] is not locked, str(job_status_result)
            assert dictionary['locked'] is locked, str(job_status_result)
            break
    else:
        pytest.fail(str(job_status_result))


@contextlib.contextmanager
def create_dataset(payload, **delete_args):
    yield call('pool.dataset.create', payload)
    assert call('pool.dataset.delete', payload['name'], delete_args)


@pytest.fixture(scope='class')
def normal_pool():
    with another_pool({'name': encrypted_pool_name}):
        yield


@pytest.fixture(scope='class')
def passphrase_pool():
    pool_passphrase = 'my_pool_passphrase'
    with another_pool({
        'name': encrypted_pool_name,
        'encryption': True,
        'encryption_options': {
            'algorithm': 'AES-128-CCM',
            'passphrase': pool_passphrase,
        },
    }):
        check_log_for(pool_passphrase)
        ds = call('pool.dataset.get_instance', encrypted_pool_name)
        assert ds['key_format']['value'] == 'PASSPHRASE', ds
        assert ds['encryption_algorithm']['value'] == 'AES-128-CCM', ds
        yield


@pytest.fixture(scope='class')
def key_pool():
    with another_pool({
        'name': encrypted_pool_name,
        'encryption': True,
        'encryption_options': {
            'algorithm': 'AES-128-CCM',
            'key': pool_token_hex,
        },
    }):
        check_log_for(pool_token_hex)
        ds = call('pool.dataset.get_instance', encrypted_pool_name)
        assert ds['key_format']['value'] == 'HEX', ds
        assert ds['encryption_algorithm']['value'] == 'AES-128-CCM', ds
        yield


@pytest.mark.usefixtures('normal_pool')
class TestNormalPool:

    def test_passphrase_encrypted_root(self):
        payload = {
            'name': dataset,
            'encryption_options': {
                'generate_key': False,
                'pbkdf2iters': 100000,
                'algorithm': 'AES-128-CCM',
                'passphrase': passphrase,
            },
            'encryption': True,
            'inherit_encryption': False
        }
        with create_dataset(payload) as ds:
            assert ds['key_format']['value'] == 'PASSPHRASE'
            check_log_for(passphrase)

            # Add a comment
            call('pool.dataset.update', dataset, {'comments': 'testing encrypted dataset'})

            # Change to key encryption
            call('pool.dataset.change_key', dataset, {'key': dataset_token_hex}, job=True)
            ds = call('pool.dataset.get_instance', dataset)
            assert ds['key_format']['value'] == 'HEX'

    @pytest.mark.parametrize('payload', [
        {'encryption': False},
        {'inherit_encryption': True}
    ])
    def test_dataset_not_encrypted(self, payload: dict):
        payload['name'] = dataset
        with create_dataset(payload) as ds:
            assert ds['key_format']['value'] is None

    @pytest.mark.parametrize('payload, message', [
        (
            {
                'encryption_options': {'pbkdf2iters': 0},
                'inherit_encryption': False
            },
            'Should be greater or equal than 100000'
        ),
        (
            {
                'encryption_options': {'passphrase': passphrase},
                'inherit_encryption': True
            },
            'Must be disabled when encryption is enabled'
        ),
        (
            {
                'encryption_options': {
                    'generate_key': True,
                    'passphrase': passphrase,
                },
                'inherit_encryption': False
            },
            'Must be disabled when dataset is to be encrypted with passphrase'
        )
    ])
    def test_try_to_create_invalid_encrypted_dataset(self, payload: dict, message: str):
        payload.update({
            'name': dataset,
            'encryption': True,
        })
        with pytest.raises(ValidationErrors, match=message):
            with create_dataset(payload): pass

    def test_invalid_encrypted_dataset_does_not_leak_passphrase_into_middleware_log(self):
        check_log_for(passphrase)

    @pytest.mark.parametrize('payload', [
        {'encryption_options': {'generate_key': True}},
        {'encryption_options': {'key': dataset_token_hex}}
    ])
    def test_encrypted_root_with_key_cannot_lock(self, payload: dict):
        payload.update({
            'name': dataset,
            'encryption': True,
            'inherit_encryption': False,
        })
        with create_dataset(payload) as ds:
            assert ds['key_format']['value'] == 'HEX'
            check_log_for(dataset_token_hex)

            with pytest.raises(ClientException, match='Only datasets which are encrypted with passphrase can be locked'):
                call('pool.dataset.lock', dataset, {'force_umount': True}, job=True)
            
    def test_encrypted_root_lock_unlock(self):
        # Start with key-encrypted dataset
        payload = {
            'name': dataset,
            'encryption': True,
            'inherit_encryption': False,
            'encryption_options': {'key': dataset_token_hex}
        }
        with create_dataset(payload):
            # Change to a passphrase-encrypted dataset
            call('pool.dataset.change_key', dataset, {'passphrase': passphrase}, job=True)
            ds = call('pool.dataset.get_instance', dataset)
            assert ds['key_format']['value'] == 'PASSPHRASE'
            check_log_for(passphrase)

            # Lock it
            assert call('pool.dataset.lock', dataset, {'force_umount': True}, job=True)
            verify_lock_status(dataset, locked=True)

            # Attempt to unlock with incorrect passphrase
            payload = {
                'recursive': True,
                'datasets': [{
                    'name': dataset,
                    'passphrase': 'bad_passphrase'
                }]
            }
            job_status = call('pool.dataset.unlock', dataset, payload, job=True)
            assert job_status['failed'][dataset]['error'] == 'Invalid Key', job_status
            verify_lock_status(dataset, locked=True)

            # Now actually unlock it
            payload['datasets'][0]['passphrase'] = passphrase
            job_status = call('pool.dataset.unlock', dataset, payload, job=True)
            assert job_status['unlocked'] == [dataset], job_status
            verify_lock_status(dataset, locked=False)


@pytest.mark.usefixtures('passphrase_pool')
class TestPassphraseEncryptedPool:

    def test_passphrase_encrypted_root_cannot_change_key(self):
        payload = {
            'name': dataset,
            'encryption_options': {
                'generate_key': False,
                'pbkdf2iters': 100000,
                'algorithm': 'AES-128-CCM',
                'passphrase': passphrase,
            },
            'encryption': True,
            'inherit_encryption': False
        }
        with create_dataset(payload):
            check_log_for(passphrase)
            with pytest.raises(Exception, match=f'{dataset} has parent\\(s\\) which are encrypted with a passphrase'):
                call('pool.dataset.change_key', dataset, {'key': dataset_token_hex}, job=True)

    def test_passphrase_encrypted_root_cannot_change_key_does_not_leak_passphrase_into_middleware_log(self):
        check_log_for(passphrase)

    def test_create_dataset_to_inherit_encryption_from_passphrase_encrypted_pool(self):
        payload = {
            'name': dataset,
            'inherit_encryption': True
        }
        with create_dataset(payload) as ds:
            assert ds['key_format']['value'] == 'PASSPHRASE', ds
    
    @pytest.mark.parametrize('payload', [
        {'encryption_options': {'generate_key': True}},
        {'encryption_options': {'key': dataset_token_hex}},
    ])
    def test_try_to_create_invalid_encrypted_dataset(self, payload: dict):
        payload.update({
            'name': dataset,
            'encryption': True,
            'inherit_encryption': False
        })
        with pytest.raises(ValidationErrors, match='Passphrase encrypted datasets cannot have children encrypted with a key'):
            with create_dataset(payload): pass

    def test_try_to_create_invalid_encrypted_dataset_does_not_leak_encryption_key_into_middleware_log(self):
        check_log_for(dataset_token_hex)


@pytest.mark.usefixtures('key_pool')
class TestKeyEncryptedPool:

    def test_key_encrypted_root(self):
        # Start with key-encrypted dataset
        payload = {
            'name': dataset,
            'encryption_options': {'key': dataset_token_hex},
            'encryption': True,
            'inherit_encryption': False
        }
        with create_dataset(payload) as ds:
            assert ds['key_format']['value'] == 'HEX', ds
            check_log_for(dataset_token_hex)

            # Change to passphrase encryption
            call('pool.dataset.change_key', dataset, {'passphrase': passphrase}, job=True)
            check_log_for(passphrase)
            ds = call('pool.dataset.get_instance', dataset)
            assert ds['key_format']['value'] == 'PASSPHRASE', ds

            # Lock the dataset
            assert call('pool.dataset.lock', dataset, {'force_umount': True}, job=True)
            ds = call('pool.dataset.get_instance', dataset)
            assert ds['locked'] is True, ds
            verify_lock_status(dataset, locked=True)

            # Unlock the dataset
            payload = {
                'recursive': True,
                'datasets': [{
                    'name': dataset,
                    'passphrase': passphrase
                }]
            }
            job_status = call('pool.dataset.unlock', dataset, payload, job=True)
            assert job_status['unlocked'] == [dataset], job_status
            check_log_for(passphrase)
            verify_lock_status(dataset, locked=False)

    def test_dataset_with_inherit_encryption(self):
        payload = {
            'name': dataset,
            'inherit_encryption': True
        }
        with create_dataset(payload) as ds:
            assert ds['key_format']['value'] == 'HEX', ds

    def test_encrypted_dataset_with_generate_key(self):
        payload = {
            'name': dataset,
            'encryption_options': {'generate_key': True},
            'encryption': True,
            'inherit_encryption': False
        }
        with create_dataset(payload): pass

    def test_passphrase_encrypted_dataset_parent_child_lock_unlock(self):
        payload = {
            'name': dataset,
            'encryption_options': {'passphrase': passphrase},
            'encryption': True,
            'inherit_encryption': False
        }
        with create_dataset(payload, recursive=True):  # Create parent dataset
            check_log_for(passphrase)

            # Create child dataset
            child_passphrase = 'my_passphrase2'
            payload.update({
                'name': child_dataset,
                'encryption_options': {'passphrase': child_passphrase},
            })
            call('pool.dataset.create', payload)
            check_log_for(child_passphrase)

            # Lock parent (and child)
            assert call('pool.dataset.lock', dataset, job=True)
            for ds_name in (dataset, child_dataset):
                ds = call('pool.dataset.get_instance', ds_name)
                assert ds['locked'] is True, ds
                verify_lock_status(ds_name, locked=True)

            # Try to unlock child
            payload = {
                'recursive': True,
                'datasets': [{
                    'name': child_dataset,
                    'passphrase': child_passphrase
                }]
            }
            with pytest.raises(ClientException, match=f'{child_dataset} has locked parents {dataset} which must be unlocked first'):
                call('pool.dataset.unlock', child_dataset, payload, job=True)
            check_log_for(child_passphrase)
            verify_lock_status(child_dataset, locked=True)

            # Unlock parent (and child)
            payload = {
                'recursive': True,
                'datasets': [
                    {
                        'name': dataset,
                        'passphrase': passphrase
                    },
                    {
                        'name': child_dataset,
                        'passphrase': child_passphrase
                    }
                ]
            }
            job_status = call('pool.dataset.unlock', dataset, payload, job=True)
            assert job_status['unlocked'] == [dataset, child_dataset], job_status
            check_log_for(passphrase, child_passphrase)
            for ds_name in (dataset, child_dataset):
                ds = call('pool.dataset.get_instance', ds_name)
                assert ds['locked'] is False, ds
                verify_lock_status(ds_name, locked=False)

    def test_key_encrypted_dataset(self):
        # Create parent dataset
        payload = {
            'name': dataset,
            'encryption_options': {'key': dataset_token_hex},
            'encryption': True,
            'inherit_encryption': False
        }
        call('pool.dataset.create', payload)
        check_log_for(dataset_token_hex)

        # Create child dataset
        payload.update({
            'name': child_dataset,
            'encryption_options': {'passphrase': passphrase},
        })
        call('pool.dataset.create', payload)
        check_log_for(passphrase)
        ds = call('pool.dataset.get_instance', child_dataset)
        assert ds['key_format']['value'] == 'PASSPHRASE', ds

        # Inherit key encryption from parent
        call('pool.dataset.inherit_parent_encryption_properties', child_dataset)
        ds = call('pool.dataset.get_instance', child_dataset)
        assert ds['key_format']['value'] == 'HEX', ds
