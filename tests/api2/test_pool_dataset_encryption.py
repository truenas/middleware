import contextlib
import secrets

import pytest
from pytest_dependency import depends

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh
from truenas_api_client.exc import ClientException


# genrated token_hex 32bit for
pool_token_hex = secrets.token_hex(32)
pool_token_hex2 = secrets.token_hex(32)
dataset_token_hex = secrets.token_hex(32)
dataset_token_hex2 = secrets.token_hex(32)

encrypted_pool_name = 'test_encrypted'
dataset = f'{encrypted_pool_name}/encrypted'
child_dataset = f'{dataset}/child'


@pytest.fixture(scope='class')
def create_pool():
    with another_pool({'name': encrypted_pool_name}):
        yield


@contextlib.contextmanager
def create_dataset(payload):
    yield call('pool.dataset.create', payload)
    assert call('pool.dataset.delete', payload['name'])


def check_log_for(phrase):
    cmd = f'grep -R "{phrase}" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


@pytest.mark.usefixtures('create_pool')
class TestNormalPool:

    def test_passphrase_encrypted_root(self):
        payload = {
            'name': dataset,
            'encryption_options': {
                'generate_key': False,
                'pbkdf2iters': 100000,
                'algorithm': 'AES-128-CCM',
                'passphrase': 'my_passphrase',
            },
            'encryption': True,
            'inherit_encryption': False
        }
        with create_dataset(payload) as ds:
            assert ds['key_format']['value'] == 'PASSPHRASE'
            check_log_for('my_passphrase')

            call('pool.dataset.update', dataset, {'comments': 'testing encrypted dataset'})
            call('pool.dataset.change_key', dataset, {'key': dataset_token_hex}, job=True)

            ds = call('pool.dataset.get_instance', dataset)
            assert ds['key_format']['value'] == 'HEX'

    @pytest.mark.parametrize('payload', [
        {
            'encryption': False,
        },
        {
            'inherit_encryption': True
        }
    ])
    def test_dataset_not_encrypted(self, payload: dict):
        payload['name'] = dataset
        with create_dataset(payload) as ds:
            assert ds['key_format']['value'] is None

    @pytest.mark.parametrize('payload, message', [
        (
            {
                'encryption_options': {
                    'pbkdf2iters': 0
                },
                'inherit_encryption': False
            },
            'Should be greater or equal than 100000'
        ),
        (
            {
                'encryption_options': {
                    'passphrase': 'my_passphrase',
                },
                'inherit_encryption': True
            },
            'Must be disabled when encryption is enabled'
        ),
        (
            {
                'encryption_options': {
                    'generate_key': True,
                    'passphrase': 'my_passphrase',
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
        check_log_for('my_passphrase')

    @pytest.mark.parametrize('payload', [
        {
            'encryption_options': {
                'generate_key': True,
            },
        },
        {
            'encryption_options': {
                'key': dataset_token_hex,
            },
        }
    ])
    def test_encrypted_root_with_key(self, payload: dict):
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
            
            # Change to a passphrase-encrypted dataset
            call('pool.dataset.change_key', dataset, {'passphrase': 'my_passphrase'}, job=True)
            ds = call('pool.dataset.get_instance', dataset)
            assert ds['key_format']['value'] == 'PASSPHRASE'
            check_log_for('my_passphrase')

            assert call('pool.dataset.lock', dataset, {'force_umount': True}, job=True)


    def test_verify_passphrase_encrypted_root_is_locked(self):
        job_status_result = call('pool.dataset.encryption_summary', dataset, job=True)
        for dictionary in job_status_result:
            if dictionary['name'] == dataset:
                assert dictionary['key_format'] == 'PASSPHRASE', str(job_status_result)
                assert dictionary['unlock_successful'] is False, str(job_status_result)
                assert dictionary['locked'] is True, str(job_status_result)
                break
        else:
            pytest.fail(str(job_status_result))


    def test_unlock_passphrase_encrypted_datasets_with_wrong_passphrase(self, request):
        depends(request, ['CREATED_POOL'])
        payload = {
            'recursive': True,
            'datasets': [
                {
                    'name': dataset,
                    'passphrase': 'bad_passphrase'
                }
            ]
        }
        job_status = call('pool.dataset.unlock', dataset, payload, job=True)
        assert job_status['failed'][dataset]['error'] == 'Invalid Key', str(job_status['results'])


    def test_verify_passphrase_encrypted_root_still_locked(self, request):
        depends(request, ['CREATED_POOL'])
        job_status_result = call('pool.dataset.encryption_summary', dataset, job=True)
        for dictionary in job_status_result:
            if dictionary['name'] == dataset:
                assert dictionary['key_format'] == 'PASSPHRASE', str(job_status_result)
                assert dictionary['unlock_successful'] is False, str(job_status_result)
                assert dictionary['locked'] is True, str(job_status_result)
                break
        else:
            pytest.fail(str(job_status_result))


    def test_unlock_passphrase_encrypted_datasets(self, request):
        depends(request, ['CREATED_POOL'])
        payload = {
            'recursive': True,
            'datasets': [
                {
                    'name': dataset,
                    'passphrase': 'my_passphrase'
                }
            ]
        }
        job_status = call('pool.dataset.unlock', dataset, payload, job=True)
        assert job_status['unlocked'] == [dataset], str(job_status)


    def test_verify_passphrase_encrypted_root_is_unlocked(self, request):
        depends(request, ['CREATED_POOL'])
        job_status_result = call('pool.dataset.encryption_summary', dataset, job=True)
        for dictionary in job_status_result:
            if dictionary['name'] == dataset:
                assert dictionary['key_format'] == 'PASSPHRASE', str(job_status_result)
                assert dictionary['unlock_successful'] is True, str(job_status_result)
                assert dictionary['locked'] is False, str(job_status_result)
                break
        else:
            pytest.fail(str(job_status_result))


    def test_delete_encrypted_dataset(self, request):
        depends(request, ['CREATED_POOL'])
        assert call('pool.dataset.delete', dataset)


#########################################################


def test_create_a_passphrase_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    global pool_id
    payload = {
        'name': encrypted_pool_name,
        'encryption': True,
        'encryption_options': {
            'algorithm': 'AES-128-CCM',
            'passphrase': 'my_pool_passphrase',
        },
        'topology': {
            'data': [
                {'type': 'STRIPE', 'disks': pool_disks}
            ],
        },
        'allow_duplicate_serials': True,
    }
    pool_id = call('pool.create', payload, job=True)['id']


def test_verify_pool_does_not_leak_passphrase_into_middleware_log(request):
    cmd = 'grep -R "my_pool_passphrase" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_verify_the_pool_dataset_is_passphrase_encrypted_and_algorithm_encryption(request):
    depends(request, ['CREATED_POOL'])
    results = call('pool.dataset.get_instance', encrypted_pool_name)
    assert results['key_format']['value'] == 'PASSPHRASE', results
    assert results['encryption_algorithm']['value'] == 'AES-128-CCM', results


def test_create_a_passphrase_encrypted_root_on_passphrase_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption_options': {
            'generate_key': False,
            'pbkdf2iters': 100000,
            'algorithm': 'AES-128-CCM',
            'passphrase': 'my_passphrase',
        },
        'encryption': True,
        'inherit_encryption': False
    }
    call('pool.dataset.create', payload)


def test_verify_pool_encrypted_root_dataset_change_key_does_not_leak_passphrase_into_middleware_log(request):
    cmd = 'grep -R "my_passphrase" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_try_to_change_a_passphrase_encrypted_root_to_key_on_passphrase_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'key': dataset_token_hex
    }
    with pytest.raises(Exception, match=f'{dataset} has parent\\(s\\) which are encrypted with a passphrase'):
        call('pool.dataset.change_key', dataset, payload, job=True)


def test_verify_pool_dataset_change_key_does_not_leak_passphrase_into_middleware_log_after_key_change(request):
    cmd = 'grep -R "my_passphrase" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_delete_encrypted_dataset_from_encrypted_root_on_passphrase_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    assert call('pool.dataset.delete', dataset)


def test_create_a_dataset_to_inherit_encryption_from_the_passphrase_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'inherit_encryption': True
    }
    results = call('pool.dataset.create', payload)
    assert results['key_format']['value'] == 'PASSPHRASE', results


def test_delete_encrypted_dataset_from_the_passphrase_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    assert call('pool.dataset.delete', dataset)


def test_try_to_create_an_encrypted_root_with_generate_key_on_passphrase_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption_options': {
            'generate_key': True,
        },
        'encryption': True,
        'inherit_encryption': False
    }
    with pytest.raises(ValidationErrors, match='Passphrase encrypted datasets cannot have children encrypted with a key'):
        call('pool.dataset.create', payload)


