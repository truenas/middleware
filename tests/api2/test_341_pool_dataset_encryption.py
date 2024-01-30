#!/usr/bin/env python3

# License: BSD

import pytest
import sys
import os
import secrets
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, PUT, wait_on_job, SSH_TEST
from auto_config import ha, ip, password, user

# genrated token_hex 32bit for
pool_token_hex = secrets.token_hex(32)
pool_token_hex2 = secrets.token_hex(32)
dataset_token_hex = secrets.token_hex(32)
dataset_token_hex2 = secrets.token_hex(32)
encrypted_pool_name = 'test_encrypted'
dataset = f'{encrypted_pool_name}/encrypted'
dataset_url = dataset.replace('/', '%2F')
child_dataset = f'{dataset}/child'
child_dataset_url = child_dataset.replace('/', '%2F')
pytestmark = pytest.mark.zfs


@pytest.mark.dependency(name="CREATED_POOL")
def test_create_a_normal_pool(request):
    global pool_id, pool_disks
    # Get one disk for encryption testing
    pool_disks = [POST('/disk/get_unused/', controller_a=ha).json()[0]['name']]
    payload = {
        'name': encrypted_pool_name,
        'encryption': False,
        'topology': {
            'data': [
                {'type': 'STRIPE', 'disks': pool_disks}
            ],
        },
        "allow_duplicate_serials": True,
    }
    results = POST('/pool/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 240)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_id = job_status['results']['result']['id']


def test_create_a_passphrase_encrypted_root_on_normal_pool(request):
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
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'PASSPHRASE', results.text


def test_verify_pool_dataset_does_not_leak_passphrase_into_middleware_log(request):
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_add_the_comment_on_the_passphrase_encrypted_root(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'comments': 'testing encrypted dataset'
    }
    results = PUT(f'/pool/dataset/id/{dataset_url}/', payload)
    assert results.status_code == 200, results.text


def test_change_a_passphrase_encrypted_root_key_encryption(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset,
        'change_key_options': {
            'key': dataset_token_hex,
        }
    }
    results = POST('/pool/dataset/change_key/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_verify_that_the_dataset_encrypted_root_changed_to_key_encryption(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'HEX', results.text


def test_delete_passphrase_encrypted_root(request):
    depends(request, ['CREATED_POOL'])
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_create_not_encrypted_dataset_on_a_normal_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption': False,
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] is None, results.text


def test_delete_not_encrypted_dataset(request):
    depends(request, ['CREATED_POOL'])
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_create_a_dataset_with_inherit_encryption_true_on_a_normal_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'inherit_encryption': True
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_verify_that_the_dataset_created_is_not_encrypted_like_the_parrent(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] is None, results.text


def test_delete_dataset(request):
    depends(request, ['CREATED_POOL'])
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_try_to_create_an_encrypted_dataset_with_pbkdf2itersl_zero(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption_options': {
            'pbkdf2iters': 0,
        },
        'encryption': True,
        'inherit_encryption': False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text
    assert 'Should be greater or equal than 100000' in results.text, results.text


def test_try_to_create_an_encrypted_dataset_with_inherit_encryption_true(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption_options': {
            'passphrase': 'my_passphrase',
        },
        'encryption': True,
        'inherit_encryption': True
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text
    assert 'Must be disabled when encryption is enabled' in results.text, results.text


def test_verify_pool_encrypted_dataset_does_not_leak_passphrase_into_middleware_log(request):
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_try_to_create_an_encrypted_dataset_with_passphrase_and_generate_key(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption_options': {
            'generate_key': True,
            'passphrase': 'my_passphrase',
        },
        'encryption': True,
        'inherit_encryption': False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text
    assert 'Must be disabled when dataset is to be encrypted with passphrase' in results.text, results.text


def test_create_an_encrypted_root_with_generate_key(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption_options': {
            'generate_key': True,
        },
        'encryption': True,
        'inherit_encryption': False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'HEX', results.text


def test_delete_generate_key_encrypted_root(request):
    depends(request, ['CREATED_POOL'])
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_create_an_encrypted_root_with_a_key(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'encryption_options': {
            'key': dataset_token_hex,
        },
        'encryption': True,
        'inherit_encryption': False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'HEX', results.text


def test_verify_pool_encrypted_root_dataset_does_not_leak_encryption_key_into_middleware_log(request):
    cmd = f"""grep -R "{dataset_token_hex}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_make_sure_we_are_not_able_to_lock_key_encrypted_dataset(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset,
        'lock_options': {
            'force_umount': True
        }
    }
    results = POST('/pool/dataset/lock', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'FAILED', str(job_status['results'])
    assert 'Only datasets which are encrypted with passphrase can be locked' in job_status['results']['error'],\
        job_status['results']['error']


def test_change_a_key_encrypted_dataset_to_passphrase(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset,
        'change_key_options': {
            'passphrase': 'my_passphrase'
        }
    }
    results = POST('/pool/dataset/change_key/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_verify_that_the_dataset_changed_to_passphrase(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'PASSPHRASE', results.text


def test_verify_pool_dataset_change_key_does_not_leak_passphrase_into_middleware_log(request):
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_lock_passphrase_encrypted_datasets_and_ensure_they_get_locked(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset,
        'lock_options': {
            'force_umount': True
        }
    }
    results = POST('/pool/dataset/lock', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_verify_passphrase_encrypted_root_is_locked(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset
    }
    results = POST('/pool/dataset/encryption_summary/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_status_result = job_status['results']['result']
    for dictionary in job_status_result:
        if dictionary['name'] == dataset:
            assert dictionary['key_format'] == 'PASSPHRASE', str(job_status_result)
            assert dictionary['unlock_successful'] is False, str(job_status_result)
            assert dictionary['locked'] is True, str(job_status_result)
            break
    else:
        assert False, str(job_status_result)


def test_unlock_passphrase_encrypted_datasets_with_wrong_passphrase(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset,
        'unlock_options': {
            'recursive': True,
            'datasets': [
                {
                    'name': dataset,
                    'passphrase': 'bad_passphrase'
                }
            ]
        }
    }
    results = POST('/pool/dataset/unlock/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    assert job_status['results']['result']['failed'][dataset]['error'] == 'Invalid Key', str(job_status['results'])


def test_verify_passphrase_encrypted_root_still_locked(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset
    }
    results = POST('/pool/dataset/encryption_summary/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_status_result = job_status['results']['result']
    for dictionary in job_status_result:
        if dictionary['name'] == dataset:
            assert dictionary['key_format'] == 'PASSPHRASE', str(job_status_result)
            assert dictionary['unlock_successful'] is False, str(job_status_result)
            assert dictionary['locked'] is True, str(job_status_result)
            break
    else:
        assert False, str(job_status_result)


def test_unlock_passphrase_encrypted_datasets(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset,
        'unlock_options': {
            'recursive': True,
            'datasets': [
                {
                    'name': dataset,
                    'passphrase': 'my_passphrase'
                }
            ]
        }
    }
    results = POST('/pool/dataset/unlock/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    assert job_status['results']['result']['unlocked'] == [dataset], str(job_status['results'])


def test_verify_passphrase_encrypted_root_is_unlocked(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset
    }
    results = POST('/pool/dataset/encryption_summary/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_status_result = job_status['results']['result']
    for dictionary in job_status_result:
        if dictionary['name'] == dataset:
            assert dictionary['key_format'] == 'PASSPHRASE', str(job_status_result)
            assert dictionary['unlock_successful'] is True, str(job_status_result)
            assert dictionary['locked'] is False, str(job_status_result)
            break
    else:
        assert False, str(job_status_result)


def test_delete_encrypted_dataset(request):
    depends(request, ['CREATED_POOL'])
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_delete_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'cascade': True,
        'restart_services': True,
        'destroy': True
    }
    results = POST(f'/pool/id/{pool_id}/export/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


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
        "allow_duplicate_serials": True,
    }
    results = POST('/pool/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 240)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_id = job_status['results']['result']['id']


def test_verify_pool_does_not_leak_passphrase_into_middleware_log(request):
    cmd = """grep -R "my_pool_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_verify_the_pool_dataset_is_passphrase_encrypted_and_algorithm_encryption(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{encrypted_pool_name}/')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'PASSPHRASE', results.text
    assert results.json()['encryption_algorithm']['value'] == 'AES-128-CCM', results.text


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
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_verify_pool_encrypted_root_dataset_change_key_does_not_leak_passphrase_into_middleware_log(request):
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_try_to_change_a_passphrase_encrypted_root_to_key_on_passphrase_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset,
        'change_key_options': {
            'key': dataset_token_hex,
        }
    }
    results = POST('/pool/dataset/change_key/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'FAILED', str(job_status['results'])


def test_verify_pool_dataset_change_key_does_not_leak_passphrase_into_middleware_log_after_key_change(request):
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_delete_encrypted_dataset_from_encrypted_root_on_passphrase_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_create_a_dataset_to_inherit_encryption_from_the_passphrase_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'inherit_encryption': True
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'PASSPHRASE', results.text


def test_delete_encrypted_dataset_from_the_passphrase_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


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
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text


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
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text


def test_verify_pool_key_encrypted_dataset_does_not_leak_encryption_key_into_middleware_log(request):
    cmd = f"""grep -R "{dataset_token_hex}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_delete_the_passphrase_encrypted_pool_with_is_datasets(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'cascade': True,
        'restart_services': True,
        'destroy': True
    }
    results = POST(f'/pool/id/{pool_id}/export/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


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
        "allow_duplicate_serials": True,
    }
    results = POST('/pool/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 240)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_id = job_status['results']['result']['id']


def test_verify_pool_does_not_leak_encryption_key_into_middleware_log(request):
    cmd = f"""grep -R "{pool_token_hex}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_verify_the_pool_dataset_is_hex_key_encrypted_and_algorithm_encryption(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{encrypted_pool_name}/')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'HEX', results.text
    assert results.json()['encryption_algorithm']['value'] == 'AES-128-CCM', results.text


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
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'HEX', results.text


def test_verify_pool_dataset_does_not_leak_encryption_hex_key_into_middleware_log(request):
    cmd = f"""grep -R "{dataset_token_hex}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_change_a_key_encrypted_root_to_passphrase_on_key_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset,
        'change_key_options': {
            'passphrase': 'my_passphrase',
        }
    }
    results = POST('/pool/dataset/change_key/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_verify_pool_encrypted_root_key_does_not_leak_passphrase_into_middleware_log(request):
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_verify_the_dataset_changed_to_passphrase(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'PASSPHRASE', results.text


def test_lock_passphrase_encrypted_dataset(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset,
        'lock_options': {
            'force_umount': True
        }
    }
    results = POST('/pool/dataset/lock', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_verify_the_dataset_is_locked(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['locked'] is True, results.text


def test_verify_passphrase_encrypted_root_unlock_successful_is_false(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset
    }
    results = POST('/pool/dataset/encryption_summary/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_status_result = job_status['results']['result']
    for dictionary in job_status_result:
        if dictionary['name'] == dataset:
            assert dictionary['unlock_successful'] is False, str(job_status_result)
            assert dictionary['locked'] is True, str(job_status_result)
            break
    else:
        assert False, str(job_status_result)


def test_unlock_passphrase_key_encrypted_datasets(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset,
        'unlock_options': {
            'recursive': True,
            'datasets': [
                {
                    'name': dataset,
                    'passphrase': 'my_passphrase'
                }
            ]
        }
    }
    results = POST('/pool/dataset/unlock/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    assert job_status['results']['result']['unlocked'] == [dataset], str(job_status['results'])


def test_verify_pool_dataset_unlock_does_not_leak_passphrase_into_middleware_log(request):
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_verify_passphrase_key_encrypted_root_is_unlocked(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset
    }
    results = POST('/pool/dataset/encryption_summary/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_status_result = job_status['results']['result']
    for dictionary in job_status_result:
        if dictionary['name'] == dataset:
            assert dictionary['unlock_successful'] is True, str(job_status_result)
            assert dictionary['locked'] is False, str(job_status_result)
            break
    else:
        assert False, str(job_status_result)


def test_delete_passphrase_key_encrypted_dataset(request):
    depends(request, ['CREATED_POOL'])
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_create_an_dataset_with_inherit_encryption_from_the_key_encrypted_pool(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'name': dataset,
        'inherit_encryption': True
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'HEX', results.text


def test_delete_inherit_encryption_from_the_key_encrypted_pool_dataset(request):
    depends(request, ['CREATED_POOL'])
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


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
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_delete_generate_key_encrypted_dataset(request):
    depends(request, ['CREATED_POOL'])
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


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
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_verify_pool_passphrase_encrypted_root_dataset_parrent_does_not_leak_passphrase_into_middleware_log(request):
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
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
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_verify_encrypted_root_child_of_passphrase_parent_dataset_does_not_leak_passphrase_into_middleware_log(request):
    cmd = """grep -R "my_passphrase2" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_lock_passphrase_encrypted_root_with_is_child(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset,
    }
    results = POST('/pool/dataset/lock', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_verify_the_parrent_encrypted_root_unlock_successful_is_false(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset
    }
    results = POST('/pool/dataset/encryption_summary/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_status_result = job_status['results']['result']
    for dictionary in job_status_result:
        if dictionary['name'] == dataset:
            assert dictionary['unlock_successful'] is False, str(job_status_result)
            assert dictionary['locked'] is True, str(job_status_result)
            break
    else:
        assert False, str(job_status_result)


def test_verify_the_parrent_encrypted_root_dataset_is_locked(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['locked'] is True, results.text


def test_verify_the_chid_of_the_encrypted_root_parent_unlock_successful_is_false(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': child_dataset
    }
    results = POST('/pool/dataset/encryption_summary/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_status_result = job_status['results']['result']
    for dictionary in job_status_result:
        if dictionary['name'] == child_dataset:
            assert dictionary['unlock_successful'] is False, str(job_status_result)
            assert dictionary['locked'] is True, str(job_status_result)
            break
    else:
        assert False, str(job_status_result)


def test_verify_the_child_dataset_is_locked(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{child_dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['locked'] is True, results.text


def test_try_to_unlock_the_child_of_lock_parent_encrypted_root(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': child_dataset,
        'unlock_options': {
            'recursive': True,
            'datasets': [
                {
                    'name': child_dataset,
                    'passphrase': 'my_passphrase2'
                }
            ]
        }
    }
    results = POST('/pool/dataset/unlock/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'FAILED', str(job_status['results'])
    assert f'{child_dataset} has locked parents' in str(job_status['results']), str(job_status['results'])
    assert job_status['results']['result'] is None, str(job_status['results'])


def test_verify_child_of_lock_parent_encrypted_root_dataset_unlock_do_not_leak_passphrase_into_middleware_log(request):
    cmd = """grep -R "my_passphrase2" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_Verify_chid_unlock_successful_is_still_false(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': child_dataset
    }
    results = POST('/pool/dataset/encryption_summary/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_status_result = job_status['results']['result']
    for dictionary in job_status_result:
        if dictionary['name'] == child_dataset:
            assert dictionary['unlock_successful'] is False, str(job_status_result)
            assert dictionary['locked'] is True, str(job_status_result)
            break
    else:
        assert False, str(job_status_result)


def test_unlock_parent_dataset_with_child_recursively(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset,
        'unlock_options': {
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
    }
    results = POST('/pool/dataset/unlock/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    assert job_status['results']['result']['unlocked'] == [dataset, child_dataset], str(job_status['results'])


def test_verify_pool_dataset_unlock_with_child_dataset_does_not_leak_passphrase_into_middleware_log(request):
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])
    cmd = """grep -R "my_passphrase2" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_verify_the_parent_dataset_unlock_successful_is_true(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': dataset
    }
    results = POST('/pool/dataset/encryption_summary/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_status_result = job_status['results']['result']
    for dictionary in job_status_result:
        if dictionary['name'] == dataset:
            assert dictionary['unlock_successful'] is True, str(job_status_result)
            assert dictionary['locked'] is False, str(job_status_result)
            break
    else:
        assert False, str(job_status_result)


def test_verify_the_dataset_is_unlocked(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{child_dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['locked'] is False, results.text


def test_verify_the_child_dataset_unlock_successful_is_true(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'id': child_dataset
    }
    results = POST('/pool/dataset/encryption_summary/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_status_result = job_status['results']['result']
    for dictionary in job_status_result:
        if dictionary['name'] == child_dataset:
            assert dictionary['unlock_successful'] is True, str(job_status_result)
            assert dictionary['locked'] is False, str(job_status_result)
            break
    else:
        assert False, str(job_status_result)


def test_verify_the_child_dataset_is_unlocked(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{child_dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['locked'] is False, results.text


def test_delete_dataset_with_is_child_recursive(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        "recursive": True,
    }
    results = DELETE(f'/pool/dataset/id/{dataset_url}/', payload)
    assert results.status_code == 200, results.text


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
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_verify_pool_encrypted_dataset_on_key_encrypted_pool_does_not_leak_encryption_key_into_middleware_log(request):
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
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
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_verify_ncrypted_root_from_key_encrypted_root_does_not_leak_passphrase_into_middleware_log(request):
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_verify_the_new_passprase_encrypted_root_is_passphrase(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{child_dataset_url}')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'PASSPHRASE', results.text


def test_run_inherit_parent_encryption_properties_on_the_passprase(request):
    depends(request, ['CREATED_POOL'])
    results = POST('/pool/dataset/inherit_parent_encryption_properties', child_dataset)
    assert results.status_code == 200, results.text


def test_verify_the_the_child_got_props_by_the_parent_root(request):
    depends(request, ['CREATED_POOL'])
    results = GET(f'/pool/dataset/id/{child_dataset_url}')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'HEX', results.text


def test_delete_the_key_encrypted_pool_with_all_the_dataset(request):
    depends(request, ['CREATED_POOL'])
    payload = {
        'cascade': True,
        'restart_services': True,
        'destroy': True
    }
    results = POST(f'/pool/id/{pool_id}/export/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
