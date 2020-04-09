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
dataset_token_hex = secrets.token_hex(32)

dataset = f'{pool_name}/encrypted'
dataset_url = dataset.replace('/', '%2F')

five_pool = [
    'data1',
    'data2',
    'data3',
    'data4',
    'data5'
]


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


def test_02_creating_an_encrypted_dataset():
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


def test_04_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_05_try_to_create_an_encrypted_dataset_with_pbkdf2itersl_zero():
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


def test_06_try_to_create_an_encrypted_dataset_with_inherit_encryption_true():
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


def test_07_try_to_create_an_encrypted_dataset_with_passphrase_and_generate_key():
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


def test_08_create_an_encrypted_dataset_with_generate_key():
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


def test_09_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_10_delete_pool():
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


def test_11_creating_a_passphrase_encrypted_pool():
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


def test_12_delete_passphrase_encrypted_pool():
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