def test_try_to_create_an_encrypted_root_with_key_on_passphrase_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption_options': {
            'key': dataset_token_hex,
        },
        'encryption': True,
        'inherit_encryption': False
    }
    with pytest.raises(ValidationErrors, match='Passphrase encrypted datasets cannot have children encrypted with a key'):
        call('pool.dataset.create', payload)


def test_verify_pool_key_encrypted_dataset_does_not_leak_encryption_key_into_middleware_log(request):
    cmd = f'grep -R "{dataset_token_hex}" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_delete_the_passphrase_encrypted_pool_with_is_datasets(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'cascade': True,
        'restart_services': True,
        'destroy': True
    }
    call('pool.export', pool_id, payload, job=True)


############################################################################


def test_creating_a_key_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    global pool_id
    payload = {
        'name': encrypted_pool_name,
        'encryption': True,
        'encryption_options': {
            'algorithm': 'AES-128-CCM',
            'key': pool_token_hex,
        },
        'topology': {
            'data': [
                {'type': 'STRIPE', 'disks': pool_disks}
            ],
        },
        'allow_duplicate_serials': True,
    }
    pool_id = call('pool.create', payload, job=True)['id']


def test_verify_pool_does_not_leak_encryption_key_into_middleware_log(request):
    cmd = f'grep -R "{pool_token_hex}" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_verify_the_pool_dataset_is_hex_key_encrypted_and_algorithm_encryption(request):
    depends(request, ['CREATED_POOL'])
    results = call('pool.dataset.get_instance', encrypted_pool_name)
    assert results['key_format']['value'] == 'HEX', results
    assert results['encryption_algorithm']['value'] == 'AES-128-CCM', results


