#!/usr/bin/env python3

# License: BSD

import sys
import os
import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, PUT, SSH_TEST, wait_on_job
from auto_config import ip, pool_name, user, password

dataset = f'{pool_name}/encrypted'
dataset_url = dataset.replace('/', '%2F')


def test_01_create_an_encrypted_dataset():
    payload = {
        'name': dataset,
        "encryption_options": {
            "generate_key": False,
            "pbkdf2iters": 100000,
            "algorithm": "AES-128-CCM",
            "passphrase": "my_passpharase",
        },
        "encryption": True,
        "inherit_encryption": False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 200, results.text


def test_02_update_dataset_description():
    payload = {
        'comments': 'testing encrypted dataset'
    }
    results = PUT(f'/pool/dataset/id/{dataset_url}/', payload)
    assert results.status_code == 200, results.text


def test_03_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text


def test_04_try_to_create_an_encrypted_dataset_with_pbkdf2itersl_zero():
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


def test_05_try_to_create_an_encrypted_dataset_with_inherit_encryption_true():
    payload = {
        'name': dataset,
        "encryption_options": {
            "passphrase": "my_passpharase",
        },
        "encryption": True,
        "inherit_encryption": True
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text
    assert 'Must be disabled when encryption is enabled' in results.text, results.text


def test_06_try_to_create_an_encrypted_dataset_with_passphrase_and_generate_key():
    payload = {
        'name': dataset,
        "encryption_options": {
            "generate_key": True,
            "passphrase": "my_passpharase",
        },
        "encryption": True,
        "inherit_encryption": False
    }
    results = POST('/pool/dataset/', payload)
    assert results.status_code == 422, results.text
    assert 'Must be disabled when dataset is to be encrypted with passphrase' in results.text, results.text


def test_07_create_an_encrypted_dataset_with_generate_key():
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


def test_08_delete_encrypted_dataset():
    results = DELETE(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
