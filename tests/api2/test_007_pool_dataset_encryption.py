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
from auto_config import pool_name, ha, ip, password, user, dev_test

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(ha or dev_test, reason='Skipping test for HA')

nas_disk = GET('/boot/get_disks/', controller_a=ha).json()
disk_list = list(POST('/device/get_info/', 'DISK', controller_a=ha).json().keys())
disk_pool = sorted(list(set(disk_list) - set(nas_disk)))
# genrated token_hex 32bit for
pool_token_hex = secrets.token_hex(32)
pool_token_hex2 = secrets.token_hex(32)
dataset_token_hex = secrets.token_hex(32)
dataset_token_hex2 = secrets.token_hex(32)
dataset = f'{pool_name}/encrypted'
dataset_url = dataset.replace('/', '%2F')
child_dataset = f'{dataset}/child'
child_dataset_url = child_dataset.replace('/', '%2F')


def test_001_create_a_normal_pool():
    global pool_id
    payload = {
        'name': pool_name,
        'encryption': False,
        'topology': {
            'data': [
                {'type': 'STRIPE', 'disks': disk_pool}
            ],
        }
    }
    results = POST('/pool/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_id = job_status['results']['result']['id']


def test_002_create_a_passphrase_encrypted_root_on_normal_pool():
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


def test_003_verify_pool_dataset_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_004_add_the_comment_on_the_passphrase_encrypted_root():
    payload = {
        'comments': 'testing encrypted dataset'
    }
    results = PUT(f'/pool/dataset/id/{dataset_url}/', payload)
    assert results.status_code == 200, results.text


def test_005_change_a_passphrase_encrypted_root_key_encryption():
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


def test_006_verify_that_the_dataset_encrypted_root_changed_to_key_encryption():
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'HEX', results.text


def test_007_delete_passphrase_encrypted_root():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_008_create_not_encrypted_dataset_on_a_normal_pool():
    payload = {
        'name': dataset,
        'encryption': False,
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] is None, results.text


def test_009_delete_not_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_010_create_a_dataset_with_inherit_encryption_true_on_a_normal_pool():
    payload = {
        'name': dataset,
        'inherit_encryption': True
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_011_verify_that_the_dataset_created_is_not_encrypted_like_the_parrent():
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] is None, results.text


def test_012_delete_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_013_try_to_create_an_encrypted_dataset_with_pbkdf2itersl_zero():
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


def test_014_try_to_create_an_encrypted_dataset_with_inherit_encryption_true():
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


def test_015_verify_pool_dataset_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_016_try_to_create_an_encrypted_dataset_with_passphrase_and_generate_key():
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


def test_017_create_an_encrypted_root_with_generate_key():
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


def test_018_delete_generate_key_encrypted_root():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_019_create_an_encrypted_root_with_a_key():
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


def test_020_verify_pool_dataset_does_not_leak_encryption_key_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = f"""grep -R "{dataset_token_hex}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_021_make_sure_we_are_not_able_to_lock_key_encrypted_dataset():
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


def test_022_change_a_key_encrypted_dataset_to_passphrase():
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


def test_023_verify_that_the_dataset_changed_to_passphrase():
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'PASSPHRASE', results.text


def test_024_verify_pool_dataset_change_key_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_025_lock_passphrase_encrypted_datasets_and_ensure_they_get_locked():
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


def test_026_verify_passphrase_encrypted_root_is_locked():
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


def test_027_unlock_passphrase_encrypted_datasets_with_wrong_passphrase():
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
    assert job_status['results']['result']['failed']['tank/encrypted']['error'] == 'Invalid Key', str(job_status['results'])


def test_028_verify_passphrase_encrypted_root_still_locked():
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


def test_029_unlock_passphrase_encrypted_datasets():
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


def test_030_verify_passphrase_encrypted_root_is_unlocked():
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


def test_031_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_032_delete_pool():
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


def test_033_create_a_passphrase_encrypted_pool():
    global pool_id
    payload = {
        'name': pool_name,
        'encryption': True,
        'encryption_options': {
            'algorithm': 'AES-128-CCM',
            'passphrase': 'my_pool_passphrase',
        },
        'topology': {
            'data': [
                {'type': 'STRIPE', 'disks': disk_pool}
            ],
        }
    }
    results = POST('/pool/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_id = job_status['results']['result']['id']


def test_034_verify_pool_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_pool_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_035_verify_the_pool_dataset_is_passphrase_encrypted_and_algorithm_encryption():
    results = GET(f'/pool/dataset/id/{pool_name}/')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'PASSPHRASE', results.text
    assert results.json()['encryption_algorithm']['value'] == 'AES-128-CCM', results.text


def test_036_create_a_passphrase_encrypted_root_on_passphrase_encrypted_pool():
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


def test_037_verify_pool_dataset_change_key_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_038_try_to_change_a_passphrase_encrypted_root_to_key_on_passphrase_encrypted_pool():
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


def test_039_verify_pool_dataset_change_key_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_040_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_041_create_a_not_encrypted_dataset_on_a_passphrase_encrypted_pool():
    payload = {
        'name': dataset,
        'encryption': False,
        'inherit_encryption': False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] is None, results.text


def test_042_delete_not_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_043_create_a_dataset_to_inherit_encryption_from_the_passphrase_encrypted_pool():
    payload = {
        'name': dataset,
        'inherit_encryption': True
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'PASSPHRASE', results.text


def test_044_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_045_try_to_create_an_encrypted_root_with_generate_key_on_passphrase_encrypted_pool():
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


def test_046_try_to_create_an_encrypted_root_with_key_on_passphrase_encrypted_pool():
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


def test_047_verify_pool_dataset_does_not_leak_encryption_key_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = f"""grep -R "{dataset_token_hex}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_048_delete_the_passphrase_encrypted_pool_with_is_datasets():
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


def test_049_creating_a_key_encrypted_pool():
    global pool_id
    payload = {
        'name': pool_name,
        'encryption': True,
        'encryption_options': {
            'algorithm': 'AES-128-CCM',
            'key': pool_token_hex,
        },
        'topology': {
            'data': [
                {'type': 'STRIPE', 'disks': disk_pool}
            ],
        }
    }
    results = POST('/pool/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_id = job_status['results']['result']['id']


def test_050_verify_pool_does_not_leak_encryption_key_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = f"""grep -R "{pool_token_hex}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_051_verify_the_pool_dataset_is_hex_key_encrypted_and_algorithm_encryption():
    results = GET(f'/pool/dataset/id/{pool_name}/')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'HEX', results.text
    assert results.json()['encryption_algorithm']['value'] == 'AES-128-CCM', results.text


def test_052_creating_a_key_encrypted_root_on_key_encrypted_pool():
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


def test_053_verify_pool_dataset_does_not_leak_encryption_key_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = f"""grep -R "{dataset_token_hex}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_054_change_a_key_encrypted_root_to_passphrase_on_key_encrypted_pool():
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


def test_055_verify_pool_dataset_change_key_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_056_verify_the_dataset_changed_to_passphrase():
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'PASSPHRASE', results.text


def test_057_lock_passphrase_encrypted_dataset():
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


def test_058_verify_the_dataset_is_locked():
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['locked'] is True, results.text


def test_059_verify_passphrase_encrypted_root_unlock_successful_is_false():
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


def test_060_unlock_passphrase_encrypted_datasets():
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


def test_061_verify_pool_dataset_unlock_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_062_verify_passphrase_encrypted_root_is_unlocked():
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


def test_063_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_064_create_an_not_encrypted_dataset_on_a_key_encrypted_pool():
    payload = {
        'name': dataset,
        'encryption': False,
        'inherit_encryption': False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] is None, results.text


def test_065_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_066_create_an_dataset_with_inherit_encryption_from_the_key_encrypted_pool():
    payload = {
        'name': dataset,
        'inherit_encryption': True
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'HEX', results.text


def test_067_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_068_create_an_encrypted_dataset_with_generate_key_on_key_encrypted_pool():
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


def test_069_delete_generate_key_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_070_create_a_passphrase_encrypted_root_dataset_parrent():
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


def test_071_verify_pool_dataset_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_072_create_a_passphrase_encrypted_root_child_of_passphrase_parent():
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


def test_073_verify_pool_dataset_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase2" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_074_lock_passphrase_encrypted_root_with_is_child():
    payload = {
        'id': dataset,
    }
    results = POST('/pool/dataset/lock', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_075_verify_the_parrent_encrypted_root_unlock_successful_is_false():
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


def test_076_verify_the_dataset_is_locked():
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['locked'] is True, results.text


def test_077_verify_the_chid_of_the_encrypted_root_parent_unlock_successful_is_false():
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


def test_078_verify_the_child_dataset_is_locked():
    results = GET(f'/pool/dataset/id/{child_dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['locked'] is True, results.text


def test_079_try_to_unlock_the_child_of_lock_parent_encrypted_root():
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


def test_080_verify_pool_dataset_unlock_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase2" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_081_Verify_chid_unlock_successful_is_still_false():
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


def test_082_unlock_parent_dataset_with_child_recursively():
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


def test_083_verify_pool_dataset_unlock_with_child_dataset_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])
    cmd = """grep -R "my_passphrase2" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_084_verify_the_parent_dataset_unlock_successful_is_true():
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


def test_085_verify_the_dataset_is_unlocked():
    results = GET(f'/pool/dataset/id/{child_dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['locked'] is False, results.text


def test_086_verify_the_child_dataset_unlock_successful_is_true():
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


def test_087_verify_the_child_dataset_is_unlocked():
    results = GET(f'/pool/dataset/id/{child_dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['locked'] is False, results.text


def test_088_delete_dataset_with_is_child_recursive():
    payload = {
        "recursive": True,
    }
    results = DELETE(f'/pool/dataset/id/{dataset_url}/', payload)
    assert results.status_code == 200, results.text


def test_089_creating_a_key_encrypted_dataset_on_key_encrypted_pool():
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


def test_090_verify_pool_dataset_does_not_leak_encryption_key_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_091_create_a_passphrase_encrypted_root_from_key_encrypted_root():
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


def test_092_verify_pool_dataset_does_not_leak_passphrase_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "my_passphrase" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_093_verify_the_new_passprase_encrypted_root_is_passphrase():
    results = GET(f'/pool/dataset/id/{child_dataset_url}')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'PASSPHRASE', results.text


def test_094_run_inherit_parent_encryption_properties_on_the_passprase():
    results = POST('/pool/dataset/inherit_parent_encryption_properties', child_dataset)
    assert results.status_code == 200, results.text


def test_095_verify_the_the_child_got_props_by_the_parent_root():
    results = GET(f'/pool/dataset/id/{child_dataset_url}')
    assert results.status_code == 200, results.text
    assert results.json()['key_format']['value'] == 'HEX', results.text


def test_096_delete_the_key_encrypted_pool_with_all_the_dataset():
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