def test_creating_a_key_encrypted_root_on_key_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption_options': {
            'key': dataset_token_hex,
        },
        'encryption': True,
        'inherit_encryption': False
    }
    results = call('pool.dataset.create', payload)
    assert results['key_format']['value'] == 'HEX', results


def test_verify_pool_dataset_does_not_leak_encryption_hex_key_into_middleware_log(request):
    cmd = f'grep -R "{dataset_token_hex}" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_change_a_key_encrypted_root_to_passphrase_on_key_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'passphrase': 'my_passphrase'
    }
    call('pool.dataset.change_key', dataset, payload, job=True)


def test_verify_pool_encrypted_root_key_does_not_leak_passphrase_into_middleware_log(request):
    cmd = 'grep -R "my_passphrase" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_verify_the_dataset_changed_to_passphrase(request):
    depends(request, ['CREATED_POOL'])
    results = call('pool.dataset.get_instance', dataset)
    assert results['key_format']['value'] == 'PASSPHRASE', results


def test_lock_passphrase_encrypted_dataset(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'force_umount': True
    }
    assert call('pool.dataset.lock', dataset, payload, job=True)


def test_verify_the_dataset_is_locked(request):
    depends(request, ['CREATED_POOL'])
    results = call('pool.dataset.get_instance', dataset)
    assert results['locked'] is True, results


def test_verify_passphrase_encrypted_root_unlock_successful_is_false(request):
    depends(request, ['CREATED_POOL'])
    job_status_result = call('pool.dataset.encryption_summary', dataset, job=True)
    for dictionary in job_status_result:
        if dictionary['name'] == dataset:
            assert dictionary['unlock_successful'] is False, str(job_status_result)
            assert dictionary['locked'] is True, str(job_status_result)
            break
    else:
        pytest.fail(str(job_status_result))


def test_unlock_passphrase_key_encrypted_datasets(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'recursive': True,
        'datasets': [
            {
                'name': dataset,
                'passphrase': 'my_passphrase'
            }
        ]
    }
    job_status = call('pool.dataset.unlock', dataset, payload, job=True)
    assert job_status['unlocked'] == [dataset], job_status


def test_verify_pool_dataset_unlock_does_not_leak_passphrase_into_middleware_log(request):
    cmd = 'grep -R "my_passphrase" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_verify_passphrase_key_encrypted_root_is_unlocked(request):
    depends(request, ['CREATED_POOL'])
    job_status_result = call('pool.dataset.encryption_summary', dataset, job=True)
    for dictionary in job_status_result:
        if dictionary['name'] == dataset:
            assert dictionary['unlock_successful'] is True, str(job_status_result)
            assert dictionary['locked'] is False, str(job_status_result)
            break
    else:
        pytest.fail(str(job_status_result))


