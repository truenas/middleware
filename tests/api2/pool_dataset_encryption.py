#!/usr/bin/env python3

# License: BSD

import sys
import os
import secrets
# import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, PUT, wait_on_job
from auto_config import pool_name  # , ha

nas_disk = GET('/boot/get_disks/').json()
disk_list = list(POST('/device/get_info/', 'DISK').json().keys())
disk_pool = sorted(list(set(disk_list) - set(nas_disk)))
# genrated token_hex 32bit for
pool_token_hex = secrets.token_hex(32)
pool_token_hex2 = secrets.token_hex(32)
dataset_token_hex = secrets.token_hex(32)
dataset_token_hex2 = secrets.token_hex(32)
dataset = f'{pool_name}/encrypted'
dataset_url = dataset.replace('/', '%2F')


def test_01_creating_an_pool():
    global pool_id
    payload = {
        "name": pool_name,
        "encryption": False,
        "topology": {
            "data": [
                {"type": "STRIPE", "disks": disk_pool}
            ],
        }
    }
    results = POST("/pool/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_id = job_status['results']['result']['id']


def test_02_creating_a_passphrase_encrypted_dataset():
    payload = {
        'name': dataset,
        "encryption_options": {
            "generate_key": False,
            "pbkdf2iters": 100000,
            "algorithm": "AES-128-CCM",
            "passphrase": "my_passphrase",
        },
        "encryption": True,
        "inherit_encryption": False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_03_update_dataset_description():
    payload = {
        'comments': 'testing encrypted dataset'
    }
    results = PUT(f'/pool/dataset/id/{dataset_url}/', payload)
    assert results.status_code == 200, results.text


def test_04_change_a_passphrase_encrypted_dataset_key():
    payload = {
        "id": dataset,
        "change_key_options": {
            "key": dataset_token_hex,
        }
    }
    results = POST(f'/pool/dataset/change_key/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_05_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_06_create_an_not_encrypted_dataset_to_a_not_encrypted_pool():
    payload = {
        'name': dataset,
        "encryption": False,
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_07_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_08_create_an_dataset_with_inherit_encryption_true_on_a_not_encrypted_pool():
    payload = {
        'name': dataset,
        "inherit_encryption": True
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_09_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_10_try_to_create_an_encrypted_dataset_with_pbkdf2itersl_zero():
    payload = {
        'name': dataset,
        "encryption_options": {
            "pbkdf2iters": 0,
        },
        "encryption": True,
        "inherit_encryption": False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text
    assert 'Should be greater or equal than 100000' in results.text, results.text


def test_11_try_to_create_an_encrypted_dataset_with_inherit_encryption_true():
    payload = {
        'name': dataset,
        "encryption_options": {
            "passphrase": "my_passphrase",
        },
        "encryption": True,
        "inherit_encryption": True
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text
    assert 'Must be disabled when encryption is enabled' in results.text, results.text


def test_12_try_to_create_an_encrypted_dataset_with_passphrase_and_generate_key():
    payload = {
        'name': dataset,
        "encryption_options": {
            "generate_key": True,
            "passphrase": "my_passphrase",
        },
        "encryption": True,
        "inherit_encryption": False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text
    assert 'Must be disabled when dataset is to be encrypted with passphrase' in results.text, results.text


def test_13_create_an_encrypted_dataset_with_generate_key():
    payload = {
        'name': dataset,
        "encryption_options": {
            "generate_key": True,
        },
        "encryption": True,
        "inherit_encryption": False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_14_delete_generate_key_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_15_create_an_encrypted_dataset_with_generate_key():
    payload = {
        'name': dataset,
        "encryption_options": {
            "key": dataset_token_hex,
        },
        "encryption": True,
        "inherit_encryption": False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_16_make_sure_we_are_not_able_to_lock_key_encrypted_datasets():
    payload = {
        "id": dataset,
        "lock_options": {
            "force_umount": True
        }
    }
    results = POST('/pool/dataset/lock', payload)
    assert results.status_code == 422, results.text
    assert 'Only datasets which are encrypted with passphrase can be locked' in results.text, results.text


def test_17_change_a_key_encrypted_dataset_to_passphrase():
    payload = {
        "id": dataset,
        "change_key_options": {
            "passphrase": "my_passphrase"
        }
    }
    results = POST('/pool/dataset/change_key/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_18_lock_passphrase_encrypted_datasets_and_ensure_they_get_locked():
    payload = {
        "id": dataset,
        "lock_options": {
            "force_umount": True
        }
    }
    results = POST('/pool/dataset/lock', payload)
    assert results.status_code == 200, results.text


def test_19_unlock_passphrase_encrypted_datasets_and_ensure_they_get_unlocked():
    payload = {
        "id": dataset,
    }
    results = POST('/pool/dataset/unlock', payload)
    assert results.status_code == 200, results.text


def test_20_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_21_delete_pool():
    payload = {
        "cascade": True,
        "restart_services": True,
        "destroy": True
    }
    results = POST(f"/pool/id/{pool_id}/export/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_22_creating_a_passphrase_encrypted_pool():
    global pool_id
    payload = {
        "name": pool_name,
        "encryption": True,
        "encryption_options": {
            "algorithm": "AES-128-CCM",
            "passphrase": "my_pool_passphrase",
        },
        "topology": {
            "data": [
                {"type": "STRIPE", "disks": disk_pool}
            ],
        }
    }
    results = POST("/pool/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_id = job_status['results']['result']['id']


def test_23_creating_an_encrypted_dataset():
    payload = {
        'name': dataset,
        "encryption_options": {
            "generate_key": False,
            "pbkdf2iters": 100000,
            "algorithm": "AES-128-CCM",
            "passphrase": "my_passphrase",
        },
        "encryption": True,
        "inherit_encryption": False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_24_update_dataset_description():
    payload = {
        'comments': 'testing encrypted dataset'
    }
    results = PUT(f'/pool/dataset/id/{dataset_url}/', payload)
    assert results.status_code == 200, results.text


def test_25_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_26_try_to_create_an_encrypted_dataset_with_pbkdf2itersl_zero():
    payload = {
        'name': dataset,
        "encryption_options": {
            "pbkdf2iters": 0,
        },
        "encryption": True,
        "inherit_encryption": False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text
    assert 'Should be greater or equal than 100000' in results.text, results.text


def test_27_try_to_create_an_encrypted_dataset_with_inherit_encryption_true():
    payload = {
        'name': dataset,
        "encryption_options": {
            "passphrase": "my_passphrase",
        },
        "encryption": True,
        "inherit_encryption": True
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text
    assert 'Must be disabled when encryption is enabled' in results.text, results.text


def test_28_try_to_create_an_encrypted_dataset_with_passphrase_and_generate_key():
    payload = {
        'name': dataset,
        "encryption_options": {
            "generate_key": True,
            "passphrase": "my_passphrase",
        },
        "encryption": True,
        "inherit_encryption": False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text
    assert 'Must be disabled when dataset is to be encrypted with passphrase' in results.text, results.text


def test_29_try_to_create_an_encrypted_dataset_with_generate_key_on_passphrase_pool():
    payload = {
        'name': dataset,
        "encryption_options": {
            "generate_key": True,
        },
        "encryption": True,
        "inherit_encryption": False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text
    assert 'Passphrase encrypted datasets cannot have children encrypted with a key' in results.text, results.text


def test_30_delete_the_passphrase_encrypted_pool():
    payload = {
        "cascade": True,
        "restart_services": True,
        "destroy": True
    }
    results = POST(f"/pool/id/{pool_id}/export/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_31_creating_a_key_encrypted_pool():
    global pool_id
    payload = {
        "name": pool_name,
        "encryption": True,
        "encryption_options": {
            "algorithm": "AES-128-CCM",
            'key': pool_token_hex,
        },
        "topology": {
            "data": [
                {"type": "STRIPE", "disks": disk_pool}
            ],
        }
    }
    results = POST("/pool/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_id = job_status['results']['result']['id']


def test_32_delete_the_key_encrypted_pool():
    payload = {
        "cascade": True,
        "restart_services": True,
        "destroy": True
    }
    results = POST(f"/pool/id/{pool_id}/export/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