def test_delete_passphrase_key_encrypted_dataset(request):
    depends(request, ['CREATED_POOL'])
    assert call('pool.dataset.delete', dataset)


def test_create_an_dataset_with_inherit_encryption_from_the_key_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'inherit_encryption': True
    }
    results = call('pool.dataset.create', payload)
    assert results['key_format']['value'] == 'HEX', results


def test_delete_inherit_encryption_from_the_key_encrypted_pool_dataset(request):
    depends(request, ['CREATED_POOL'])
    assert call('pool.dataset.delete', dataset)


def test_create_an_encrypted_dataset_with_generate_key_on_key_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption_options': {
            'generate_key': True,
        },
        'encryption': True,
        'inherit_encryption': False
    }
    call('pool.dataset.create', payload)


def test_delete_generate_key_encrypted_dataset(request):
    depends(request, ['CREATED_POOL'])
    assert call('pool.dataset.delete', dataset)


def test_create_a_passphrase_encrypted_root_dataset_parrent(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption_options': {
            'passphrase': 'my_passphrase',
        },
        'encryption': True,
        'inherit_encryption': False
    }
    call('pool.dataset.create', payload)


def test_verify_pool_passphrase_encrypted_root_dataset_parrent_does_not_leak_passphrase_into_middleware_log(request):
    cmd = 'grep -R "my_passphrase" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_create_a_passphrase_encrypted_root_child_of_passphrase_parent(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': child_dataset,
        'encryption_options': {
            'passphrase': 'my_passphrase2',
        },
        'encryption': True,
        'inherit_encryption': False
    }
    call('pool.dataset.create', payload)


def test_verify_encrypted_root_child_of_passphrase_parent_dataset_does_not_leak_passphrase_into_middleware_log(request):
    cmd = 'grep -R "my_passphrase2" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_lock_passphrase_encrypted_root_with_is_child(request):
    depends(request, ['CREATED_POOL'])
    assert call('pool.dataset.lock', dataset, job=True)


def test_verify_the_parrent_encrypted_root_unlock_successful_is_false(request):
    depends(request, ['CREATED_POOL'])
    job_status_result = call('pool.dataset.encryption_summary', dataset, job=True)
    for dictionary in job_status_result:
        if dictionary['name'] == dataset:
            assert dictionary['unlock_successful'] is False, str(job_status_result)
            assert dictionary['locked'] is True, str(job_status_result)
            break
    else:
        pytest.fail(str(job_status_result))


def test_verify_the_parent_encrypted_root_dataset_is_locked(request):
    depends(request, ['CREATED_POOL'])
    results = call('pool.dataset.get_instance', dataset)
    assert results['locked'] is True, results


def test_verify_the_chid_of_the_encrypted_root_parent_unlock_successful_is_false(request):
    depends(request, ['CREATED_POOL'])
    job_status_result = call('pool.dataset.encryption_summary', child_dataset, job=True)
    for dictionary in job_status_result:
        if dictionary['name'] == child_dataset:
            assert dictionary['unlock_successful'] is False, str(job_status_result)
            assert dictionary['locked'] is True, str(job_status_result)
            break
    else:
        pytest.fail(str(job_status_result))


def test_verify_the_child_dataset_is_locked(request):
    depends(request, ['CREATED_POOL'])
    results = call('pool.dataset.get_instance', child_dataset)
    assert results['locked'] is True, results


def test_try_to_unlock_the_child_of_lock_parent_encrypted_root(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'recursive': True,
        'datasets': [
            {
                'name': child_dataset,
                'passphrase': 'my_passphrase2'
            }
        ]
    }
    with pytest.raises(ClientException, match=f'{child_dataset} has locked parents {dataset} which must be unlocked first'):
        call('pool.dataset.unlock', child_dataset, payload, job=True)


def test_verify_child_of_lock_parent_encrypted_root_dataset_unlock_do_not_leak_passphrase_into_middleware_log(request):
    cmd = 'grep -R "my_passphrase2" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_verify_child_unlock_successful_is_still_false(request):
    depends(request, ['CREATED_POOL'])
    job_status_result = call('pool.dataset.encryption_summary', child_dataset, job=True)
    for dictionary in job_status_result:
        if dictionary['name'] == child_dataset:
            assert dictionary['unlock_successful'] is False, str(job_status_result)
            assert dictionary['locked'] is True, str(job_status_result)
            break
    else:
        pytest.fail(str(job_status_result))


def test_unlock_parent_dataset_with_child_recursively(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'recursive': True,
        'datasets': [
            {
                'name': dataset,
                'passphrase': 'my_passphrase'
            },
            {
                'name': child_dataset,
                'passphrase': 'my_passphrase2'
            }
        ]
    }
    job_status = call('pool.dataset.unlock', dataset, payload, job=True)
    assert job_status['unlocked'] == [dataset, child_dataset], job_status


def test_verify_pool_dataset_unlock_with_child_dataset_does_not_leak_passphrase_into_middleware_log(request):
    cmd = 'grep -R "my_passphrase" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])
    cmd = 'grep -R "my_passphrase2" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_verify_the_parent_dataset_unlock_successful_is_true(request):
    depends(request, ['CREATED_POOL'])
    job_status_result = call('pool.dataset.encryption_summary', dataset, job=True)
    for dictionary in job_status_result:
        if dictionary['name'] == dataset:
            assert dictionary['unlock_successful'] is True, str(job_status_result)
            assert dictionary['locked'] is False, str(job_status_result)
            break
    else:
        pytest.fail(str(job_status_result))


def test_verify_the_dataset_is_unlocked(request):
    depends(request, ['CREATED_POOL'])
    results = call('pool.dataset.get_instance', child_dataset)
    assert results['locked'] is False, results


def test_verify_the_child_dataset_unlock_successful_is_true(request):
    depends(request, ['CREATED_POOL'])
    job_status_result = call('pool.dataset.encryption_summary', child_dataset, job=True)
    for dictionary in job_status_result:
        if dictionary['name'] == child_dataset:
            assert dictionary['unlock_successful'] is True, str(job_status_result)
            assert dictionary['locked'] is False, str(job_status_result)
            break
    else:
        pytest.fail(str(job_status_result))


def test_verify_the_child_dataset_is_unlocked(request):
    depends(request, ['CREATED_POOL'])
    results = call('pool.dataset.get_instance', child_dataset)
    assert results['locked'] is False, results


def test_delete_dataset_with_is_child_recursive(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'recursive': True,
    }
    assert call('pool.dataset.delete', dataset, payload)


def test_creating_a_key_encrypted_dataset_on_key_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption_options': {
            'key': dataset_token_hex,
        },
        'encryption': True,
        'inherit_encryption': False
    }
    call('pool.dataset.create', payload)


def test_verify_pool_encrypted_dataset_on_key_encrypted_pool_does_not_leak_encryption_key_into_middleware_log(request):
    cmd = 'grep -R "my_passphrase" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_create_a_passphrase_encrypted_root_from_key_encrypted_root(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': child_dataset,
        'encryption_options': {
            'passphrase': 'my_passphrase',
        },
        'encryption': True,
        'inherit_encryption': False
    }
    call('pool.dataset.create', payload)


def test_verify_ncrypted_root_from_key_encrypted_root_does_not_leak_passphrase_into_middleware_log(request):
    cmd = 'grep -R "my_passphrase" /var/log/middlewared.log'
    results = ssh(cmd, check=False, complete_response=True)
    assert results['result'] is False, str(results['output'])


def test_verify_the_new_passprase_encrypted_root_is_passphrase(request):
    depends(request, ['CREATED_POOL'])
    results = call('pool.dataset.get_instance', child_dataset)
    assert results['key_format']['value'] == 'PASSPHRASE', results


def test_run_inherit_parent_encryption_properties_on_the_passprase(request):
    depends(request, ['CREATED_POOL'])
    call('pool.dataset.inherit_parent_encryption_properties', child_dataset)


def test_verify_the_the_child_got_props_by_the_parent_root(request):
    depends(request, ['CREATED_POOL'])
    results = call('pool.dataset.get_instance', child_dataset)
    assert results['key_format']['value'] == 'HEX', results


def test_delete_the_key_encrypted_pool_with_all_the_dataset(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'cascade': True,
        'restart_services': True,
        'destroy': True
    }
    call('pool.export', pool_id, payload, job=True)
